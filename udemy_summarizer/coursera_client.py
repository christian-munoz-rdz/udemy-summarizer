"""Cliente para la API interna de Coursera (api.coursera.org)."""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin

import requests

from .client import PlatformError, TokenExpiradoError
from .models import Course, Lecture, Section
from .transcript import (
    download_vtt,
    html_to_text,
    pick_subtitle_language,
    subtitle_to_text,
)

BASE_URL = "https://api.coursera.org/api"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

MEMBERSHIPS_URL = (
    f"{BASE_URL}/memberships.v1"
    "?includes=courseId,courses.v1"
    "&q=me&showHidden=true&filter=current,preEnrolled"
)

COURSE_URL = (
    f"{BASE_URL}/onDemandCourses.v1"
    "?q=slug&slug={slug}"
    "&includes=instructorIds,partnerIds,_links"
    "&fields=brandingImage,certificatePurchaseEnabledAt,"
    "partners.v1(squareLogo,rectangularLogo),"
    "instructors.v1(fullName),overridePartnerLogos,"
    "sessionsEnabledAt,domainTypes,premiumExperienceVariant,"
    "isRestrictedMembership"
)

MATERIALS_URL = (
    f"{BASE_URL}/onDemandCourseMaterials.v2/"
    "?q=slug&slug={slug}"
    "&includes=modules,lessons,passableItemGroups,passableItemGroupChoices,"
    "passableLessonElements,items,tracks,gradePolicy"
    "&fields=moduleIds,"
    "onDemandCourseMaterialModules.v1(name,slug,description,timeCommitment,"
    "lessonIds,optional,learningObjectives),"
    "onDemandCourseMaterialLessons.v1(name,slug,timeCommitment,elementIds,"
    "optional,trackId),"
    "onDemandCourseMaterialPassableItemGroups.v1(requiredPassedCount,"
    "passableItemGroupChoiceIds,trackId),"
    "onDemandCourseMaterialPassableItemGroupChoices.v1(name,description,itemIds),"
    "onDemandCourseMaterialPassableLessonElements.v1(gradingWeight,"
    "isRequiredForPassing),"
    "onDemandCourseMaterialItems.v2(name,slug,timeCommitment,contentSummary,"
    "isLocked,lockableByItem,itemLockedReasonCode,trackId,lockedStatus,"
    "itemLockSummary),"
    "onDemandCourseMaterialTracks.v1(passablesCount)"
    "&showLockedItems=true"
)

VIDEO_URL = (
    BASE_URL + "/onDemandLectureVideos.v1/{course_id}~{item_id}"
    "?includes=video"
    "&fields=onDemandVideos.v1(sources,subtitles,subtitlesVtt,subtitlesTxt)"
)

SUPPLEMENT_URL = (
    BASE_URL + "/onDemandSupplements.v1/{course_id}~{item_id}"
    "?includes=asset"
    "&fields=openCourseAssets.v1(typeName),openCourseAssets.v1(definition)"
)

COURSE_URL_RE = re.compile(r"coursera\.org/learn/([^/?#]+)")

VIDEO_TYPES = {"lecture"}
ARTICLE_TYPES = {"supplement"}


class CourseraError(PlatformError):
    """Error genérico de la API de Coursera."""


class CourseraTokenExpiradoError(TokenExpiradoError):
    def __init__(self) -> None:
        super().__init__(
            "La cookie CAUTH expiró o no es válida. Abre coursera.org en tu navegador, "
            "copia el valor de la cookie 'CAUTH' y actualízala en .env "
            "(COURSERA_CAUTH) o usa --token."
        )


class CourseraClient:
    def __init__(self, cauth: str, max_retries: int = 3) -> None:
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )
        self.session.cookies.set("CAUTH", cauth, domain=".coursera.org")

    def _get(self, url: str) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, timeout=30)
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(2**attempt)
                continue
            if resp.status_code in (401, 403):
                raise CourseraTokenExpiradoError()
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = CourseraError(f"HTTP {resp.status_code} en {url}")
                time.sleep(2**attempt)
                continue
            if not resp.ok:
                raise CourseraError(f"HTTP {resp.status_code} en {url}: {resp.text[:200]}")
            return resp.json()
        raise CourseraError(f"Fallo de red tras {self.max_retries} intentos: {last_exc}")

    def list_enrolled_courses(self) -> list[dict]:
        data = self._get(MEMBERSHIPS_URL)
        courses = data.get("linked", {}).get("courses.v1", [])
        return [
            {
                "id": course.get("id", course.get("slug", "")),
                "title": course.get("name", "Sin título"),
                "url": f"/learn/{course.get('slug', '')}",
                "slug": course.get("slug", ""),
            }
            for course in courses
        ]

    def resolve_course(self, arg: str) -> Course:
        slug = self._extract_slug(arg)
        data = self._get_course_metadata(slug)
        element = data["elements"][0]
        resolved_slug = element.get("slug", slug)
        title = element.get("name", slug)
        course_id = element["id"]
        return Course(
            id=course_id,
            title=title,
            url=f"https://www.coursera.org/learn/{resolved_slug}",
            slug=resolved_slug,
        )

    def get_curriculum(self, course: Course) -> Course:
        if not course.slug:
            raise CourseraError("El curso no tiene slug; llama a resolve_course primero.")
        data = self._get(MATERIALS_URL.format(slug=course.slug))
        if not data.get("elements"):
            raise CourseraError(f"No se encontró el temario para '{course.slug}'.")
        course.id = data["elements"][0]["id"]

        linked = data.get("linked", {})
        modules = {
            item["id"]: item for item in linked.get("onDemandCourseMaterialModules.v1", [])
        }
        lessons = {
            item["id"]: item for item in linked.get("onDemandCourseMaterialLessons.v1", [])
        }
        items = {
            item["id"]: item for item in linked.get("onDemandCourseMaterialItems.v2", [])
        }

        sections: list[Section] = []
        lecture_index = 0
        for module_index, module_id in enumerate(data["elements"][0].get("moduleIds", []), 1):
            module = modules.get(module_id)
            if not module:
                continue
            section = Section(index=module_index, title=module.get("name", "Sin título"))
            for lesson_id in module.get("lessonIds", []):
                lesson = lessons.get(lesson_id)
                if not lesson:
                    continue
                lesson_items = self._lesson_items(lesson, items, lesson_id)
                for item in lesson_items:
                    lecture = self._parse_item(item, lecture_index + 1)
                    if lecture.type == "other":
                        continue
                    lecture_index += 1
                    section.lectures.append(lecture)
            if section.lectures:
                sections.append(section)
        course.sections = sections
        return course

    def fetch_transcript(
        self, course: Course, lecture: Lecture, locale: str, fallback: str
    ) -> bool:
        if lecture.type == "article":
            return self._fetch_supplement_transcript(course, lecture)
        if lecture.type == "video":
            return self._fetch_video_transcript(course, lecture, locale, fallback)
        return False

    def describe_lecture(
        self, course: Course, lecture: Lecture, locale: str, fallback: str
    ) -> str:
        if lecture.type == "article":
            return "lectura"
        if lecture.type != "video":
            return lecture.type
        try:
            subtitles = self._get_video_subtitles(course, lecture)
        except CourseraError:
            return "video (subtítulos no verificados)"
        picked = pick_subtitle_language(subtitles.get("vtt", {}), locale, fallback)
        if picked:
            return f"subtítulos: {picked[0]}"
        picked = pick_subtitle_language(subtitles.get("txt", {}), locale, fallback)
        if picked:
            return f"transcripción: {picked[0]}"
        picked = pick_subtitle_language(subtitles.get("srt", {}), locale, fallback)
        if picked:
            return f"subtítulos: {picked[0]}"
        if subtitles.get("vtt") or subtitles.get("txt") or subtitles.get("srt"):
            return "subtítulos en otro idioma"
        return "sin subtítulos"

    def _extract_slug(self, arg: str) -> str:
        match = COURSE_URL_RE.search(arg)
        return match.group(1) if match else arg.strip().strip("/")

    def _get_course_metadata(self, slug: str) -> dict:
        candidates = [slug]
        if not re.search(r"-\d{3}$", slug):
            candidates.extend(f"{slug}-{version:03d}" for version in range(1, 4))
        last_error: CourseraError | None = None
        for candidate in candidates:
            try:
                return self._get(COURSE_URL.format(slug=candidate))
            except CourseraError as exc:
                last_error = exc
        raise last_error or CourseraError(f"No se encontró el curso '{slug}'.")

    @staticmethod
    def _lesson_items(lesson: dict, items: dict[str, dict], lesson_id: str) -> list[dict]:
        lesson_items = [
            items[item_id]
            for item_id in lesson.get("elementIds") or lesson.get("itemIds") or []
            if item_id in items
        ]
        if lesson_items:
            return lesson_items
        return [item for item in items.values() if item.get("lessonId") == lesson_id]

    @staticmethod
    def _parse_item(item: dict, object_index: int) -> Lecture:
        content = item.get("contentSummary") or {}
        type_name = (content.get("typeName") or "").strip()
        if type_name in VIDEO_TYPES:
            lecture_type = "video"
        elif type_name in ARTICLE_TYPES:
            lecture_type = "article"
        else:
            lecture_type = "other"
        return Lecture(
            id=item["id"],
            title=item.get("name", "Sin título"),
            object_index=object_index,
            type=lecture_type,
            content_id=item["id"],
        )

    def _fetch_video_transcript(
        self, course: Course, lecture: Lecture, locale: str, fallback: str
    ) -> bool:
        subtitles = self._get_video_subtitles(course, lecture)
        for fmt, mapping in (("vtt", subtitles["vtt"]), ("txt", subtitles["txt"]), ("srt", subtitles["srt"])):
            picked = pick_subtitle_language(mapping, locale, fallback)
            if not picked:
                continue
            language, url = picked
            lecture.transcript = subtitle_to_text(download_vtt(self._absolute_url(url)), fmt)
            lecture.transcript_locale = language
            return True
        return False

    def _fetch_supplement_transcript(self, course: Course, lecture: Lecture) -> bool:
        item_id = lecture.content_id or str(lecture.id)
        url = SUPPLEMENT_URL.format(course_id=course.id, item_id=item_id)
        data = self._get(url)
        assets = data.get("linked", {}).get("openCourseAssets.v1", [])
        if not assets:
            return False
        value = assets[0].get("definition", {}).get("value", "")
        if not value:
            return False
        lecture.transcript = html_to_text(value)
        return True

    def _get_video_subtitles(self, course: Course, lecture: Lecture) -> dict[str, dict[str, str]]:
        item_id = lecture.content_id or str(lecture.id)
        url = VIDEO_URL.format(course_id=course.id, item_id=item_id)
        data = self._get(url)
        videos = data.get("linked", {}).get("onDemandVideos.v1", [])
        if not videos:
            return {"vtt": {}, "txt": {}, "srt": {}}
        video = videos[0]
        return {
            "vtt": self._normalize_subtitle_map(video.get("subtitlesVtt") or {}),
            "txt": self._normalize_subtitle_map(video.get("subtitlesTxt") or {}),
            "srt": self._normalize_subtitle_map(video.get("subtitles") or {}),
        }

    @staticmethod
    def _normalize_subtitle_map(subtitles: dict[str, str]) -> dict[str, str]:
        return {
            language: url
            for language, url in subtitles.items()
            if isinstance(url, str) and url
        }

    @staticmethod
    def _absolute_url(url: str) -> str:
        if url.startswith("http"):
            return url
        return urljoin("https://www.coursera.org", url)

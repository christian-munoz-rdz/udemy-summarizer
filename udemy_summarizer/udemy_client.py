"""Cliente para la API interna de Udemy (api-2.0)."""

from __future__ import annotations

import re
import time

import requests

from .models import Course, Lecture, Section

BASE_URL = "https://www.udemy.com/api-2.0"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

CURRICULUM_FIELDS = (
    "page_size=200"
    "&fields[lecture]=title,object_index,asset"
    "&fields[chapter]=title,object_index"
    "&fields[asset]=asset_type,captions,body"
)

COURSE_URL_RE = re.compile(r"udemy\.com/course/([^/?#]+)")


class UdemyError(Exception):
    """Error genérico de la API de Udemy."""


class TokenExpiradoError(UdemyError):
    def __init__(self) -> None:
        super().__init__(
            "El access_token expiró o no es válido. Abre udemy.com en tu navegador, "
            "copia el valor de la cookie 'access_token' y vuelve a intentarlo "
            "(--token o variable de entorno UDEMY_ACCESS_TOKEN)."
        )


class UdemyClient:
    def __init__(self, access_token: str, max_retries: int = 3) -> None:
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {access_token}",
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )

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
                raise TokenExpiradoError()
            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = UdemyError(f"HTTP {resp.status_code} en {url}")
                time.sleep(2**attempt)
                continue
            if not resp.ok:
                raise UdemyError(f"HTTP {resp.status_code} en {url}: {resp.text[:200]}")
            return resp.json()
        raise UdemyError(f"Fallo de red tras {self.max_retries} intentos: {last_exc}")

    def _get_paginated(self, url: str) -> list[dict]:
        results: list[dict] = []
        next_url: str | None = url
        while next_url:
            data = self._get(next_url)
            results.extend(data.get("results", []))
            next_url = data.get("next")
        return results

    def list_enrolled_courses(self) -> list[dict]:
        url = f"{BASE_URL}/users/me/subscribed-courses/?fields[course]=id,title,url&page_size=100"
        return self._get_paginated(url)

    def resolve_course(self, arg: str) -> Course:
        """Acepta un ID numérico, un slug o una URL completa del curso."""
        match = COURSE_URL_RE.search(arg)
        slug_or_id = match.group(1) if match else arg.strip().strip("/")
        if slug_or_id.isdigit():
            data = self._get(f"{BASE_URL}/courses/{slug_or_id}/?fields[course]=id,title,url")
        else:
            data = self._get(f"{BASE_URL}/courses/{slug_or_id}/?fields[course]=id,title,url")
        return Course(id=data["id"], title=data["title"], url=data.get("url", ""))

    def get_curriculum(self, course: Course) -> Course:
        url = f"{BASE_URL}/courses/{course.id}/subscriber-curriculum-items/?{CURRICULUM_FIELDS}"
        items = self._get_paginated(url)

        sections: list[Section] = []
        current: Section | None = None
        for item in items:
            cls = item.get("_class")
            if cls == "chapter":
                current = Section(
                    index=len(sections) + 1, title=item.get("title", "Sin título")
                )
                sections.append(current)
            elif cls == "lecture":
                if current is None:
                    current = Section(index=1, title="Introducción")
                    sections.append(current)
                current.lectures.append(self._parse_lecture(item))
        course.sections = sections
        return course

    @staticmethod
    def _parse_lecture(item: dict) -> Lecture:
        asset = item.get("asset") or {}
        asset_type = (asset.get("asset_type") or "").lower()
        if asset_type == "video":
            ltype = "video"
        elif asset_type == "article":
            ltype = "article"
        else:
            ltype = "other"
        return Lecture(
            id=item["id"],
            title=item.get("title", "Sin título"),
            object_index=item.get("object_index", 0),
            type=ltype,
            captions=asset.get("captions") or [],
            body_html=asset.get("body"),
        )

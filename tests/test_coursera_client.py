import json
from pathlib import Path

import pytest
import responses

from udemy_summarizer.coursera_client import (
    BASE_URL,
    COURSE_URL,
    MATERIALS_URL,
    MEMBERSHIPS_URL,
    SUPPLEMENT_URL,
    VIDEO_URL,
    CourseraClient,
    CourseraTokenExpiradoError,
)
from udemy_summarizer.models import Course, Lecture

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client():
    return CourseraClient("cauth-falso", max_retries=1)


@responses.activate
def test_list_enrolled_courses(client):
    responses.add(
        responses.GET,
        MEMBERSHIPS_URL,
        json={
            "linked": {
                "courses.v1": [
                    {"id": "abc", "name": "Machine Learning", "slug": "machine-learning"}
                ]
            }
        },
    )
    courses = client.list_enrolled_courses()
    assert courses[0]["title"] == "Machine Learning"
    assert courses[0]["slug"] == "machine-learning"


@responses.activate
def test_resolve_course_from_url(client):
    data = json.loads((FIXTURES / "coursera_course.json").read_text(encoding="utf-8"))
    responses.add(responses.GET, COURSE_URL.format(slug="machine-learning"), json=data)
    course = client.resolve_course("https://www.coursera.org/learn/machine-learning")
    assert course.id == "course123"
    assert course.title == "Machine Learning"
    assert course.slug == "machine-learning"


@responses.activate
def test_token_expirado(client):
    responses.add(responses.GET, COURSE_URL.format(slug="x"), status=403)
    with pytest.raises(CourseraTokenExpiradoError):
        client.resolve_course("x")


@responses.activate
def test_get_curriculum_builds_sections(client):
    course = Course(
        id="course123",
        title="Machine Learning",
        url="https://www.coursera.org/learn/machine-learning",
        slug="machine-learning",
    )
    materials = json.loads((FIXTURES / "coursera_materials.json").read_text(encoding="utf-8"))
    responses.add(responses.GET, MATERIALS_URL.format(slug="machine-learning"), json=materials)
    client.get_curriculum(course)
    assert len(course.sections) == 1
    assert course.sections[0].title == "Semana 1"
    assert [lec.title for lec in course.sections[0].lectures] == [
        "Bienvenida",
        "Lectura complementaria",
    ]
    assert course.sections[0].lectures[0].type == "video"
    assert course.sections[0].lectures[1].type == "article"
    assert course.total_lectures == 2


@responses.activate
def test_fetch_video_transcript(client):
    course = Course(id="course123", title="ML", url="", slug="machine-learning")
    lecture = Lecture(
        id="item1",
        title="Bienvenida",
        object_index=1,
        type="video",
        content_id="item1",
    )
    video = json.loads((FIXTURES / "coursera_video.json").read_text(encoding="utf-8"))
    vtt = (FIXTURES / "sample_coursera.vtt").read_text(encoding="utf-8")
    responses.add(
        responses.GET,
        VIDEO_URL.format(course_id="course123", item_id="item1"),
        json=video,
    )
    responses.add(responses.GET, "https://www.coursera.org/subtitles/es.vtt", body=vtt)
    assert client.fetch_transcript(course, lecture, "es", "en") is True
    assert "Hola desde Coursera." in lecture.transcript
    assert lecture.transcript_locale == "es"


@responses.activate
def test_fetch_supplement_transcript(client):
    course = Course(id="course123", title="ML", url="", slug="machine-learning")
    lecture = Lecture(
        id="item2",
        title="Lectura",
        object_index=2,
        type="article",
        content_id="item2",
    )
    supplement = json.loads((FIXTURES / "coursera_supplement.json").read_text(encoding="utf-8"))
    responses.add(
        responses.GET,
        SUPPLEMENT_URL.format(course_id="course123", item_id="item2"),
        json=supplement,
    )
    assert client.fetch_transcript(course, lecture, "es", "en") is True
    assert "lectura complementaria" in lecture.transcript


@responses.activate
def test_describe_lecture_video(client):
    course = Course(id="course123", title="ML", url="", slug="machine-learning")
    lecture = Lecture(
        id="item1",
        title="Bienvenida",
        object_index=1,
        type="video",
        content_id="item1",
    )
    video = json.loads((FIXTURES / "coursera_video.json").read_text(encoding="utf-8"))
    responses.add(
        responses.GET,
        VIDEO_URL.format(course_id="course123", item_id="item1"),
        json=video,
    )
    status = client.describe_lecture(course, lecture, "es", "en")
    assert status == "subtítulos: es"

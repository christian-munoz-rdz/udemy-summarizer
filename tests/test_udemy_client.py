import pytest
import responses

from udemy_summarizer.models import Course
from udemy_summarizer.udemy_client import BASE_URL, TokenExpiradoError, UdemyClient


@pytest.fixture
def client():
    return UdemyClient("token-falso", max_retries=1)


@responses.activate
def test_list_enrolled_courses_paginates(client):
    url = f"{BASE_URL}/users/me/subscribed-courses/"
    responses.add(
        responses.GET,
        url,
        json={
            "results": [{"id": 1, "title": "Curso A", "url": "/course/a/"}],
            "next": f"{url}?page=2",
        },
    )
    responses.add(
        responses.GET,
        url,
        json={"results": [{"id": 2, "title": "Curso B", "url": "/course/b/"}], "next": None},
    )
    courses = client.list_enrolled_courses()
    assert [c["id"] for c in courses] == [1, 2]


@responses.activate
def test_resolve_course_from_url(client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/courses/python-total/",
        json={"id": 42, "title": "Python Total", "url": "/course/python-total/"},
    )
    course = client.resolve_course("https://www.udemy.com/course/python-total/learn/")
    assert course.id == 42
    assert course.title == "Python Total"


@responses.activate
def test_token_expirado(client):
    responses.add(responses.GET, f"{BASE_URL}/courses/x/", status=401)
    with pytest.raises(TokenExpiradoError):
        client.resolve_course("x")


@responses.activate
def test_get_curriculum_builds_sections(client):
    course = Course(id=42, title="Python Total", url="")
    responses.add(
        responses.GET,
        f"{BASE_URL}/courses/42/subscriber-curriculum-items/",
        json={
            "next": None,
            "results": [
                {"_class": "lecture", "id": 10, "title": "Bienvenida", "object_index": 1,
                 "asset": {"asset_type": "Video", "captions": [{"locale_id": "es_ES", "url": "u"}]}},
                {"_class": "chapter", "id": 1, "title": "Variables", "object_index": 1},
                {"_class": "lecture", "id": 11, "title": "Tipos de datos", "object_index": 2,
                 "asset": {"asset_type": "Video", "captions": []}},
                {"_class": "lecture", "id": 12, "title": "Recursos", "object_index": 3,
                 "asset": {"asset_type": "Article", "body": "<p>Hola</p>"}},
                {"_class": "quiz", "id": 99, "title": "Examen"},
            ],
        },
    )
    client.get_curriculum(course)
    assert [s.title for s in course.sections] == ["Introducción", "Variables"]
    assert course.sections[0].lectures[0].title == "Bienvenida"
    variables = course.sections[1]
    assert [lec.title for lec in variables.lectures] == ["Tipos de datos", "Recursos"]
    assert variables.lectures[1].type == "article"
    assert variables.lectures[1].body_html == "<p>Hola</p>"
    assert course.total_lectures == 3


@responses.activate
def test_fetch_transcript_video(client):
    from udemy_summarizer.models import Lecture

    course = Course(id=42, title="Python Total", url="")
    lecture = Lecture(
        id=10,
        title="Bienvenida",
        object_index=1,
        type="video",
        captions=[{"locale_id": "es_ES", "url": "http://example.com/es.vtt"}],
    )
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nHola desde Udemy."
    responses.add(responses.GET, "http://example.com/es.vtt", body=vtt)
    assert client.fetch_transcript(course, lecture, "es", "en") is True
    assert "Hola desde Udemy." in lecture.transcript
    assert lecture.transcript_locale == "es_ES"


@responses.activate
def test_fetch_transcript_article(client):
    from udemy_summarizer.models import Lecture

    course = Course(id=42, title="Python Total", url="")
    lecture = Lecture(
        id=12,
        title="Recursos",
        object_index=3,
        type="article",
        body_html="<p>Material de apoyo</p>",
    )
    assert client.fetch_transcript(course, lecture, "es", "en") is True
    assert lecture.transcript == "Material de apoyo"

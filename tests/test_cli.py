import pytest
import responses

from udemy_summarizer.cli import EXIT_OK, EXIT_TOKEN, main
from udemy_summarizer.udemy_client import BASE_URL


def test_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("UDEMY_ACCESS_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        main(["mi-curso"])
    assert "access_token" in capsys.readouterr().err


def test_requires_course_or_list(monkeypatch):
    with pytest.raises(SystemExit):
        main(["--token", "t"])


@responses.activate
def test_list_courses(capsys):
    responses.add(
        responses.GET,
        f"{BASE_URL}/users/me/subscribed-courses/",
        json={"results": [{"id": 7, "title": "Mi Curso", "url": "/course/mi-curso/"}], "next": None},
    )
    assert main(["--token", "t", "--list-courses"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "[7] Mi Curso" in out


@responses.activate
def test_expired_token_exit_code(capsys):
    responses.add(responses.GET, f"{BASE_URL}/users/me/subscribed-courses/", status=403)
    assert main(["--token", "t", "--list-courses"]) == EXIT_TOKEN


@responses.activate
def test_dry_run_prints_tree(capsys):
    responses.add(
        responses.GET,
        f"{BASE_URL}/courses/mi-curso/",
        json={"id": 7, "title": "Mi Curso", "url": "/course/mi-curso/"},
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/courses/7/subscriber-curriculum-items/",
        json={
            "next": None,
            "results": [
                {"_class": "chapter", "id": 1, "title": "Sección Uno", "object_index": 1},
                {"_class": "lecture", "id": 10, "title": "Lección A", "object_index": 1,
                 "asset": {"asset_type": "Video",
                           "captions": [{"locale_id": "es_ES", "url": "u"}]}},
                {"_class": "lecture", "id": 11, "title": "Lección B", "object_index": 2,
                 "asset": {"asset_type": "Video", "captions": []}},
            ],
        },
    )
    assert main(["--token", "t", "--dry-run", "mi-curso"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "Sección Uno" in out
    assert "subtítulos: es_ES" in out
    assert "sin subtítulos" in out

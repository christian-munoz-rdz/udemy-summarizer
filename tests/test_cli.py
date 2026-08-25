import json

import pytest
import responses

from udemy_summarizer.cli import EXIT_OK, EXIT_TOKEN, _resolve_locales, main
from udemy_summarizer.udemy_client import BASE_URL


def test_requires_token(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UDEMY_ACCESS_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        main(["mi-curso"])
    err = capsys.readouterr().err
    assert "UDEMY_ACCESS_TOKEN" in err
    assert ".env" in err


def test_requires_course_or_list(monkeypatch):
    with pytest.raises(SystemExit):
        main(["--token", "t"])


def test_reads_token_from_env_file(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UDEMY_ACCESS_TOKEN", raising=False)
    (tmp_path / ".env").write_text("UDEMY_ACCESS_TOKEN=from-file\n", encoding="utf-8")

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            f"{BASE_URL}/users/me/subscribed-courses/",
            json={"results": [{"id": 7, "title": "Mi Curso", "url": "/course/mi-curso/"}], "next": None},
        )
        assert main(["--list-courses"]) == EXIT_OK
    assert "[7] Mi Curso" in capsys.readouterr().out


def test_english_flag_sets_locale():
    parser = __import__("argparse").Namespace(
        english=True, locale="es", fallback_locale="en"
    )
    assert _resolve_locales(parser) == ("en", "en")


def test_locale_without_english_flag():
    parser = __import__("argparse").Namespace(
        english=False, locale="es", fallback_locale="en"
    )
    assert _resolve_locales(parser) == ("es", "en")


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


@responses.activate
def test_coursera_requires_token(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COURSERA_CAUTH", raising=False)
    with pytest.raises(SystemExit):
        main(["--platform", "coursera", "machine-learning"])
    err = capsys.readouterr().err
    assert "coursera" in err.lower()
    assert ".env" in err


@responses.activate
def test_coursera_dry_run(capsys):
    from pathlib import Path

    fixtures = Path(__file__).parent / "fixtures"
    course = json.loads((fixtures / "coursera_course.json").read_text(encoding="utf-8"))
    materials = json.loads((fixtures / "coursera_materials.json").read_text(encoding="utf-8"))
    video = json.loads((fixtures / "coursera_video.json").read_text(encoding="utf-8"))

    from udemy_summarizer.coursera_client import COURSE_URL, MATERIALS_URL, VIDEO_URL

    responses.add(responses.GET, COURSE_URL.format(slug="machine-learning"), json=course)
    responses.add(responses.GET, MATERIALS_URL.format(slug="machine-learning"), json=materials)
    responses.add(
        responses.GET,
        VIDEO_URL.format(course_id="course123", item_id="item1"),
        json=video,
    )
    assert main(
        ["--platform", "coursera", "--token", "t", "--dry-run", "machine-learning"]
    ) == EXIT_OK
    out = capsys.readouterr().out
    assert "Semana 1" in out
    assert "subtítulos: es" in out
    assert "lectura" in out

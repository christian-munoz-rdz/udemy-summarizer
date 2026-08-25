from pathlib import Path

from udemy_summarizer.models import Course
from udemy_summarizer.runner import (
    RunOptions,
    default_output_filename,
    resolve_locales,
    resolve_output_path,
    validate_options,
)


def test_resolve_locales_english():
    assert resolve_locales(RunOptions(english=True, locale="es", fallback_locale="fr")) == ("en", "en")


def test_resolve_locales_custom():
    assert resolve_locales(RunOptions(locale="es", fallback_locale="en")) == ("es", "en")


def test_default_output_filename():
    course = Course(id=7, title="Mi Curso!", url="")
    assert default_output_filename(course) == "mi-curso.pdf"


def test_resolve_output_path_with_directory(tmp_path):
    course = Course(id=1, title="Python Total", url="")
    options = RunOptions(output_dir=str(tmp_path), output_filename="estudio.pdf")
    assert resolve_output_path(options, course) == tmp_path / "estudio.pdf"


def test_resolve_output_path_adds_pdf_extension(tmp_path):
    course = Course(id=1, title="Python Total", url="")
    options = RunOptions(output_dir=str(tmp_path), output_filename="estudio")
    assert resolve_output_path(options, course) == tmp_path / "estudio.pdf"


def test_validate_options_requires_token(monkeypatch):
    monkeypatch.delenv("UDEMY_ACCESS_TOKEN", raising=False)
    message = validate_options(RunOptions(curso="mi-curso"))
    assert message is not None
    assert "UDEMY_ACCESS_TOKEN" in message


def test_validate_options_requires_course():
    message = validate_options(RunOptions(token="t"))
    assert message is not None
    assert "curso" in message.lower()

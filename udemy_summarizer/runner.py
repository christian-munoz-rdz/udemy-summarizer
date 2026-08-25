"""Pipeline compartido entre CLI y GUI."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from .client import PlatformError, TokenExpiradoError, create_client, default_token
from .models import Course

LogFn = Callable[[str], None]

EXIT_OK = 0
EXIT_ARGS = 1
EXIT_TOKEN = 2
EXIT_NETWORK = 3

PLATFORM_ENV = {
    "udemy": "UDEMY_ACCESS_TOKEN",
    "coursera": "COURSERA_CAUTH",
}


@dataclass
class RunOptions:
    platform: str = "udemy"
    token: str | None = None
    curso: str | None = None
    list_courses: bool = False
    locale: str = "es"
    fallback_locale: str = "en"
    english: bool = False
    output: str | None = None
    output_dir: str | None = None
    output_filename: str | None = None
    no_ai: bool = False
    model: str = "claude-opus-4-8"
    max_lectures: int | None = None
    dry_run: bool = False
    verbose: bool = False


@dataclass
class RunResult:
    exit_code: int
    output_path: str | None = None
    courses: list[dict] | None = None


def resolve_locales(options: RunOptions) -> tuple[str, str]:
    if options.english:
        return "en", "en"
    return options.locale, options.fallback_locale


def default_output_filename(course: Course) -> str:
    slug = re.sub(r"[^\w\-]+", "-", course.title.lower()).strip("-") or f"curso-{course.id}"
    return f"{slug}.pdf"


def resolve_output_path(options: RunOptions, course: Course) -> Path:
    if options.output:
        return Path(options.output)
    directory = Path(options.output_dir) if options.output_dir else Path.cwd()
    filename = options.output_filename or default_output_filename(course)
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return directory / filename


def resolve_token(options: RunOptions) -> str | None:
    token = (options.token or "").strip() or default_token(options.platform)
    return token or None


def validate_options(options: RunOptions) -> str | None:
    if not resolve_token(options):
        return (
            f"Falta la credencial de {options.platform}. "
            f"Define {PLATFORM_ENV[options.platform]} en el archivo .env "
            f"(copia .env.example) o indica un token."
        )
    if not options.list_courses and not (options.curso or "").strip():
        return "Indica el curso (URL, slug o ID) o usa listar cursos."
    return None


def run(options: RunOptions, log: LogFn = print) -> RunResult:
    error = validate_options(options)
    if error:
        log(error)
        return RunResult(exit_code=EXIT_ARGS)

    token = resolve_token(options)
    assert token is not None
    client = create_client(options.platform, token)
    platform_label = "Coursera" if options.platform == "coursera" else "Udemy"
    locale, fallback = resolve_locales(options)

    try:
        if options.list_courses:
            courses = client.list_enrolled_courses()
            if not courses:
                log("No se encontraron cursos inscritos.")
                return RunResult(exit_code=EXIT_OK, courses=[])
            log(f"Cursos inscritos ({len(courses)}):")
            for course in courses:
                log(f"  [{course['id']}] {course['title']}")
                url = course.get("url", "")
                if not url:
                    continue
                if url.startswith("http"):
                    log(f"        {url}")
                elif options.platform == "coursera":
                    log(f"        https://www.coursera.org{url}")
                else:
                    log(f"        https://www.udemy.com{url}")
            return RunResult(exit_code=EXIT_OK, courses=courses)

        curso = (options.curso or "").strip()
        course = client.resolve_course(curso)
        log(f"Curso: {course.title} (id {course.id})")
        log("Descargando el temario...")
        client.get_curriculum(course)
        apply_max_lectures(course, options.max_lectures)
        log(f"  {len(course.sections)} secciones, {course.total_lectures} lecciones")

        if options.dry_run:
            print_course_tree(client, course, locale, fallback, log)
            return RunResult(exit_code=EXIT_OK)

        download_transcripts(client, course, locale, fallback, options.verbose, log)

        if not options.no_ai:
            summarize(course, options.model, log)
        else:
            log("Resúmenes IA omitidos (--no-ai).")

        output_path = resolve_output_path(options, course)
        log(f"Generando PDF: {output_path}")
        from .pdf_builder import build_pdf

        build_pdf(course, str(output_path))
        log(f"Listo: {output_path}")
        return RunResult(exit_code=EXIT_OK, output_path=str(output_path))

    except TokenExpiradoError as exc:
        log(f"Error: {exc}")
        return RunResult(exit_code=EXIT_TOKEN)
    except (PlatformError, requests.RequestException) as exc:
        log(f"Error de red o de la API de {platform_label}: {exc}")
        return RunResult(exit_code=EXIT_NETWORK)


def apply_max_lectures(course: Course, limit: int | None) -> None:
    if not limit:
        return
    remaining = limit
    sections = []
    for section in course.sections:
        if remaining <= 0:
            break
        section.lectures = section.lectures[:remaining]
        remaining -= len(section.lectures)
        if section.lectures:
            sections.append(section)
    course.sections = sections


def print_course_tree(client, course: Course, locale: str, fallback: str, log: LogFn) -> None:
    for section in course.sections:
        log(f"\n[{section.index}] {section.title}")
        for lec in section.lectures:
            status = client.describe_lecture(course, lec, locale, fallback)
            log(f"    {section.index}.{lec.object_index} {lec.title}  ({status})")


def download_transcripts(
    client,
    course: Course,
    locale: str,
    fallback: str,
    verbose: bool,
    log: LogFn,
) -> None:
    total = course.total_lectures
    done = 0
    missing = 0
    log("Descargando transcripciones...")
    for section in course.sections:
        for lec in section.lectures:
            done += 1
            if verbose:
                log(f"  [{done}/{total}] {lec.title}")
            else:
                log(f"  {done}/{total}")
            try:
                if not client.fetch_transcript(course, lec, locale, fallback):
                    missing += 1
            except requests.RequestException as exc:
                missing += 1
                log(f"  Aviso: fallo descargando '{lec.title}': {exc}")
    if missing:
        log(f"  Aviso: {missing}/{total} lecciones sin transcripción en '{locale}'.")


def summarize(course: Course, model: str, log: LogFn) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("ANTHROPIC_API_KEY no definida en .env; se omiten los resúmenes IA.")
        return
    from .summarizer import Summarizer

    summarizer = Summarizer(model=model)
    total = len(course.sections)
    for i, section in enumerate(course.sections, 1):
        log(f"Resumiendo sección {i}/{total}: {section.title}")
        section.summary = summarizer.summarize_section(course.title, section)

"""CLI: orquestación del pipeline curso → transcripciones → resúmenes → PDF."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from . import __version__
from .client import PlatformError, TokenExpiradoError, create_client, default_token
from .models import Course

EXIT_OK = 0
EXIT_ARGS = 1
EXIT_TOKEN = 2
EXIT_NETWORK = 3

PLATFORM_ENV = {
    "udemy": "UDEMY_ACCESS_TOKEN",
    "coursera": "COURSERA_CAUTH",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="udemy-summarizer",
        description=(
            "Convierte un curso de Udemy o Coursera (en el que estás inscrito) "
            "en un PDF de estudio con transcripciones y resúmenes generados con IA."
        ),
    )
    parser.add_argument(
        "curso",
        nargs="?",
        help="URL, slug o ID del curso (omitir con --list-courses)",
    )
    parser.add_argument(
        "--platform",
        choices=["udemy", "coursera"],
        default="udemy",
        help="Plataforma del curso (default: udemy)",
    )
    parser.add_argument(
        "--token",
        help="Credencial de la plataforma (override de .env)",
    )
    parser.add_argument(
        "--list-courses", action="store_true", help="Listar cursos inscritos y salir"
    )
    parser.add_argument(
        "--locale", default="es", help="Idioma preferido de subtítulos (default: es). Usa 'en' para inglés."
    )
    parser.add_argument(
        "--fallback-locale",
        default="en",
        help="Idioma de respaldo si no hay subtítulos en --locale (default: en)",
    )
    parser.add_argument(
        "--english",
        action="store_true",
        help="Descargar transcripciones en inglés (equivale a --locale en --fallback-locale en)",
    )
    parser.add_argument("--output", help="Ruta del PDF de salida (default: <slug>.pdf)")
    parser.add_argument(
        "--no-ai", action="store_true", help="Omitir los resúmenes generados con Claude"
    )
    parser.add_argument(
        "--model", default="claude-opus-4-8", help="Modelo de Claude para los resúmenes"
    )
    parser.add_argument(
        "--max-lectures", type=int, help="Limitar el número de lecciones (para pruebas)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar la estructura del curso y la disponibilidad de subtítulos, sin descargar ni generar nada",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def load_env(env_file: Path | None = None) -> None:
    """Carga variables desde .env del directorio de trabajo (no pisa el entorno)."""
    load_dotenv(env_file or Path.cwd() / ".env")


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    token = args.token or default_token(args.platform)

    if not token:
        parser.error(
            f"Falta la credencial de {args.platform}. "
            f"Define {PLATFORM_ENV[args.platform]} en el archivo .env "
            f"(copia .env.example) o usa --token."
        )
    if not args.list_courses and not args.curso:
        parser.error("Indica el curso (URL, slug o ID) o usa --list-courses.")

    client = create_client(args.platform, token)
    platform_label = "Coursera" if args.platform == "coursera" else "Udemy"
    locale, fallback = _resolve_locales(args)
    try:
        if args.list_courses:
            return _cmd_list_courses(client, args.platform)

        course = client.resolve_course(args.curso)
        print(f"Curso: {course.title} (id {course.id})")
        print("Descargando el temario...")
        client.get_curriculum(course)
        _apply_max_lectures(course, args.max_lectures)
        print(f"  {len(course.sections)} secciones, {course.total_lectures} lecciones")

        if args.dry_run:
            _print_tree(client, course, locale, fallback)
            return EXIT_OK

        _download_transcripts(client, course, locale, fallback, args.verbose)

        if not args.no_ai:
            _summarize(course, args.model)
        else:
            print("Resúmenes IA omitidos (--no-ai).")

        output = args.output or _default_output(course)
        print(f"Generando PDF: {output}")
        from .pdf_builder import build_pdf

        build_pdf(course, output)
        print(f"Listo: {output}")
        return EXIT_OK

    except TokenExpiradoError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_TOKEN
    except (PlatformError, requests.RequestException) as exc:
        print(f"Error de red o de la API de {platform_label}: {exc}", file=sys.stderr)
        return EXIT_NETWORK


def _resolve_locales(args: argparse.Namespace) -> tuple[str, str]:
    if args.english:
        return "en", "en"
    return args.locale, args.fallback_locale


def _cmd_list_courses(client, platform: str) -> int:
    courses = client.list_enrolled_courses()
    if not courses:
        print("No se encontraron cursos inscritos.")
        return EXIT_OK
    print(f"Cursos inscritos ({len(courses)}):")
    for course in courses:
        print(f"  [{course['id']}] {course['title']}")
        url = course.get("url", "")
        if not url:
            continue
        if url.startswith("http"):
            print(f"        {url}")
        elif platform == "coursera":
            print(f"        https://www.coursera.org{url}")
        else:
            print(f"        https://www.udemy.com{url}")
    return EXIT_OK


def _apply_max_lectures(course: Course, limit: int | None) -> None:
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


def _print_tree(client, course: Course, locale: str, fallback: str) -> None:
    for section in course.sections:
        print(f"\n[{section.index}] {section.title}")
        for lec in section.lectures:
            status = client.describe_lecture(course, lec, locale, fallback)
            print(f"    {section.index}.{lec.object_index} {lec.title}  ({status})")


def _download_transcripts(client, course: Course, locale: str, fallback: str, verbose: bool) -> None:
    total = course.total_lectures
    done = 0
    missing = 0
    print("Descargando transcripciones...")
    for section in course.sections:
        for lec in section.lectures:
            done += 1
            if verbose:
                print(f"  [{done}/{total}] {lec.title}")
            else:
                print(f"\r  {done}/{total}", end="", flush=True)
            try:
                if not client.fetch_transcript(course, lec, locale, fallback):
                    missing += 1
            except requests.RequestException as exc:
                missing += 1
                print(f"\n  Aviso: fallo descargando '{lec.title}': {exc}", file=sys.stderr)
    if not verbose:
        print()
    if missing:
        print(f"  Aviso: {missing}/{total} lecciones sin transcripción en '{locale}'.")


def _summarize(course: Course, model: str) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY no definida en .env; se omiten los resúmenes IA.")
        return
    from .summarizer import Summarizer

    summarizer = Summarizer(model=model)
    total = len(course.sections)
    for i, section in enumerate(course.sections, 1):
        print(f"Resumiendo sección {i}/{total}: {section.title}")
        section.summary = summarizer.summarize_section(course.title, section)


def _default_output(course: Course) -> str:
    slug = re.sub(r"[^\w\-]+", "-", course.title.lower()).strip("-") or f"curso-{course.id}"
    return f"{slug}.pdf"


if __name__ == "__main__":
    sys.exit(main())

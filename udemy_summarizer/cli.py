"""CLI: orquestación del pipeline curso → transcripciones → resúmenes → PDF."""

from __future__ import annotations

import argparse
import os
import re
import sys

import requests

from . import __version__
from .models import Course
from .transcript import download_vtt, html_to_text, pick_caption, vtt_to_text
from .udemy_client import TokenExpiradoError, UdemyClient, UdemyError

EXIT_OK = 0
EXIT_ARGS = 1
EXIT_TOKEN = 2
EXIT_NETWORK = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="udemy-summarizer",
        description=(
            "Convierte un curso de Udemy (en el que estás inscrito) en un PDF de "
            "estudio con transcripciones y resúmenes generados con IA."
        ),
    )
    parser.add_argument(
        "curso",
        nargs="?",
        help="URL, slug o ID del curso (omitir con --list-courses)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("UDEMY_ACCESS_TOKEN"),
        help="Cookie access_token de Udemy (o variable UDEMY_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--list-courses", action="store_true", help="Listar cursos inscritos y salir"
    )
    parser.add_argument(
        "--locale", default="es", help="Idioma preferido de subtítulos (default: es)"
    )
    parser.add_argument(
        "--fallback-locale",
        default="en",
        help="Idioma de respaldo si no hay subtítulos en --locale (default: en)",
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.token:
        parser.error(
            "Falta el access_token de Udemy. Usa --token o define UDEMY_ACCESS_TOKEN."
        )
    if not args.list_courses and not args.curso:
        parser.error("Indica el curso (URL, slug o ID) o usa --list-courses.")

    client = UdemyClient(args.token)
    try:
        if args.list_courses:
            return _cmd_list_courses(client)

        course = client.resolve_course(args.curso)
        print(f"Curso: {course.title} (id {course.id})")
        print("Descargando el temario...")
        client.get_curriculum(course)
        _apply_max_lectures(course, args.max_lectures)
        print(f"  {len(course.sections)} secciones, {course.total_lectures} lecciones")

        if args.dry_run:
            _print_tree(course, args.locale, args.fallback_locale)
            return EXIT_OK

        _download_transcripts(course, args.locale, args.fallback_locale, args.verbose)

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
    except (UdemyError, requests.RequestException) as exc:
        print(f"Error de red o de la API de Udemy: {exc}", file=sys.stderr)
        return EXIT_NETWORK


def _cmd_list_courses(client: UdemyClient) -> int:
    courses = client.list_enrolled_courses()
    if not courses:
        print("No se encontraron cursos inscritos.")
        return EXIT_OK
    print(f"Cursos inscritos ({len(courses)}):")
    for c in courses:
        print(f"  [{c['id']}] {c['title']}")
        if c.get("url"):
            print(f"        https://www.udemy.com{c['url']}")
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


def _print_tree(course: Course, locale: str, fallback: str) -> None:
    for section in course.sections:
        print(f"\n[{section.index}] {section.title}")
        for lec in section.lectures:
            if lec.type == "article":
                status = "artículo"
            else:
                cap = pick_caption(lec.captions, locale, fallback)
                status = f"subtítulos: {cap['locale_id']}" if cap else "sin subtítulos"
            print(f"    {section.index}.{lec.object_index} {lec.title}  ({status})")


def _download_transcripts(course: Course, locale: str, fallback: str, verbose: bool) -> None:
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
                if lec.type == "article" and lec.body_html:
                    lec.transcript = html_to_text(lec.body_html)
                    continue
                cap = pick_caption(lec.captions, locale, fallback)
                if not cap:
                    missing += 1
                    continue
                lec.transcript = vtt_to_text(download_vtt(cap["url"]))
                lec.transcript_locale = cap.get("locale_id")
            except requests.RequestException as exc:
                missing += 1
                print(f"\n  Aviso: fallo descargando '{lec.title}': {exc}", file=sys.stderr)
    if not verbose:
        print()
    if missing:
        print(f"  Aviso: {missing}/{total} lecciones sin transcripción en '{locale}'.")


def _summarize(course: Course, model: str) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY no definida; se omiten los resúmenes IA.")
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

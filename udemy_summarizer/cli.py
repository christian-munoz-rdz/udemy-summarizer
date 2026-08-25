"""CLI: orquestación del pipeline curso → transcripciones → resúmenes → PDF."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import __version__
from .runner import (
    EXIT_OK,
    EXIT_TOKEN,
    PLATFORM_ENV,
    RunOptions,
    resolve_locales,
    resolve_token,
    run,
)


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


def args_to_options(args: argparse.Namespace) -> RunOptions:
    return RunOptions(
        platform=args.platform,
        token=args.token,
        curso=args.curso,
        list_courses=args.list_courses,
        locale=args.locale,
        fallback_locale=args.fallback_locale,
        english=args.english,
        output=args.output,
        no_ai=args.no_ai,
        model=args.model,
        max_lectures=args.max_lectures,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


def main(argv: list[str] | None = None) -> int:
    load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    options = args_to_options(args)

    if not resolve_token(options):
        parser.error(
            f"Falta la credencial de {options.platform}. "
            f"Define {PLATFORM_ENV[options.platform]} en el archivo .env "
            f"(copia .env.example) o usa --token."
        )
    if not options.list_courses and not options.curso:
        parser.error("Indica el curso (URL, slug o ID) o usa --list-courses.")

    def log(message: str) -> None:
        stream = sys.stderr if message.startswith(("Error", "  Aviso:")) else sys.stdout
        print(message, file=stream)

    return run(options, log=log).exit_code


def _resolve_locales(args: argparse.Namespace) -> tuple[str, str]:
    return resolve_locales(
        RunOptions(
            locale=args.locale,
            fallback_locale=args.fallback_locale,
            english=args.english,
        )
    )


if __name__ == "__main__":
    sys.exit(main())

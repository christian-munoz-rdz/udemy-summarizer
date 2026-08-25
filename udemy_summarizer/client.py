"""Interfaz común y factory para clientes de plataforma."""

from __future__ import annotations

import os
from typing import Protocol

from .models import Course, Lecture


class PlatformError(Exception):
    """Error genérico de la API de la plataforma."""


class TokenExpiradoError(PlatformError):
    """La credencial de autenticación expiró o no es válida."""


class CourseClient(Protocol):
    def list_enrolled_courses(self) -> list[dict]: ...

    def resolve_course(self, arg: str) -> Course: ...

    def get_curriculum(self, course: Course) -> Course: ...

    def fetch_transcript(
        self, course: Course, lecture: Lecture, locale: str, fallback: str
    ) -> bool: ...

    def describe_lecture(self, course: Course, lecture: Lecture, locale: str, fallback: str) -> str: ...


def default_token(platform: str) -> str | None:
    key = "COURSERA_CAUTH" if platform == "coursera" else "UDEMY_ACCESS_TOKEN"
    token = (os.environ.get(key) or "").strip()
    return token or None


def create_client(platform: str, token: str) -> CourseClient:
    if platform == "coursera":
        from .coursera_client import CourseraClient

        return CourseraClient(token)
    from .udemy_client import UdemyClient

    return UdemyClient(token)

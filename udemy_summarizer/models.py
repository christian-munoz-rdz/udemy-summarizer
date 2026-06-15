"""Modelos de datos del curso."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Lecture:
    id: int | str
    title: str
    object_index: int
    type: str  # "video" | "article" | "other"
    captions: list[dict] = field(default_factory=list)  # [{locale_id, url}]
    body_html: str | None = None
    transcript: str | None = None
    transcript_locale: str | None = None
    content_id: str | None = None  # ID de plataforma para fetch de subtítulos/suplementos


@dataclass
class Section:
    index: int
    title: str
    lectures: list[Lecture] = field(default_factory=list)
    summary: str | None = None


@dataclass
class Course:
    id: int | str
    title: str
    url: str
    slug: str | None = None
    sections: list[Section] = field(default_factory=list)

    @property
    def total_lectures(self) -> int:
        return sum(len(s.lectures) for s in self.sections)

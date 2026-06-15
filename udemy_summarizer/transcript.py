"""Descarga y limpieza de transcripciones (VTT) y artículos HTML."""

from __future__ import annotations

import re
from html.parser import HTMLParser

import requests

TIMESTAMP_RE = re.compile(r"-->")
CUE_TAG_RE = re.compile(r"</?[^>]+>")
SRT_INDEX_RE = re.compile(r"^\d+$")


def pick_caption(captions: list[dict], locale: str, fallback: str | None = None) -> dict | None:
    """Elige el subtítulo más adecuado: locale exacto → prefijo de idioma → fallback."""
    if not captions:
        return None
    lang = locale.split("_")[0].lower()

    for c in captions:
        if (c.get("locale_id") or "").lower() == locale.lower():
            return c
    for c in captions:
        if (c.get("locale_id") or "").lower().startswith(lang):
            return c
    if fallback and fallback.lower() != locale.lower():
        return pick_caption(captions, fallback, None)
    return None


def download_vtt(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def _timed_text_to_paragraphs(lines: list[str]) -> str:
    paragraphs: list[str] = []
    for i in range(0, len(lines), 6):
        paragraphs.append(" ".join(lines[i : i + 6]))
    return "\n\n".join(paragraphs)


def _extract_timed_caption_lines(raw_text: str) -> list[str]:
    lines: list[str] = []
    for raw in raw_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "NOTE", "STYLE", "Kind:", "Language:")):
            continue
        if TIMESTAMP_RE.search(line):
            continue
        if line.isdigit() or SRT_INDEX_RE.match(line):
            continue
        line = CUE_TAG_RE.sub("", line).strip()
        if not line:
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return lines


def vtt_to_text(vtt: str) -> str:
    """Convierte un archivo WEBVTT en texto plano en párrafos."""
    return _timed_text_to_paragraphs(_extract_timed_caption_lines(vtt))


def srt_to_text(srt: str) -> str:
    """Convierte un archivo SRT en texto plano en párrafos."""
    return _timed_text_to_paragraphs(_extract_timed_caption_lines(srt))


def subtitle_to_text(content: str, fmt: str | None = None) -> str:
    """Convierte subtítulos VTT, SRT o texto plano en párrafos legibles."""
    stripped = content.strip()
    if fmt == "txt" or (fmt is None and stripped and "-->" not in stripped and not stripped.startswith("WEBVTT")):
        return stripped
    if fmt == "srt" or (fmt is None and SRT_INDEX_RE.match(stripped.split("\n", 1)[0])):
        return srt_to_text(content)
    return vtt_to_text(content)


def pick_subtitle_language(
    subtitles: dict[str, str], locale: str, fallback: str | None = None
) -> tuple[str, str] | None:
    """Elige idioma de subtítulo Coursera: exacto → prefijo → fallback."""
    if not subtitles:
        return None
    lang = locale.split("_")[0].lower()
    normalized = {key.lower(): (key, url) for key, url in subtitles.items() if url}

    if locale.lower() in normalized:
        key, url = normalized[locale.lower()]
        return key, url
    for key, url in normalized.values():
        if key.lower().startswith(lang):
            return key, url
    if fallback and fallback.lower() != locale.lower():
        return pick_subtitle_language(subtitles, fallback, None)
    return None


class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    # Colapsar espacios y líneas en blanco múltiples
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()

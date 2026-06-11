"""Renderizado de diagramas Mermaid a PNG vía el servicio mermaid.ink."""

from __future__ import annotations

import base64

import requests

MERMAID_INK_URL = "https://mermaid.ink/img/"
PNG_MAGIC = b"\x89PNG"


def render_mermaid(code: str, timeout: int = 30) -> bytes | None:
    """Devuelve el PNG del diagrama, o None si el renderizado falla."""
    encoded = base64.urlsafe_b64encode(code.strip().encode("utf-8")).decode("ascii")
    url = f"{MERMAID_INK_URL}{encoded}?type=png&bgColor=white&width=900"
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return None
    if resp.ok and resp.content.startswith(PNG_MAGIC):
        return resp.content
    return None

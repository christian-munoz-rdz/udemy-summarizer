"""Resúmenes por sección con la API de Claude."""

from __future__ import annotations

import sys

import anthropic

from .models import Section

DEFAULT_MODEL = "claude-opus-4-8"

# Heurística conservadora: ~3 caracteres por token
MAX_INPUT_TOKENS = 150_000
CHUNK_TOKENS = 100_000

SYSTEM_PROMPT = """Eres un asistente de estudio experto. Recibirás las transcripciones \
de las lecciones de una sección de un curso online y debes generar un resumen de \
estudio en español, rico y didáctico, con este formato Markdown:

## Conceptos clave
Explica los conceptos principales de la sección en párrafos breves. Usa **negritas** \
para los términos importantes.

## Puntos importantes
- Lista de los puntos más relevantes para recordar.

## Ejemplos de código
Incluye esta sección solo si el contenido es técnico (programación, comandos, \
configuración). Reconstruye los ejemplos mencionados en las lecciones como bloques de \
código con su lenguaje:

```python
# ejemplo
```

Añade un comentario breve explicando qué hace cada ejemplo.

## Diagrama
Incluye esta sección solo cuando un diagrama ayude a visualizar un flujo, proceso, \
arquitectura o jerarquía explicada en la sección. Usa sintaxis Mermaid dentro de un \
bloque de código `mermaid` (prefiere `flowchart TD` o `flowchart LR`; mantenlo simple, \
máximo ~10 nodos, etiquetas cortas y sin caracteres especiales en los IDs):

```mermaid
flowchart LR
    Cliente --> Servidor --> BaseDeDatos[Base de datos]
```

Añade una frase antes del diagrama explicando qué representa.

## Términos y definiciones
- **Término**: definición breve.

Sé fiel al contenido de las transcripciones; no inventes información. Omite las \
secciones de código o diagrama si no aplican. No uses cursivas (guiones bajos) ni \
tablas Markdown."""


def _estimate_tokens(text: str) -> int:
    return len(text) // 3


class Summarizer:
    def __init__(self, model: str = DEFAULT_MODEL, client: anthropic.Anthropic | None = None) -> None:
        self.model = model
        self.client = client or anthropic.Anthropic(max_retries=5)

    def _complete(self, user_content: str, max_tokens: int = 8000) -> str:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            message = stream.get_final_message()
        return "".join(b.text for b in message.content if b.type == "text").strip()

    def summarize_section(self, course_title: str, section: Section) -> str | None:
        texts = [
            f"### Lección: {lec.title}\n\n{lec.transcript}"
            for lec in section.lectures
            if lec.transcript
        ]
        if not texts:
            return None

        header = f"Curso: {course_title}\nSección: {section.title}\n\n"
        full_text = header + "\n\n".join(texts)
        try:
            if _estimate_tokens(full_text) <= MAX_INPUT_TOKENS:
                return self._complete(full_text)
            return self._summarize_chunked(header, texts)
        except anthropic.APIError as exc:
            print(
                f"  Aviso: no se pudo resumir la sección '{section.title}': {exc}",
                file=sys.stderr,
            )
            return None

    def _summarize_chunked(self, header: str, texts: list[str]) -> str:
        """Map-reduce: resume bloques de lecciones y luego resume los parciales."""
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for text in texts:
            tokens = _estimate_tokens(text)
            if current and current_tokens + tokens > CHUNK_TOKENS:
                chunks.append("\n\n".join(current))
                current, current_tokens = [], 0
            current.append(text)
            current_tokens += tokens
        if current:
            chunks.append("\n\n".join(current))

        partials = [
            self._complete(f"{header}(Parte {i + 1} de {len(chunks)})\n\n{chunk}")
            for i, chunk in enumerate(chunks)
        ]
        combined = (
            f"{header}A continuación tienes resúmenes parciales de esta sección. "
            "Combínalos en un único resumen final con el formato indicado.\n\n"
            + "\n\n---\n\n".join(partials)
        )
        return self._complete(combined)

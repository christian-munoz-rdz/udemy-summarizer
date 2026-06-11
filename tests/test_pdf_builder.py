import io
from unittest.mock import patch

from PIL import Image

from udemy_summarizer.models import Course, Lecture, Section
from udemy_summarizer.pdf_builder import _split_segments, build_pdf


def _tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buf, format="PNG")
    return buf.getvalue()


SUMMARY_RICH = """## Conceptos clave
Python es un lenguaje. Usa `print()` para mostrar texto.
- **Variables**: cajas de datos.

## Ejemplos de código
```python
nombre = "Ana"
print(f"Hola, {nombre}")
```

## Diagrama
El flujo de ejecución:
```mermaid
flowchart LR
    Codigo --> Interprete --> Resultado
```
"""


def test_split_segments():
    segments = _split_segments(SUMMARY_RICH)
    kinds = [k for k, _ in segments]
    assert kinds == ["text", "code", "text", "mermaid"]
    assert 'print(f"Hola, {nombre}")' in segments[1][1]
    assert "flowchart LR" in segments[3][1]


def test_build_pdf_creates_valid_file(tmp_path):
    course = Course(
        id=1,
        title="Curso de Prueba: Python desde cero",
        url="",
        sections=[
            Section(
                index=1,
                title="Introducción",
                summary=SUMMARY_RICH,
                lectures=[
                    Lecture(id=1, title="Bienvenida", object_index=1, type="video",
                            transcript="Hola y bienvenidos. " * 50),
                    Lecture(id=2, title="Sin subtítulos", object_index=2, type="video"),
                ],
            ),
            Section(
                index=2,
                title="Variables y ñoños (acentos: á é í ó ú)",
                lectures=[
                    Lecture(id=3, title="Artículo", object_index=1, type="article",
                            transcript="Texto del artículo con eñes: ñandú."),
                ],
            ),
        ],
    )
    output = tmp_path / "curso.pdf"
    with patch("udemy_summarizer.pdf_builder.render_mermaid",
               return_value=_tiny_png()) as mock_render:
        build_pdf(course, str(output))
    assert mock_render.call_count == 1
    assert "flowchart LR" in mock_render.call_args.args[0]
    data = output.read_bytes()
    assert data[:5] == b"%PDF-"
    assert len(data) > 5000


def test_build_pdf_falls_back_to_code_when_mermaid_fails(tmp_path):
    course = Course(id=1, title="Curso", url="", sections=[
        Section(index=1, title="S1", summary=SUMMARY_RICH,
                lectures=[Lecture(id=1, title="L1", object_index=1, type="video",
                                  transcript="Texto.")]),
    ])
    output = tmp_path / "curso.pdf"
    with patch("udemy_summarizer.pdf_builder.render_mermaid", return_value=None):
        build_pdf(course, str(output))
    assert output.read_bytes()[:5] == b"%PDF-"

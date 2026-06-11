from udemy_summarizer.models import Course, Lecture, Section
from udemy_summarizer.pdf_builder import build_pdf


def test_build_pdf_creates_valid_file(tmp_path):
    course = Course(
        id=1,
        title="Curso de Prueba: Python desde cero",
        url="",
        sections=[
            Section(
                index=1,
                title="Introducción",
                summary="## Conceptos clave\nPython es un lenguaje.\n- **Variables**: cajas de datos.",
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
    build_pdf(course, str(output))
    data = output.read_bytes()
    assert data[:5] == b"%PDF-"
    assert len(data) > 5000

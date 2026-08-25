"""Generación del PDF de estudio con fpdf2."""

from __future__ import annotations

import datetime
import io
import re
import sys
from pathlib import Path

from fpdf import FPDF

from .mermaid import render_mermaid
from .models import Course

FONTS_DIR = Path(__file__).parent / "fonts"

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
FENCE_RE = re.compile(r"^```(\w*)\s*$")


class StudyPDF(FPDF):
    def __init__(self, course_title: str) -> None:
        super().__init__(format="A4")
        self.course_title = course_title
        self.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
        # fpdf2 pide variantes I/BI para markdown con *cursiva*; reutilizamos las TTF existentes
        self.add_font("DejaVu", "I", str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "BI", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVuMono", "", str(FONTS_DIR / "DejaVuSansMono.ttf"))
        self.add_font("DejaVuMono", "B", str(FONTS_DIR / "DejaVuSansMono-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=18)

    def note(self, text: str) -> None:
        """Aviso secundario en gris."""
        self.set_font("DejaVu", "", 10)
        self.set_text_color(130)
        self.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0)

    def footer(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(130)
        self.cell(0, 8, f"Página {self.page_no()}", align="C")
        self.set_text_color(0)


def build_pdf(course: Course, output_path: str) -> None:
    pdf = StudyPDF(course.title)

    # Portada
    pdf.add_page()
    pdf.set_y(90)
    pdf.set_font("DejaVu", "B", 24)
    pdf.multi_cell(0, 12, course.title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("DejaVu", "", 12)
    pdf.multi_cell(0, 8, "Material de estudio — transcripciones y resúmenes", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(110)
    fecha = datetime.date.today().strftime("%d/%m/%Y")
    pdf.multi_cell(0, 6, f"Generado con udemy-summarizer el {fecha}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0)

    # Índice: el placeholder registra la posición actual, reserva las páginas
    # indicadas y deja el cursor en una página nueva (donde empieza el contenido).
    pdf.add_page()
    toc_pages = max(1, (len(course.sections) + course.total_lectures) * 6 // 240 + 1)
    try:
        pdf.insert_toc_placeholder(_render_toc, pages=toc_pages, allow_extra_pages=True)
    except TypeError:  # fpdf2 antiguo sin allow_extra_pages
        pdf.insert_toc_placeholder(_render_toc, pages=toc_pages)

    # Contenido (la primera sección usa la página que dejó el placeholder)
    for i, section in enumerate(course.sections):
        if i > 0:
            pdf.add_page()
        pdf.start_section(f"{section.index}. {section.title}", level=0)
        pdf.set_font("DejaVu", "B", 16)
        pdf.set_fill_color(40, 60, 100)
        pdf.set_text_color(255)
        pdf.multi_cell(0, 10, f"Sección {section.index}: {section.title}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0)
        pdf.ln(4)

        if section.summary:
            _render_summary(pdf, section.summary)
        elif any(lec.transcript for lec in section.lectures):
            pdf.note("Resumen no disponible.")
            pdf.ln(2)

        for lecture in section.lectures:
            pdf.ln(3)
            pdf.start_section(lecture.title, level=1)
            pdf.set_font("DejaVu", "B", 12)
            pdf.multi_cell(0, 7, f"{section.index}.{lecture.object_index}  {lecture.title}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("DejaVu", "", 10)
            if lecture.transcript:
                pdf.multi_cell(0, 5.5, lecture.transcript, align="J", new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.note("Sin transcripción disponible.")

    pdf.output(output_path)


def _render_toc(pdf: StudyPDF, outline: list) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Índice", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("DejaVu", "", 10)
    for entry in outline:
        indent = 6 * entry.level
        link = pdf.add_link(page=entry.page_number)
        with pdf.local_context():
            if entry.level == 0:
                pdf.set_font("DejaVu", "B", 10)
            label = entry.name
            if len(label) > 80:
                label = label[:77] + "..."
            pdf.set_x(pdf.l_margin + indent)
            pdf.cell(0, 6, f"{label}  ·  pág. {entry.page_number}", link=link,
                     new_x="LMARGIN", new_y="NEXT")


def _split_segments(summary: str) -> list[tuple[str, str]]:
    """Divide el markdown en segmentos: ("text", ...), ("code"|"mermaid", ...)."""
    segments: list[tuple[str, str]] = []
    text_lines: list[str] = []
    code_lines: list[str] = []
    code_lang: str | None = None
    for raw in summary.splitlines():
        fence = FENCE_RE.match(raw.strip())
        if code_lang is None:
            if fence:
                if text_lines:
                    segments.append(("text", "\n".join(text_lines)))
                    text_lines = []
                code_lang = fence.group(1).lower()
            else:
                text_lines.append(raw)
        elif fence and not fence.group(1):
            kind = "mermaid" if code_lang == "mermaid" else "code"
            segments.append((kind, "\n".join(code_lines)))
            code_lines, code_lang = [], None
        else:
            code_lines.append(raw)
    if code_lines:  # bloque sin cerrar
        segments.append(("mermaid" if code_lang == "mermaid" else "code", "\n".join(code_lines)))
    if text_lines:
        segments.append(("text", "\n".join(text_lines)))
    return segments


def _render_code_block(pdf: StudyPDF, code: str) -> None:
    pdf.ln(1)
    pdf.set_font("DejaVuMono", "", 8.5)
    pdf.set_fill_color(245, 245, 245)
    pdf.multi_cell(0, 4.8, code.rstrip() or " ", fill=True, wrapmode="CHAR",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.ln(2)


def _render_diagram(pdf: StudyPDF, code: str) -> None:
    """Renderiza un diagrama Mermaid como imagen; si falla, muestra el código."""
    png = render_mermaid(code)
    if not png:
        print("  Aviso: no se pudo renderizar un diagrama Mermaid; se incluye el código.",
              file=sys.stderr)
        _render_code_block(pdf, code)
        return
    width = min(pdf.epw, 150)
    x = pdf.l_margin + (pdf.epw - width) / 2
    pdf.ln(2)
    pdf.image(io.BytesIO(png), x=x, w=width)
    pdf.ln(3)


def _render_text_lines(pdf: StudyPDF, text: str) -> None:
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            pdf.ln(2)
            continue
        if line.startswith("#"):
            pdf.set_font("DejaVu", "B", 11)
            pdf.multi_cell(0, 6, line.lstrip("# ").strip(), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("DejaVu", "", 10)
            continue
        bullet = ""
        if line.startswith(("- ", "* ")):
            bullet = "•  "
            line = line[2:]
        pdf.set_font("DejaVu", "", 10)
        line = INLINE_CODE_RE.sub(r"\1", line)
        # markdown=True renderiza **negritas** con la variante B de la fuente
        pdf.multi_cell(0, 5.5, bullet + line, markdown=True,
                       new_x="LMARGIN", new_y="NEXT")


def _render_summary(pdf: StudyPDF, summary: str) -> None:
    """Renderiza el resumen IA: texto con negritas, código y diagramas Mermaid."""
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("DejaVu", "B", 11)
    pdf.multi_cell(0, 7, "Resumen (IA)", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    for kind, content in _split_segments(summary):
        if kind == "text":
            _render_text_lines(pdf, content)
        elif kind == "mermaid":
            _render_diagram(pdf, content)
        else:
            _render_code_block(pdf, content)
    pdf.ln(3)

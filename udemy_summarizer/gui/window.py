"""Ventana principal de udemy-summarizer."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QThread, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..cli import load_env
from ..runner import RunOptions, resolve_token
from .worker import PipelineWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"udemy-summarizer {__version__}")
        self.resize(980, 720)
        self._thread: QThread | None = None
        self._worker: PipelineWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        layout.addWidget(self._build_platform_group())
        layout.addWidget(self._build_course_group())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_options_group())
        splitter.addWidget(self._build_log_group())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, stretch=1)

        actions = QHBoxLayout()
        self.run_button = QPushButton("Ejecutar")
        self.run_button.clicked.connect(self._on_run)
        self.list_button = QPushButton("Listar cursos")
        self.list_button.clicked.connect(self._on_list_courses)
        self.clear_log_button = QPushButton("Limpiar log")
        self.clear_log_button.clicked.connect(self.log_view.clear)
        actions.addWidget(self.run_button)
        actions.addWidget(self.list_button)
        actions.addStretch()
        actions.addWidget(self.clear_log_button)
        layout.addLayout(actions)

    def _build_platform_group(self) -> QGroupBox:
        group = QGroupBox("Plataforma y credenciales")
        form = QFormLayout(group)

        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["udemy", "coursera"])
        form.addRow("Plataforma", self.platform_combo)

        token_row = QHBoxLayout()
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Opcional: pisa el valor de .env")
        token_row.addWidget(self.token_input)
        self.show_token_check = QCheckBox("Mostrar")
        self.show_token_check.toggled.connect(self._toggle_token_visibility)
        token_row.addWidget(self.show_token_check)
        form.addRow("Token", token_row)

        return group

    def _build_course_group(self) -> QGroupBox:
        group = QGroupBox("Curso")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        self.curso_input = QLineEdit()
        self.curso_input.setPlaceholderText("URL, slug o ID del curso")
        row.addWidget(self.curso_input)
        layout.addLayout(row)

        self.course_list = QListWidget()
        self.course_list.setMaximumHeight(140)
        self.course_list.itemDoubleClicked.connect(self._pick_course_from_list)
        layout.addWidget(QLabel("Cursos inscritos (doble clic para seleccionar):"))
        layout.addWidget(self.course_list)

        return group

    def _build_options_group(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        subtitles = QGroupBox("Subtítulos")
        subtitles_form = QFormLayout(subtitles)
        self.locale_input = QLineEdit("es")
        self.fallback_locale_input = QLineEdit("en")
        self.english_check = QCheckBox("Transcripciones en inglés")
        self.english_check.toggled.connect(self._on_english_toggled)
        subtitles_form.addRow("Idioma preferido", self.locale_input)
        subtitles_form.addRow("Idioma de respaldo", self.fallback_locale_input)
        subtitles_form.addRow("", self.english_check)
        layout.addWidget(subtitles)

        output = QGroupBox("Salida")
        output_form = QFormLayout(output)
        folder_row = QHBoxLayout()
        self.output_dir_input = QLineEdit(str(Path.cwd()))
        self.output_dir_input.setPlaceholderText("Carpeta de destino del PDF")
        browse_button = QPushButton("Examinar…")
        browse_button.clicked.connect(self._browse_output_dir)
        folder_row.addWidget(self.output_dir_input)
        folder_row.addWidget(browse_button)
        self.output_filename_input = QLineEdit()
        self.output_filename_input.setPlaceholderText("Opcional: nombre del PDF (default: slug del curso)")
        output_form.addRow("Carpeta destino", folder_row)
        output_form.addRow("Nombre del archivo", self.output_filename_input)
        layout.addWidget(output)

        ai = QGroupBox("Resúmenes IA")
        ai_form = QFormLayout(ai)
        self.no_ai_check = QCheckBox("Omitir resúmenes con Claude")
        self.model_input = QLineEdit("claude-opus-4-8")
        ai_form.addRow("", self.no_ai_check)
        ai_form.addRow("Modelo", self.model_input)
        layout.addWidget(ai)

        advanced = QGroupBox("Avanzado")
        advanced_form = QFormLayout(advanced)
        self.max_lectures_spin = QSpinBox()
        self.max_lectures_spin.setRange(0, 9999)
        self.max_lectures_spin.setSpecialValueText("Sin límite")
        self.max_lectures_spin.setValue(0)
        self.dry_run_check = QCheckBox("Solo mostrar estructura (dry-run)")
        self.verbose_check = QCheckBox("Salida detallada")
        advanced_form.addRow("Máx. lecciones", self.max_lectures_spin)
        advanced_form.addRow("", self.dry_run_check)
        advanced_form.addRow("", self.verbose_check)
        layout.addWidget(advanced)
        layout.addStretch()

        return container

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        return group

    def _toggle_token_visibility(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.token_input.setEchoMode(mode)

    def _on_english_toggled(self, checked: bool) -> None:
        self.locale_input.setEnabled(not checked)
        self.fallback_locale_input.setEnabled(not checked)

    def _browse_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Elegir carpeta de destino",
            self.output_dir_input.text() or str(Path.cwd()),
        )
        if directory:
            self.output_dir_input.setText(directory)

    def _pick_course_from_list(self, item: QListWidgetItem) -> None:
        course_ref = item.data(Qt.ItemDataRole.UserRole)
        if course_ref:
            self.curso_input.setText(str(course_ref))

    def _append_log(self, message: str) -> None:
        self.log_view.append(message)

    def _set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)
        self.list_button.setEnabled(not busy)

    def _collect_options(self, *, list_courses: bool) -> RunOptions:
        max_lectures = self.max_lectures_spin.value()
        token = self.token_input.text().strip() or None
        filename = self.output_filename_input.text().strip() or None
        output_dir = self.output_dir_input.text().strip() or None

        return RunOptions(
            platform=self.platform_combo.currentText(),
            token=token,
            curso=self.curso_input.text().strip() or None,
            list_courses=list_courses,
            locale=self.locale_input.text().strip() or "es",
            fallback_locale=self.fallback_locale_input.text().strip() or "en",
            english=self.english_check.isChecked(),
            output_dir=output_dir,
            output_filename=filename,
            no_ai=self.no_ai_check.isChecked(),
            model=self.model_input.text().strip() or "claude-opus-4-8",
            max_lectures=max_lectures or None,
            dry_run=self.dry_run_check.isChecked(),
            verbose=self.verbose_check.isChecked(),
        )

    def _validate_before_run(self, options: RunOptions, *, list_courses: bool) -> bool:
        if not resolve_token(options):
            QMessageBox.warning(
                self,
                "Credencial faltante",
                f"Define la credencial de {options.platform} en .env o indica un token.",
            )
            return False
        if not list_courses and not options.curso:
            QMessageBox.warning(self, "Curso faltante", "Indica el curso o usa listar cursos.")
            return False
        if not list_courses and not options.dry_run:
            output_dir = Path(options.output_dir or Path.cwd())
            if not output_dir.is_dir():
                QMessageBox.warning(
                    self,
                    "Carpeta inválida",
                    "La carpeta de destino no existe o no es accesible.",
                )
                return False
        return True

    def _start_worker(self, options: RunOptions) -> None:
        if self._thread is not None:
            return

        self._set_busy(True)
        self._thread = QThread()
        self._worker = PipelineWorker(options)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.execute)
        self._worker.log_line.connect(self._append_log)
        self._worker.finished.connect(self._on_worker_finished)
        self._thread.start()

    def _on_list_courses(self) -> None:
        options = self._collect_options(list_courses=True)
        if not self._validate_before_run(options, list_courses=True):
            return
        self._append_log("--- Listando cursos ---")
        self._start_worker(options)

    def _on_run(self) -> None:
        options = self._collect_options(list_courses=False)
        if not self._validate_before_run(options, list_courses=False):
            return
        self._append_log("--- Iniciando ---")
        self._start_worker(options)

    def _on_worker_finished(self, exit_code: int, result: object) -> None:
        from ..runner import RunResult

        if isinstance(result, RunResult) and result.courses is not None:
            self.course_list.clear()
            platform = self.platform_combo.currentText()
            for course in result.courses:
                title = course.get("title", "Sin título")
                course_id = course.get("id", "")
                slug = course.get("slug")
                url = course.get("url", "")
                if slug:
                    ref = slug
                elif url.startswith("http"):
                    ref = url
                elif platform == "coursera" and url:
                    ref = url.removeprefix("/learn/").split("/")[0] or url
                elif url:
                    ref = url.strip("/").split("/")[-1] or str(course_id)
                else:
                    ref = str(course_id)
                item = QListWidgetItem(f"[{course_id}] {title}")
                item.setData(Qt.ItemDataRole.UserRole, ref)
                item.setToolTip(url or ref)
                self.course_list.addItem(item)

        if exit_code == 0:
            self._append_log("--- Completado ---")
        else:
            self._append_log(f"--- Terminado con código {exit_code} ---")

        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        self._set_busy(False)


def main() -> int:
    load_env()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()

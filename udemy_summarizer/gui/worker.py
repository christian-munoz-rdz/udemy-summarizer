"""Worker en segundo plano para la GUI."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from ..runner import RunOptions, run


class PipelineWorker(QObject):
    log_line = pyqtSignal(str)
    finished = pyqtSignal(int, object)

    def __init__(self, options: RunOptions) -> None:
        super().__init__()
        self._options = options

    def execute(self) -> None:
        result = run(self._options, log=self.log_line.emit)
        self.finished.emit(result.exit_code, result)

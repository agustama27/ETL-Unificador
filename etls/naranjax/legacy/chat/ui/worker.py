from __future__ import annotations

import threading
from collections.abc import Callable
from queue import Queue

from core.modelos import ArchivosDia, ConfigDia, ResultadoDia
from core.procesar_dia import procesar_dia


WorkerEvent = tuple[str, object]


class WorkerThread(threading.Thread):
    def __init__(self, config: ConfigDia, archivos: ArchivosDia, queue: Queue[WorkerEvent]) -> None:
        super().__init__(daemon=True)
        self._config = config
        self._archivos = archivos
        self._queue = queue

    def run(self) -> None:
        try:
            resultado = procesar_dia(self._config, self._archivos, log_cb=self._on_log)
            self._queue.put(("done", resultado))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _on_log(self, line: str) -> None:
        self._queue.put(("log", line))

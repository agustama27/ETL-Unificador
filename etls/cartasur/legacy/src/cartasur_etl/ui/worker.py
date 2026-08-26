from __future__ import annotations

import queue
import threading

from cartasur_etl.models import EtlConfig, InputFiles
from cartasur_etl.procesar_dia import procesar_dia


class WorkerThread(threading.Thread):
    def __init__(self, config: EtlConfig, archivos: InputFiles, events: queue.Queue):
        super().__init__(daemon=True)
        self._config = config
        self._archivos = archivos
        self._events = events

    def run(self) -> None:
        try:
            resultado = procesar_dia(
                self._config,
                self._archivos,
                log_cb=lambda line: self._events.put(("log", line)),
            )
            self._events.put(("done", resultado))
        except Exception as exc:  # last-resort guard for UI stability
            self._events.put(("error", f"No se pudo completar el proceso: {exc}"))

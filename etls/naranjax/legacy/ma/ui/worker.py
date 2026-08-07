from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from queue import Queue

from core.modelos import ArchivosDia, ConfigDia, ResultadoDia
from core.procesar_dia import procesar_dia
from core.procesar_tipificaciones import procesar_tipificaciones, resolve_tipificaciones_input_path
from core.modelos import ConfigTipificaciones


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


class BackResultadosWorkerThread(threading.Thread):
    def __init__(
        self,
        selected_input: str | None,
        output_dir: str,
        queue: Queue[WorkerEvent],
        cruce_origen: str = "none",
        cruce_path: str | None = None,
        cruce_lookup_path: str | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self._selected_input = selected_input
        self._output_dir = output_dir
        self._queue = queue
        self._cruce_origen = cruce_origen
        self._cruce_path = cruce_path
        self._cruce_lookup_path = cruce_lookup_path

    def run(self) -> None:
        try:
            resolved_input = resolve_tipificaciones_input_path(Path(self._selected_input) if self._selected_input else None)
            self._queue.put(("log", f"Input seleccionado: {resolved_input}"))
            result = procesar_tipificaciones(
                resolved_input,
                ConfigTipificaciones(
                    output_dir=Path(self._output_dir),
                    cruce_origen=self._cruce_origen,
                    cruce_path=Path(self._cruce_path) if self._cruce_path else None,
                    cruce_lookup_path=Path(self._cruce_lookup_path) if self._cruce_lookup_path else None,
                ),
                log_cb=self._on_log,
            )
            self._queue.put(("done", result))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _on_log(self, line: str) -> None:
        self._queue.put(("log", line))

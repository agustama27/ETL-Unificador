import threading
from pathlib import Path
from queue import Queue

from core.modelos import ArchivosDia, ConfigDia
from core.procesar_dia import procesar_dia
from core.modelos import ResultadoTipificaciones
from procesos.back_resultados import procesar as procesar_back_resultados


class WorkerThread(threading.Thread):
    def __init__(self, config: ConfigDia, archivos: ArchivosDia, queue: Queue):
        super().__init__(daemon=True)
        self._config = config
        self._archivos = archivos
        self._queue = queue

    def run(self) -> None:
        try:
            resultado = procesar_dia(self._config, self._archivos, log_cb=self._on_log, modo_ejecucion="ui")
            self._queue.put(("done", resultado))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _on_log(self, line: str) -> None:
        self._queue.put(("log", line))


class BackResultadosWorkerThread(threading.Thread):
    def __init__(
        self,
        selected_input: str,
        output_dir: str,
        queue: Queue,
        cruce_origen: str = "none",
        cruce_path: str | None = None,
        cruce_lookup_path: str | None = None,
    ):
        super().__init__(daemon=True)
        self._selected_input = selected_input
        self._output_dir = output_dir
        self._queue = queue
        self._cruce_origen = cruce_origen
        self._cruce_path = cruce_path
        self._cruce_lookup_path = cruce_lookup_path

    def run(self) -> None:
        try:
            historial_path = Path(self._selected_input) if self._selected_input else None
            logcall_path = Path(self._cruce_path) if self._cruce_path else None
            m30_path = Path(self._cruce_lookup_path) if self._cruce_lookup_path else None
            if m30_path is not None and m30_path.suffix.lower() != ".txt":
                raise ValueError("La base M30 debe ser un archivo .txt (pipe-delimited).")

            self._queue.put(("log", f"Historial: {historial_path or 'auto'}"))
            self._queue.put(("log", f"LOGCALL: {logcall_path or 'auto'}"))
            self._queue.put(("log", f"M30: {m30_path or 'auto'}"))

            output_path, anomalias_path, total = procesar_back_resultados(
                logcall_path=logcall_path,
                historial_path=historial_path,
                m30olos_path=m30_path,
                output_dir=Path(self._output_dir),
            )
            self._queue.put(("log", f"Anomalias: {anomalias_path}"))
            result = ResultadoTipificaciones(
                status="success",
                total_input_rows=total,
                total_output_rows=total,
                output_path=output_path,
            )
            self._queue.put(("done", result))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

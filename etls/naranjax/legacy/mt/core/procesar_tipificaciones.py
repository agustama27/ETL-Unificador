from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable

from core.log_bridge import bind_log_callback
from core.modelos import ConfigTipificaciones, ResultadoTipificaciones


LOGGER = logging.getLogger(__name__)

_BACK_RESULTADOS_ROOT = Path(__file__).resolve().parent.parent / "back-resultados"
if str(_BACK_RESULTADOS_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACK_RESULTADOS_ROOT))

from back_resultados_etl.io import load_input, save_output  # noqa: E402
from back_resultados_etl.logcall import build_logcall_input  # noqa: E402
from back_resultados_etl.transformers import transform  # noqa: E402


def resolve_tipificaciones_input_path(input_path: Path | None) -> Path:
    if input_path is not None:
        return input_path

    roman_dir = _BACK_RESULTADOS_ROOT / "roman"
    candidates: list[Path] = []
    for pattern in ("*.csv", "*.xlsx", "*.xls"):
        candidates.extend(roman_dir.glob(pattern))
    if not candidates:
        raise FileNotFoundError("No files found in default folder back-resultados/roman")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def procesar_tipificaciones(
    input_path: Path,
    config: ConfigTipificaciones,
    log_cb: Callable[[str], None] | None = None,
) -> ResultadoTipificaciones:
    try:
        with bind_log_callback(log_cb):
            if input_path.name.upper().startswith("LOGCALL_"):
                source_rows = build_logcall_input(input_path, config.cruce_path)
            else:
                source_rows = load_input(input_path)
                if config.cruce_path is not None:
                    source_rows = source_rows + build_logcall_input(config.cruce_path, config.cruce_lookup_path or input_path)

            output_rows, metrics = transform(source_rows, logger=LOGGER)
            output_path = save_output(output_rows, config.output_dir)

            return ResultadoTipificaciones(
                status="success",
                total_input_rows=metrics["total_input_rows"],
                total_output_rows=metrics["total_output_rows"],
                omitted_rows_total=metrics["omitted_rows_total"],
                warning_count=metrics["warning_count"],
                omitted_by_reason=metrics["omitted_by_reason"],
                output_path=output_path,
                output_contract={
                    "header": "(sin cabecera)",
                    "filename_prefix": "DEELO_NAR_USUEVOLTIS_",
                    "delimiter": "|",
                    "encoding": "cp1252",
                    "lineterminator": "\\n",
                    "quoting": "QUOTE_NONE",
                    "columns": "40 columnas estilo USUOLOS",
                },
            )
    except Exception as exc:
        LOGGER.exception("Error procesando tipificaciones")
        return ResultadoTipificaciones(status="error", errores=[str(exc)])

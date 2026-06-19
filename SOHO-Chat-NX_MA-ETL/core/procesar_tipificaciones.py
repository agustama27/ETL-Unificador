from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACK_RESULTADOS_DIR = ROOT_DIR / "back-resultados"
if str(BACK_RESULTADOS_DIR) not in sys.path:
    sys.path.insert(0, str(BACK_RESULTADOS_DIR))

from back_resultados_etl.io import load_input, save_output
from back_resultados_etl.transformers import transform

from .log_bridge import bind_log_callback
from .modelos import ConfigTipificaciones, ResultadoTipificaciones


LOGGER = logging.getLogger("core.procesar_tipificaciones")


def procesar_tipificaciones(
    input_path: Path,
    config: ConfigTipificaciones,
    log_cb: Callable[[str], None] | None = None,
) -> ResultadoTipificaciones:
    with bind_log_callback(log_cb):
        try:
            source_df = load_input(str(input_path))
            output_df = transform(source_df, logger=LOGGER)
            output_path = Path(save_output(output_df, str(config.output_dir)))
            return ResultadoTipificaciones(
                status="success",
                total_input_rows=int(output_df.attrs.get("total_input_rows", len(source_df))),
                total_output_rows=int(output_df.attrs.get("total_output_rows", len(output_df))),
                omitted_rows_total=int(output_df.attrs.get("omitted_rows_total", 0)),
                omitted_by_reason=dict(output_df.attrs.get("omitted_by_reason", {})),
                warning_count=int(output_df.attrs.get("warning_count", 0)),
                output_path=output_path,
            )
        except Exception as exc:
            LOGGER.exception("Tipificaciones execution failed in core")
            return ResultadoTipificaciones(status="error", errores=[str(exc)])

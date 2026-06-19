from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
BACK_RESULTADOS_DIR = ROOT_DIR / "back-resultados"
if str(BACK_RESULTADOS_DIR) not in sys.path:
    sys.path.insert(0, str(BACK_RESULTADOS_DIR))

from back_resultados_etl.io import load_input, save_output
from back_resultados_etl.logcall import build_logcall_input
from back_resultados_etl.constants import OUTPUT_COLUMNS_COUNT, OUTPUT_DATE_FORMAT, OUTPUT_DELIMITER, OUTPUT_ENCODING
from back_resultados_etl.transformers import transform

from .log_bridge import bind_log_callback
from .modelos import ConfigTipificaciones, ResultadoTipificaciones


LOGGER = logging.getLogger("core.procesar_tipificaciones")
DEFAULT_INPUT_DIR = BACK_RESULTADOS_DIR / "roman"


def resolve_tipificaciones_input_path(input_path: Path | None) -> Path:
    if input_path is not None:
        return input_path

    DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates: list[Path] = []
    for extension in ("*.csv", "*.xlsx", "*.xls"):
        candidates.extend(path for path in DEFAULT_INPUT_DIR.glob(extension) if path.is_file())

    if not candidates:
        raise FileNotFoundError(
            "No input file selected and no files found in default folder "
            f"'{DEFAULT_INPUT_DIR}'. Put a .csv/.xlsx/.xls file there or choose one explicitly."
        )

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    selected = candidates[0]
    LOGGER.info("Using latest input file from roman/: %s", selected)
    return selected


def procesar_tipificaciones(
    input_path: Path,
    config: ConfigTipificaciones,
    log_cb: Callable[[str], None] | None = None,
) -> ResultadoTipificaciones:
    with bind_log_callback(log_cb):
        try:
            if input_path.name.upper().startswith("LOGCALL_"):
                source_df = build_logcall_input(input_path, config.cruce_path)
            else:
                source_df = load_input(str(input_path))

            if config.cruce_path and not input_path.name.upper().startswith("LOGCALL_"):
                cruce_lookup = config.cruce_lookup_path or input_path
                logcall_df = build_logcall_input(config.cruce_path, cruce_lookup)
                source_df = pd.concat([source_df, logcall_df], ignore_index=True)
                LOGGER.info(
                    "Combinando ROMAN + LOGCALL: roman_rows=%s, logcall_rows=%s, cruce=%s",
                    len(source_df) - len(logcall_df),
                    len(logcall_df),
                    cruce_lookup,
                )
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
                output_contract={
                    "delimiter": OUTPUT_DELIMITER,
                    "encoding": OUTPUT_ENCODING,
                    "columns": OUTPUT_COLUMNS_COUNT,
                    "date_format": OUTPUT_DATE_FORMAT,
                },
            )
        except Exception as exc:
            LOGGER.exception("Tipificaciones execution failed in core")
            return ResultadoTipificaciones(status="error", errores=[str(exc)])

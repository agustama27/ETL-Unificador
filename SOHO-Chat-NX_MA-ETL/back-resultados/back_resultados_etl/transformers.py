"""Core transformation rules for IA voz PCT output."""

from __future__ import annotations

import logging
from collections import Counter

import pandas as pd

from .cleaners import (
    format_fecha_compromiso,
    normalize_result_key,
    resolve_fecha_promesa,
    to_clean_str,
    to_input_str_preserve,
    truncate_observaciones,
)
from .constants import OUTPUT_COLUMNS, TIPIF_MAP
from .validators import validate_dni


def transform(source_df: pd.DataFrame, logger: logging.Logger | None = None) -> pd.DataFrame:
    """Transform source rows into strict PCT output rows."""
    active_logger = logger or logging.getLogger("etl_tipificaciones_ia_voz_pct")

    records: list[dict[str, str]] = []
    omitted_by_reason: Counter[str] = Counter()
    warning_count = 0

    for idx, (_, row) in enumerate(source_df.iterrows(), start=2):
        row_number = idx
        result_key = normalize_result_key(row.get("tipificaciones", ""))
        codigo_pct = TIPIF_MAP.get(result_key)
        if not codigo_pct:
            omitted_by_reason["unmapped_tipificacion"] += 1
            warning_count += 1
            active_logger.warning(
                "Row %s: no mapping for tipificaciones=%r",
                row_number,
                row.get("tipificaciones", ""),
            )
            continue

        dni_raw = to_input_str_preserve(row.get("id_cliente", ""))
        dni_for_validation = to_clean_str(row.get("id_cliente", ""))
        if not validate_dni(dni_for_validation):
            omitted_by_reason["missing_dni"] += 1
            warning_count += 1
            active_logger.warning("Row %s: missing id_cliente, row omitted", row_number)
            continue

        fecha = resolve_fecha_promesa(
            to_clean_str(row.get("fecha_compromiso_tc", "")),
            to_clean_str(row.get("fecha_compromiso_nd", "")),
        )

        records.append(
            {
                "DNI": dni_raw,
                "TIPIFICACION": codigo_pct,
                "NROPRODUCTO": to_clean_str(row.get("id_nro_producto", "")),
                "FECHA_PROMESA": format_fecha_compromiso(fecha),
                "MONTO_PROMESA": to_clean_str(row.get("monto_compromiso", "")),
                "CALL_REFID": to_clean_str(row.get("call_refid", row.get("call_id", ""))),
                "OBSERVACIONES": truncate_observaciones(to_clean_str(row.get("observaciones", ""))),
            }
        )

    output_df = pd.DataFrame.from_records(records).reindex(columns=list(OUTPUT_COLUMNS))
    output_df.attrs["total_input_rows"] = len(source_df)
    output_df.attrs["total_output_rows"] = len(output_df)
    output_df.attrs["omitted_rows_total"] = int(sum(omitted_by_reason.values()))
    output_df.attrs["warning_count"] = warning_count
    output_df.attrs["omitted_by_reason"] = dict(omitted_by_reason)
    return output_df

from __future__ import annotations

from collections import Counter
from typing import Any

from .cleaners import (
    format_fecha_compromiso,
    normalize_upper_snake,
    resolve_fecha_promesa,
    to_clean_str,
    to_input_str_preserve,
    truncate_observaciones,
)
from .constants import TIPIF_MAP
from .validators import validate_dni


def transform(source_rows: list[dict[str, Any]], logger: Any = None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    output_rows: list[dict[str, str]] = []
    omitted_by_reason: Counter[str] = Counter()
    warning_count = 0

    for index, row in enumerate(source_rows, start=2):
        key = normalize_upper_snake(row.get("tipificaciones", ""))
        codigo = TIPIF_MAP.get(key)
        if not codigo:
            omitted_by_reason["unmapped_tipificacion"] += 1
            warning_count += 1
            if logger:
                logger.warning("Fila %s omitida: tipificacion no mapeada '%s'", index, row.get("tipificaciones", ""))
            continue

        dni_raw = to_input_str_preserve(row.get("id_cliente", ""))
        dni_clean = to_clean_str(row.get("id_cliente", ""))
        if not validate_dni(dni_clean):
            omitted_by_reason["missing_dni"] += 1
            warning_count += 1
            if logger:
                logger.warning("Fila %s omitida: DNI vacio", index)
            continue

        fecha = resolve_fecha_promesa(row.get("fecha_compromiso_tc", ""), row.get("fecha_compromiso_nd", ""))
        output_rows.append(
            {
                "DNI": dni_raw,
                "TIPIFICACION": codigo,
                "NROPRODUCTO": to_clean_str(row.get("id_nro_producto", "")),
                "FECHA_PROMESA": format_fecha_compromiso(fecha),
                "MONTO_PROMESA": to_clean_str(row.get("monto_compromiso", "")),
                "CALL_REFID": to_clean_str(row.get("call_refid", row.get("call_id", ""))),
                "OBSERVACIONES": truncate_observaciones(to_clean_str(row.get("observaciones", ""))),
            }
        )

    metrics = {
        "total_input_rows": len(source_rows),
        "total_output_rows": len(output_rows),
        "omitted_rows_total": len(source_rows) - len(output_rows),
        "warning_count": warning_count,
        "omitted_by_reason": dict(omitted_by_reason),
    }
    return output_rows, metrics

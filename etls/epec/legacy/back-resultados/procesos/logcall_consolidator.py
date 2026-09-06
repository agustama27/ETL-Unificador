"""
Pipeline para consolidar archivos de Roman + Logcall en un Excel.
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd


logger = logging.getLogger(__name__)


OUTPUT_COLUMNS = [
    "Fecha y Hora",
    "Desde",
    "[Entrada] Contrato",
    "[Entrada] Suministro",
    "[Entrada] Razón social",
    "[Salida] Impedimento",
    "[Salida] Confirmo Solucion",
    "[Salida] Contacto Efectivo",
    "[Salida] Resultado Efectivamente Informado",
    "[Salida] Disponibilidad Horaria",
    "[Salida] Domicilio Referencias",
    "[Salida] Hubo Interaccion",
    "[Salida] Motivo No Entrega",
    "[Salida] Duracion Total Seg",
    "[Salida] Tipo Contacto",
    "[Salida] Utilidad Informacion",
]


def _strip_io_prefix(column_name: str) -> str:
    for prefix in ("[Salida] ", "[Entrada] "):
        if column_name.startswith(prefix):
            return column_name[len(prefix) :]
    return column_name


OUTPUT_EXPORT_COLUMNS = [_strip_io_prefix(column) for column in OUTPUT_COLUMNS]


BOOLEAN_OUTPUT_COLUMNS = [
    "[Salida] Confirmo Solucion",
    "[Salida] Contacto Efectivo",
    "[Salida] Hubo Interaccion",
    "[Salida] Resultado Efectivamente Informado",
]


UTILIDAD_INFORMACION_DEFAULT = "No informado"


SENSITIVE_TEXT_COLUMNS = [
    "Desde",
    "[Entrada] Contrato",
    "[Entrada] Suministro",
]


INPUT_COLUMN_FALLBACKS = {
    "[Entrada] Razón social": (
        "[Entrada] nombre_cliente",
        "[Entrada] customer_name",
        "nombre_cliente",
        "customer_name",
    ),
}


RESULT_CODE_MOTIVO_NO_ENTREGA: Dict[int, str] = {
    1004: "contestador",
    7: "ocupado",
    9: "número errado",
    8: "no contesta",
    16: "número fuera de servicio",
    18: "error técnico",
}


RESULT_CODE_TIPO_CONTACTO: Dict[int, str] = {
    1004: "Contestador",
    7: "Desconocido",
    9: "Desconocido",
    8: "Desconocido",
    16: "Desconocido",
    18: "Desconocido",
}


def build_output_filename(now: datetime | None = None) -> str:
    run_date = now or datetime.now()
    return f"output_luz_{run_date.strftime('%d_%m_%y')}.xlsx"


def generate_consolidated_dataframe(roman_folder: Path, logcall_folder: Path) -> pd.DataFrame:
    roman_df = _load_roman_files(roman_folder)
    logcall_df = _load_logcall_files(logcall_folder)

    roman_phone_keys = _extract_normalized_phone_keys(roman_df, "Desde")
    no_connected_df = _build_no_connected_rows(logcall_df, excluded_phone_keys=roman_phone_keys)
    combined = pd.concat([roman_df, no_connected_df], ignore_index=True)

    if combined.empty:
        return _empty_output_dataframe()

    sort_key = pd.to_datetime(combined["Fecha y Hora"], format="%d/%m/%Y, %H:%M", errors="coerce")
    combined = combined.assign(_sort_datetime=sort_key)
    combined = combined.sort_values(by="_sort_datetime", ascending=False, na_position="last")
    combined = combined.drop(columns=["_sort_datetime"])

    output = _ensure_output_shape(combined)
    output = _normalize_canonical_fields(output)
    return _fill_missing_with_dash(output)


def get_consolidation_summary(roman_folder: Path, logcall_folder: Path) -> dict:
    roman_df = _load_roman_files(roman_folder)
    logcall_df = _load_logcall_files(logcall_folder)

    result_counts = {}
    if not logcall_df.empty and "RESULT" in logcall_df.columns:
        counts_series = (
            pd.to_numeric(logcall_df["RESULT"], errors="coerce")
            .dropna()
            .astype(int)
            .value_counts()
            .sort_index()
        )
        result_counts = counts_series.to_dict()

    roman_phone_keys = _extract_normalized_phone_keys(roman_df, "Desde")
    logcall_unique_df = _deduplicate_logcall_by_phone(logcall_df)
    unique_non_connected_df = logcall_unique_df[
        (logcall_unique_df["RESULT"] != 10)
        & (~logcall_unique_df["_phone_key"].isin(roman_phone_keys))
    ] if not logcall_unique_df.empty and "RESULT" in logcall_unique_df.columns else pd.DataFrame()

    return {
        "roman_rows": len(roman_df),
        "logcall_rows": len(logcall_df),
        "logcall_connected_result_10": result_counts.get(10, 0),
        "logcall_non_connected_rows": sum(v for k, v in result_counts.items() if k != 10),
        "logcall_unique_phones": len(logcall_unique_df),
        "logcall_unique_non_connected_rows": len(unique_non_connected_df),
        "logcall_result_distribution": result_counts,
    }


def write_consolidated_excel(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_df = _ensure_sensitive_columns_as_text(_ensure_output_shape(df))
    export_df = export_df.rename(columns=dict(zip(OUTPUT_COLUMNS, OUTPUT_EXPORT_COLUMNS)))
    export_df = export_df[OUTPUT_EXPORT_COLUMNS]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Sheet1")

        worksheet = writer.book["Sheet1"]
        worksheet.column_dimensions["B"].width = 32.28515625


def _load_roman_files(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.csv"), key=lambda f: f.name.lower())
    if not files:
        logger.warning("No se encontraron archivos Roman en %s", folder)
        return _empty_output_dataframe()

    dataframes: List[pd.DataFrame] = []
    for file_path in files:
        df = _read_csv_with_fallback(file_path)
        df = _normalize_roman_dataframe(df)
        dataframes.append(df)

    merged = pd.concat(dataframes, ignore_index=True)

    if "ID de Llamada" in merged.columns:
        merged = merged.drop_duplicates(subset=["ID de Llamada"], keep="last")

    merged = _ensure_output_shape(merged)

    logger.info("Roman consolidado: %s archivos, %s registros", len(files), len(merged))
    return merged


def _load_logcall_files(folder: Path) -> pd.DataFrame:
    files = sorted(folder.glob("*.csv"), key=lambda f: f.name.lower())
    if not files:
        logger.warning("No se encontraron archivos Logcall en %s", folder)
        return pd.DataFrame()

    dataframes: List[pd.DataFrame] = []
    for file_path in files:
        df = _read_csv_with_fallback(file_path)
        dataframes.append(df)

    merged = pd.concat(dataframes, ignore_index=True)
    merged = _drop_embedded_logcall_headers(merged)

    if "CALLREFID" in merged.columns:
        merged = merged.drop_duplicates(subset=["CALLREFID"], keep="last")

    logger.info("Logcall consolidado: %s archivos, %s registros", len(files), len(merged))
    return merged


def _drop_embedded_logcall_headers(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "PHONE" not in df.columns:
        return df

    header_like_phone_tokens = {"numerotelefono", "telefono", "phone"}

    normalized_phone = df["PHONE"].apply(lambda value: _normalize_column_name(str(value)))
    header_like_mask = normalized_phone.isin(header_like_phone_tokens)

    dropped_rows = int(header_like_mask.sum())
    if dropped_rows:
        logger.warning("Se descartaron %s filas Logcall con cabecera incrustada", dropped_rows)

    return df.loc[~header_like_mask].copy()


def _build_no_connected_rows(
    logcall_df: pd.DataFrame,
    excluded_phone_keys: set[str] | None = None,
) -> pd.DataFrame:
    if logcall_df.empty:
        return _empty_output_dataframe()

    if "RESULT" not in logcall_df.columns:
        logger.warning("Logcall no contiene columna RESULT; no se agregarán no conectados")
        return _empty_output_dataframe()

    df = _deduplicate_logcall_by_phone(logcall_df)
    if df.empty:
        return _empty_output_dataframe()

    excluded_phone_keys = excluded_phone_keys or set()
    if excluded_phone_keys and "_phone_key" in df.columns:
        before_exclusion = len(df)
        df = df[~df["_phone_key"].isin(excluded_phone_keys)].copy()
        excluded_rows = before_exclusion - len(df)
        if excluded_rows:
            logger.info(
                "Se omitieron %s teléfonos Logcall porque ya existen en Roman/conectados",
                excluded_rows,
            )

    df = df[df["RESULT"] != 10].copy()
    if df.empty:
        return _empty_output_dataframe()

    rows: List[dict] = []
    for _, row in df.iterrows():
        result_code = int(row["RESULT"])
        motivo_no_entrega = RESULT_CODE_MOTIVO_NO_ENTREGA.get(result_code, "error técnico")
        tipo_contacto = RESULT_CODE_TIPO_CONTACTO.get(result_code, "Desconocido")

        row_payload = {col: "" for col in OUTPUT_COLUMNS}
        row_payload["Fecha y Hora"] = _build_datetime_string(row.get("LOGDATE"), row.get("LOGTIME"))
        row_payload["Desde"] = _normalize_phone(row.get("PHONE"))
        row_payload["[Salida] Contacto Efectivo"] = "No"
        row_payload["[Salida] Duracion Total Seg"] = row.get("LENGTHCALL", "")
        row_payload["[Salida] Hubo Interaccion"] = "No"
        row_payload["[Salida] Motivo No Entrega"] = motivo_no_entrega
        row_payload["[Salida] Resultado Efectivamente Informado"] = "No"
        row_payload["[Salida] Tipo Contacto"] = tipo_contacto
        row_payload["[Salida] Utilidad Informacion"] = UTILIDAD_INFORMACION_DEFAULT

        rows.append(row_payload)

    return _ensure_output_shape(pd.DataFrame(rows))


def _deduplicate_logcall_by_phone(logcall_df: pd.DataFrame) -> pd.DataFrame:
    if logcall_df.empty or "PHONE" not in logcall_df.columns or "RESULT" not in logcall_df.columns:
        return pd.DataFrame()

    df = logcall_df.copy()
    df["RESULT"] = pd.to_numeric(df["RESULT"], errors="coerce")
    df = df[df["RESULT"].notna()].copy()
    df["RESULT"] = df["RESULT"].astype(int)

    df["_phone_key"] = df["PHONE"].apply(_normalize_phone_key)
    df = df[df["_phone_key"] != ""].copy()
    if df.empty:
        return df

    df["_sort_datetime"] = pd.to_datetime(
        df["LOGDATE"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(8)
        + df["LOGTIME"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6),
        format="%Y%m%d%H%M%S",
        errors="coerce",
    )
    df = df.sort_values(by="_sort_datetime", ascending=True, na_position="first")
    deduplicated = df.drop_duplicates(subset=["_phone_key"], keep="last").copy()
    dropped_rows = len(df) - len(deduplicated)
    if dropped_rows:
        logger.info("Se consolidaron %s intentos Logcall repetidos por teléfono", dropped_rows)

    return deduplicated.drop(columns=["_sort_datetime"])


def _extract_normalized_phone_keys(df: pd.DataFrame, column: str) -> set[str]:
    if df.empty or column not in df.columns:
        return set()

    return {key for key in df[column].apply(_normalize_phone_key) if key}


def _read_csv_with_fallback(file_path: Path) -> pd.DataFrame:
    last_error = None
    best_df: pd.DataFrame | None = None
    best_score = -1

    for encoding in ("utf-8", "latin-1"):
        for separator in (",", ";", "\t"):
            try:
                df = pd.read_csv(file_path, encoding=encoding, sep=separator)
            except UnicodeDecodeError as exc:
                last_error = exc
                continue

            if _contains_replacement_character(df):
                continue

            score = _score_csv_parse(df)
            if score > best_score:
                best_df = df
                best_score = score

            if _looks_like_valid_csv_parse(df):
                return df

        if best_df is not None:
            return best_df

    if last_error:
        raise last_error

    if best_df is not None:
        return best_df

    return pd.read_csv(file_path, encoding="latin-1", sep=None, engine="python")


def _looks_like_valid_csv_parse(df: pd.DataFrame) -> bool:
    return _score_csv_parse(df) >= 2


def _score_csv_parse(df: pd.DataFrame) -> int:
    if df.empty and len(df.columns) == 0:
        return 0

    columns = [str(column) for column in df.columns]
    if len(columns) <= 1:
        return 1

    normalized_columns = {_normalize_column_name(column) for column in columns}
    known_columns = {
        "logdate",
        "logtime",
        "phone",
        "result",
        "lengthcall",
        "callrefid",
        "callid",
        "fecha",
        "desde",
        "duracions",
    }

    known_column_hits = len(normalized_columns & known_columns)
    return len(columns) + (known_column_hits * 10)


def _contains_replacement_character(df: pd.DataFrame) -> bool:
    object_columns = [col for col in df.columns if pd.api.types.is_object_dtype(df[col])]
    if not object_columns:
        return False

    for column in object_columns:
        series = df[column].dropna().astype(str)
        if series.str.contains("�", regex=False).any():
            return True

    return False


def _ensure_output_shape(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    for col in OUTPUT_COLUMNS:
        if col not in normalized.columns:
            normalized[col] = ""

    return normalized[OUTPUT_COLUMNS]


def _empty_output_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def _build_datetime_string(logdate_value, logtime_value) -> str:
    if pd.isna(logdate_value) or pd.isna(logtime_value):
        return ""

    try:
        date_str = str(int(float(logdate_value)))
        time_str = f"{int(float(logtime_value)):06d}"
        dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
        return dt.strftime("%d/%m/%Y, %H:%M")
    except (ValueError, TypeError):
        return ""


def _normalize_phone(value) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())

    if not digits:
        return text

    return digits


def _normalize_phone_key(value) -> str:
    digits = _normalize_phone(value)
    if not digits.isdigit():
        return ""

    if digits.startswith("549") and len(digits) >= 12:
        return "54" + digits[3:]

    return digits


def _normalize_roman_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    normalized_lookup: dict[str, str] = {}
    for source_column in normalized.columns:
        key = _normalize_column_name(source_column)
        normalized_lookup.setdefault(key, source_column)

    rename_map: dict[str, str] = {}
    for output_column in OUTPUT_COLUMNS:
        output_key = _normalize_column_name(output_column)
        source_column = normalized_lookup.get(output_key)

        if source_column and source_column != output_column:
            rename_map[source_column] = output_column

    if rename_map:
        normalized = normalized.rename(columns=rename_map)

    _fill_output_columns_from_fallbacks(normalized)

    if "Fecha" in normalized.columns and "Fecha y Hora" not in normalized.columns:
        normalized["Fecha y Hora"] = normalized["Fecha"].apply(_normalize_roman_datetime)

    return normalized


def _fill_output_columns_from_fallbacks(df: pd.DataFrame) -> None:
    normalized_lookup = {
        _normalize_column_name(column): column
        for column in df.columns
    }

    for output_column, fallback_columns in INPUT_COLUMN_FALLBACKS.items():
        values = df[output_column] if output_column in df.columns else pd.Series("", index=df.index)

        for fallback_column in fallback_columns:
            source_column = normalized_lookup.get(_normalize_column_name(fallback_column))
            if source_column is None:
                continue

            values = values.where(~values.apply(_is_missing_value), df[source_column])

        df[output_column] = values


def _normalize_column_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return "".join(ch for ch in normalized if ch.isalnum())


def _normalize_roman_datetime(value) -> str:
    if _is_missing_value(value):
        return ""

    text = str(value).strip()

    for date_format in ("%d/%m/%Y %H:%M", "%d/%m/%Y, %H:%M"):
        try:
            parsed = datetime.strptime(text, date_format)
            return parsed.strftime("%d/%m/%Y, %H:%M")
        except ValueError:
            continue

    return text


def _ensure_sensitive_columns_as_text(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    for column in SENSITIVE_TEXT_COLUMNS:
        if column in normalized.columns:
            normalized[column] = normalized[column].apply(_normalize_identifier)

    return normalized


def _normalize_identifier(value) -> str:
    if _is_missing_value(value):
        return ""

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return format(value, ".15g")

    text = str(value).strip()
    return text


def _normalize_canonical_fields(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    for column in BOOLEAN_OUTPUT_COLUMNS:
        if column in normalized.columns:
            normalized[column] = normalized[column].apply(_normalize_boolean_to_si_no)

    if "[Salida] Motivo No Entrega" in normalized.columns:
        normalized["[Salida] Motivo No Entrega"] = normalized["[Salida] Motivo No Entrega"].apply(
            _normalize_motivo_no_entrega
        )

    if "[Salida] Tipo Contacto" in normalized.columns:
        normalized["[Salida] Tipo Contacto"] = normalized["[Salida] Tipo Contacto"].apply(
            _normalize_tipo_contacto
        )

    if "[Salida] Utilidad Informacion" in normalized.columns:
        normalized["[Salida] Utilidad Informacion"] = normalized[
            "[Salida] Utilidad Informacion"
        ].apply(_normalize_utilidad_informacion)

    return normalized


def _fill_missing_with_dash(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()

    for column in normalized.columns:
        normalized[column] = normalized[column].apply(lambda value: "-" if _is_missing_value(value) else value)

    return normalized


def _normalize_motivo_no_entrega(value) -> str:
    if _is_missing_value(value):
        return "-"

    text = str(value).strip()
    normalized = _normalize_text(text)

    canonical_map = {
        "corta la llamada": "corta la llamada",
        "contestador": "contestador",
        "no era titular": "no era titular",
        "no acepto": "no aceptó",
        "interrupciones": "interrupciones",
        "error tecnico": "error técnico",
        "buzon de voz": "buzón de voz",
        "ocupado": "ocupado",
        "numero errado": "número errado",
        "numero fuera de servicio": "número fuera de servicio",
        "numero internacional": "número internacional",
        "no contesta": "no contesta",
        "mensaje con tercero": "mensaje con tercero",
    }

    if normalized in canonical_map:
        return canonical_map[normalized]

    if "corta la llamada" in normalized:
        return "corta la llamada"
    if "buzon" in normalized:
        return "buzón de voz"
    if "contestador" in normalized or "ivr" in normalized:
        return "contestador"
    if "no era titular" in normalized:
        return "no era titular"
    if "no acept" in normalized or "rechaz" in normalized:
        return "no aceptó"
    if "interrup" in normalized:
        return "interrupciones"
    if "error tecn" in normalized or "tecnico" in normalized or "falla" in normalized:
        return "error técnico"
    if "ocupad" in normalized:
        return "ocupado"
    if "errone" in normalized or "numero errado" in normalized or "equivoc" in normalized:
        return "número errado"
    if "fuera de servicio" in normalized or "sin servicio" in normalized:
        return "número fuera de servicio"
    if "internacional" in normalized:
        return "número internacional"
    if "no contesta" in normalized or "no responde" in normalized:
        return "no contesta"
    if "tercero" in normalized:
        return "mensaje con tercero"

    return "error técnico"


def _normalize_tipo_contacto(value) -> str:
    if _is_missing_value(value):
        return "-"

    normalized = _normalize_text(str(value))

    if normalized == "humano":
        return "Humano"
    if normalized == "contestador" or "contestador" in normalized or "buzon" in normalized:
        return "Contestador"
    if normalized == "ivr" or "ivr" in normalized:
        return "IVR"
    if normalized == "interrumpido" or "interrump" in normalized or "corta" in normalized:
        return "Interrumpido"
    if normalized == "desconocido":
        return "Desconocido"

    return "Desconocido"


def _normalize_utilidad_informacion(value) -> str:
    if _is_missing_value(value):
        return UTILIDAD_INFORMACION_DEFAULT

    return str(value).strip()


def _normalize_boolean_to_si_no(value):
    if _is_missing_value(value):
        return value

    if isinstance(value, bool):
        return "Sí" if value else "No"

    if isinstance(value, (int, float)) and not pd.isna(value):
        if float(value) == 1.0:
            return "Sí"
        if float(value) == 0.0:
            return "No"

    raw_text = str(value).strip().lower()
    normalized = _normalize_text(str(value))

    if raw_text in {"sí", "si", "s", "s�", "sã­"}:
        return "Sí"

    if raw_text in {"no", "n"}:
        return "No"

    if normalized in {"si", "se", "s", "yes", "true", "verdadero", "1", "1.0"}:
        return "Sí"

    if normalized in {"no", "n", "false", "falso", "0", "0.0"}:
        return "No"

    return value


def _is_missing_value(value) -> bool:
    if pd.isna(value):
        return True

    text = str(value).strip()
    return text == ""


def _normalize_text(value: str) -> str:
    text = value.strip().lower()
    text = text.replace("�", "e")
    normalized = unicodedata.normalize("NFKD", text)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("-", " ")
    normalized = " ".join(normalized.split())
    return normalized

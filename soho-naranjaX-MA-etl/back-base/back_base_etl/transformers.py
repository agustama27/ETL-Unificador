"""Transformation and business rules for Naranja X ETL output."""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from .cleaners import (
    clean_email,
    clean_monto,
    clean_telefono,
    extract_dias_mora,
    extract_dni,
    normalize_upper_snake,
    prioritize_emails,
)
from .constants import (
    AMOUNT_INPUT_COLS,
    EMAIL_COLUMNS,
    OUTPUT_COLUMNS,
    OUTPUT_COLUMNS_ROMAN,
    PHONE_COLUMNS,
)
from .validators import is_missing, should_warn_invalid_amount


def _is_null_scalar(value) -> bool:
    """Return True when value is a scalar null-like."""
    result = pd.isna(value)
    if isinstance(result, bool):
        return result
    return False


PLAN_COLUMN_REGEX = re.compile(r"^plan_([1-7])_.+")


def _has_text_or_value(value: object) -> bool:
    if _is_null_scalar(value):
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _is_plan_ok(row: pd.Series, plan_columns: list[str]) -> bool:
    """Return True when at least one plan has entrega and cuota_mensual informed."""
    plan_indexes: set[str] = set()
    for column in plan_columns:
        match = PLAN_COLUMN_REGEX.match(str(column))
        if match:
            plan_indexes.add(match.group(1))

    if not plan_indexes:
        for column in row.index:
            match = PLAN_COLUMN_REGEX.match(str(column))
            if match:
                plan_indexes.add(match.group(1))

    for idx in sorted(plan_indexes):
        entrega_value = row.get(f"plan_{idx}_entrega", "")
        cuota_value = row.get(f"plan_{idx}_cuota_mensual", "")
        if _has_text_or_value(entrega_value) and _has_text_or_value(cuota_value):
            return True
    return False


def transform(
    df: pd.DataFrame,
    plan_columns: list[str] | None = None,
    output_columns_base: list[str] | None = None,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """Transform raw Naranja X dataframe into SOHO output dataframe."""
    active_logger = logger or logging.getLogger("etl_naranjax")
    execution_date_iso = date.today().isoformat()
    plan_columns = plan_columns or []
    is_roman_output = output_columns_base == OUTPUT_COLUMNS_ROMAN
    records = []
    rows_with_warning = 0

    for row_index, (_, row) in enumerate(df.iterrows(), start=2):
        row_has_warning = False
        row_number = row_index

        dni = extract_dni(row.get("dni", ""))
        if not dni:
            active_logger.warning("Row %s: DNI without digits, output as empty", row_number)
            row_has_warning = True

        phones_cleaned = []
        for phone_col in PHONE_COLUMNS:
            raw_phone = row.get(phone_col)
            cleaned_phone = clean_telefono(raw_phone)
            if cleaned_phone == "" and not is_missing(raw_phone):
                active_logger.warning(
                    "Row %s: discarded phone in %s value=%r",
                    row_number,
                    phone_col,
                    raw_phone,
                )
                row_has_warning = True
            phones_cleaned.append(cleaned_phone)

        cleaned_emails = []
        for email_col in EMAIL_COLUMNS:
            raw_email = row.get(email_col)
            cleaned_email = clean_email(raw_email)
            if cleaned_email == "" and not is_missing(raw_email):
                active_logger.warning(
                    "Row %s: invalid email in %s value=%r",
                    row_number,
                    email_col,
                    raw_email,
                )
                row_has_warning = True
            cleaned_emails.append(cleaned_email)

        p_email_1, p_email_2, p_email_3 = prioritize_emails(*cleaned_emails)

        amounts = {}
        for output_col, input_col in AMOUNT_INPUT_COLS.items():
            raw_value = row.get(input_col)
            if is_missing(raw_value):
                active_logger.warning(
                    "Row %s: null amount in %s, defaulted to 0.0",
                    row_number,
                    input_col,
                )
                row_has_warning = True

            parsed_amount = clean_monto(raw_value)
            if should_warn_invalid_amount(raw_value, parsed_amount):
                active_logger.warning(
                    "Row %s: invalid amount format in %s value=%r, defaulted to 0.0",
                    row_number,
                    input_col,
                    raw_value,
                )
                row_has_warning = True

            amounts[output_col] = parsed_amount

        record = {
            "id_nro_dni": dni,
            "customer_name": ""
            if _is_null_scalar(row.get("nombre_apellido"))
            else str(row.get("nombre_apellido")).strip(),
            "tel_1": phones_cleaned[0],
            "tel_2": phones_cleaned[1],
            "tel_3": phones_cleaned[2],
            "tel_4": phones_cleaned[3],
            "txt_email_1": p_email_1,
            "txt_email_2": p_email_2,
            "txt_email_3": p_email_3,
            "id_nro_producto": ""
            if _is_null_scalar(row.get("nroproducto"))
            else str(row.get("nroproducto")).strip(),
            "tipo_ecosistema": ""
            if _is_null_scalar(row.get("ecosistema"))
            else str(row.get("ecosistema")).strip(),
            "tipo_asignacion": normalize_upper_snake(row.get("asignacion")),
            "tipo_plan": normalize_upper_snake(row.get("marca_plan")),
            "tipo_cajon": ""
            if _is_null_scalar(row.get("cajon"))
            else str(row.get("cajon")).strip(),
            "tipo_estrategia": ""
            if _is_null_scalar(row.get("estrategia"))
            else str(row.get("estrategia")).strip(),
            "cnt_dias_mora": extract_dias_mora(row.get("cajon")),
            "fecha_gestion": execution_date_iso,
            "recupero": ""
            if _is_null_scalar(row.get("recupero"))
            else str(row.get("recupero")).strip(),
            "tipo_pago": ""
            if _is_null_scalar(row.get("tipo_pago"))
            else str(row.get("tipo_pago")).strip(),
        }
        for plan_column in plan_columns:
            value = row.get(plan_column, "")
            record[plan_column] = "" if _is_null_scalar(value) else value

        record.update(amounts)
        if is_roman_output:
            roman_record = {
                "nombre_cliente": record["customer_name"],
                "tel_1": record["tel_1"],
                "tel_2": record["tel_2"],
                "tel_3": record["tel_3"],
                "tel_4": record["tel_4"],
                "id_dni": record["id_nro_dni"],
                "id_producto": record["id_nro_producto"],
                "tipo_cajon": record["tipo_cajon"],
                "plan_ok": "si" if _is_plan_ok(row, plan_columns) else "no",
                "monto_deuda_tc": record["monto_deuda_total_tc_ars"],
                "monto_deuda_nd": record["monto_deuda_total_nd_ars"],
                "monto_deuda_total": record["monto_deuda_total_ars"],
                "monto_deuda_vencida_actual": clean_monto(row.get("monto_deuda_vencida_actual", row.get("total_vencida", 0))),
                "fecha_limite_sistema": execution_date_iso,
            }
            for plan_column in plan_columns:
                roman_record[plan_column] = record.get(plan_column, "")
            records.append(roman_record)
        else:
            records.append(record)

        if row_has_warning:
            rows_with_warning += 1

    output_base = output_columns_base if output_columns_base is not None else OUTPUT_COLUMNS
    output_columns = [*output_base, *plan_columns]
    output_df = pd.DataFrame(records, columns=pd.Index(output_columns))
    output_df.attrs["total_rows"] = len(df)
    output_df.attrs["rows_with_warning"] = rows_with_warning
    return output_df


def sort_roman_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return ROMAN dataframe sorted by tel_3, id_dni, id_producto.

    Empty tel_3 values are placed at the end to keep deterministic ordering.
    """
    required_columns = ["tel_3", "id_dni", "id_producto"]
    if any(column not in df.columns for column in required_columns):
        return df

    sortable = df.copy()
    sortable["_sort_tel_3"] = sortable["tel_3"].fillna("").astype(str).str.strip()
    sortable["_sort_id_dni"] = sortable["id_dni"].fillna("").astype(str).str.strip()
    sortable["_sort_id_producto"] = sortable["id_producto"].fillna("").astype(str).str.strip()
    sortable["_sort_tel_3_empty"] = sortable["_sort_tel_3"] == ""

    sorted_df = sortable.sort_values(
        by=["_sort_tel_3_empty", "_sort_tel_3", "_sort_id_dni", "_sort_id_producto"],
        ascending=[True, True, True, True],
        kind="mergesort",
    )
    return sorted_df.drop(columns=["_sort_tel_3", "_sort_id_dni", "_sort_id_producto", "_sort_tel_3_empty"])


def build_e1kia_output(df_roman: pd.DataFrame) -> pd.DataFrame:
    """Build E1KIA export from ROMAN final dataframe."""
    e1kia_columns = ["tel_1", "tel_2", "tel_3"]
    if any(column not in df_roman.columns for column in e1kia_columns):
        return pd.DataFrame(columns=pd.Index(e1kia_columns))

    output = df_roman.loc[:, e1kia_columns].copy()
    for column in e1kia_columns:
        output[column] = output[column].fillna("").astype(str).str.strip()
    return output

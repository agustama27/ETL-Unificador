"""Validation and warning helper checks for ETL data quality."""

from __future__ import annotations

import pandas as pd

from .constants import INPUT_COLUMN_COUNT, INPUT_SHEET_NAME


def validate_input_shape(df: pd.DataFrame) -> None:
    """Validate required input column width for source sheet."""
    if df.shape[1] < INPUT_COLUMN_COUNT:
        raise ValueError(
            f"Expected at least {INPUT_COLUMN_COUNT} columns in sheet "
            f"'{INPUT_SHEET_NAME}', got {df.shape[1]}"
        )


def is_missing(value) -> bool:
    """Return True for null, blank, or #N/A values."""
    if pd.isna(value):
        return True
    text = str(value).strip()
    return text == "" or text.upper() == "#N/A"


def should_warn_invalid_amount(raw_value, parsed_amount: float) -> bool:
    """Return True when amount was non-empty and could not be parsed."""
    if parsed_amount != 0.0 or is_missing(raw_value):
        return False

    raw_text = str(raw_value).strip().replace(",", ".")
    if raw_text in {"0", "0.0", "0.00"}:
        return False

    try:
        float(raw_text)
        return False
    except ValueError:
        return True


def validate_required_columns(df: pd.DataFrame, required_columns: list[str], context: str) -> None:
    """Validate that dataframe contains required columns."""
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        available = ", ".join(str(column) for column in df.columns) or "(none)"
        raise ValueError(
            f"Missing required columns in {context}: {', '.join(sorted(missing))}. "
            f"Available columns: {available}"
        )

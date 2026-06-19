"""Input and output adapters for tipificaciones IA voz PCT ETL."""

from __future__ import annotations

import os
import csv
from datetime import date
from pathlib import Path

import pandas as pd

from .cleaners import normalize_upper_snake
from .constants import (
    COLUMN_ALIASES,
    OUTPUT_DELIMITER,
    OUTPUT_ENCODING,
    OPTIONAL_SOURCE_COLUMNS,
    OUTPUT_COLUMNS,
    OUTPUT_COLUMNS_COUNT,
    OUTPUT_DATE_FORMAT,
    OUTPUT_FILENAME_EXTENSION,
    OUTPUT_FILENAME_PREFIX,
    REQUIRED_SOURCE_COLUMNS,
)
from .validators import validate_required_columns


def _normalize_column_name(column_name: str) -> str:
    return normalize_upper_snake(column_name).lower()


def _load_delimited(filepath: str) -> pd.DataFrame:
    last_error: Exception | None = None
    best_candidate: pd.DataFrame | None = None
    for separator in (",", ";", "\t", None):
        try:
            candidate = pd.read_csv(
                filepath,
                sep=separator,
                engine="python",
                dtype=str,
                keep_default_na=False,
            )
            if len(candidate.columns) > 1:
                return candidate
            if best_candidate is None:
                best_candidate = candidate
        except Exception as error:  # pragma: no cover - covered by explicit failing branch
            last_error = error
    if best_candidate is not None:
        return best_candidate
    raise ValueError(f"Unable to parse delimited input file: {filepath}") from last_error


def _load_raw_input(filepath: str) -> pd.DataFrame:
    extension = Path(filepath).suffix.lower()
    if extension in {".csv", ".txt"}:
        return _load_delimited(filepath)
    if extension in {".xlsx", ".xls"}:
        return pd.read_excel(filepath, dtype=str)
    raise ValueError(f"Unsupported input extension '{extension}' for file: {filepath}")


def _canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    normalized_to_original: dict[str, list[str]] = {}
    for column in df.columns:
        normalized = _normalize_column_name(str(column))
        if not normalized:
            continue
        normalized_to_original.setdefault(normalized, []).append(str(column))

    selected_originals: dict[str, list[str]] = {}
    missing_required: list[str] = []
    required_and_optional = REQUIRED_SOURCE_COLUMNS + OPTIONAL_SOURCE_COLUMNS
    for canonical_name in required_and_optional:
        aliases = COLUMN_ALIASES.get(canonical_name, {canonical_name})
        matched_originals: list[str] = []
        for alias in aliases:
            if alias in df.columns and alias not in matched_originals:
                matched_originals.append(alias)
            normalized_alias = _normalize_column_name(alias)
            for original_name in normalized_to_original.get(normalized_alias, []):
                if original_name not in matched_originals:
                    matched_originals.append(original_name)
        if not matched_originals and canonical_name in REQUIRED_SOURCE_COLUMNS:
            missing_required.append(canonical_name)
            continue
        if matched_originals:
            selected_originals[canonical_name] = matched_originals

    if missing_required:
        available = ", ".join(str(col) for col in df.columns)
        raise ValueError(
            "Missing required source columns: "
            f"{', '.join(missing_required)}. Available columns: {available}"
        )

    output = pd.DataFrame()
    for canonical_name in required_and_optional:
        original_names = selected_originals.get(canonical_name)
        if not original_names:
            output[canonical_name] = ""
            continue
        column = df[original_names[0]]
        for extra_name in original_names[1:]:
            column = column.where(column != "", df[extra_name])
        output[canonical_name] = column
    return output


def load_input(filepath: str) -> pd.DataFrame:
    """Load source input and enforce required schema."""
    try:
        raw_df = _load_raw_input(filepath)
    except Exception as error:
        raise ValueError(f"Failed to read input file '{filepath}': {error}") from error

    if raw_df.empty and not list(raw_df.columns):
        raise ValueError(f"Input file '{filepath}' is empty or unreadable")

    canonical_df = _canonicalize_columns(raw_df)
    validate_required_columns(list(canonical_df.columns))
    return canonical_df


def save_output(df: pd.DataFrame, output_dir: str) -> str:
    """Persist output in strict PCT csv contract."""
    os.makedirs(output_dir, exist_ok=True)
    filename = (
        f"{OUTPUT_FILENAME_PREFIX}{date.today().strftime('%Y%m%d')}"
        f"{OUTPUT_FILENAME_EXTENSION}"
    )
    output_path = os.path.join(output_dir, filename)

    output_df = df.reindex(columns=OUTPUT_COLUMNS)
    output_df.to_csv(
        output_path,
        sep=OUTPUT_DELIMITER,
        header=True,
        index=False,
        encoding=OUTPUT_ENCODING,
        lineterminator="\n",
        quoting=csv.QUOTE_NONE,
        escapechar="\\",
    )
    output_df.attrs["output_contract"] = {
        "delimiter": OUTPUT_DELIMITER,
        "encoding": OUTPUT_ENCODING,
        "columns": OUTPUT_COLUMNS_COUNT,
        "date_format": OUTPUT_DATE_FORMAT,
    }
    return output_path

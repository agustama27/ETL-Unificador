"""Normalization and formatting helpers for tipificaciones ETL."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

import pandas as pd

from .constants import OBSERVACIONES_MAX_CHARS


def to_clean_str(value) -> str:
    """Return stripped text or empty string for null-like values."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.upper() == "#N/A" else text


def to_input_str_preserve(value) -> str:
    """Return original text representation without trimming."""
    if pd.isna(value):
        return ""
    return str(value)


def normalize_upper_snake(value) -> str:
    """Normalize any text to uppercase snake-like key."""
    text = to_clean_str(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    text = text.strip("_")
    return text.upper()


def normalize_result_key(value) -> str:
    """Normalize resultado_agente values for dictionary lookups."""
    return normalize_upper_snake(value)


def format_fecha_compromiso(value: str) -> str:
    """Convert DD/MM/YY into YYYYMMDD. Return empty string if invalid."""
    clean_value = to_clean_str(value)
    if not clean_value:
        return ""
    try:
        return datetime.strptime(clean_value, "%d/%m/%y").strftime("%Y%m%d")
    except ValueError:
        return ""


def truncate_observaciones(value: str, max_chars: int = OBSERVACIONES_MAX_CHARS) -> str:
    """Sanitize and truncate observations without splitting words when possible."""
    text = to_clean_str(value)
    text = text.replace("\"\"", " ").replace("|", " ").replace("\\", " ")
    if len(text) <= max_chars:
        return text

    chunk = text[:max_chars]
    last_space = chunk.rfind(" ")
    if last_space <= 0:
        return chunk
    return chunk[:last_space].rstrip()


def resolve_fecha_promesa(fecha_tc: str, fecha_nd: str) -> str:
    """Choose TC date first, then ND date, else empty."""
    clean_tc = to_clean_str(fecha_tc)
    clean_nd = to_clean_str(fecha_nd)
    if clean_tc:
        return clean_tc
    if clean_nd:
        return clean_nd
    return ""

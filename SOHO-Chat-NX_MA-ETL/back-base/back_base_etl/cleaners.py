"""Cleaning helpers for phones, emails, ids, and textual normalization."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

from .constants import (
    PHONE_LANDLINE_LENGTH,
    PHONE_LANDLINE_PREFIX,
    PHONE_MOBILE_LENGTH,
    PHONE_MOBILE_PREFIX,
)


def clean_telefono(valor) -> str:
    """Clean phone value and keep only valid numbers with expected prefixes/lengths."""
    if pd.isna(valor):
        return ""

    if isinstance(valor, float):
        if pd.isna(valor):
            return ""
        texto = str(int(valor)) if valor.is_integer() else str(valor).strip()
    elif isinstance(valor, int):
        texto = str(valor)
    else:
        texto = str(valor).strip()

    if not texto or texto.upper() == "#N/A":
        return ""

    if re.fullmatch(r"\d+\.0+", texto):
        texto = texto.split(".", 1)[0]

    digitos = re.sub(r"\D", "", texto)
    if digitos.startswith(PHONE_MOBILE_PREFIX):
        return digitos if len(digitos) == PHONE_MOBILE_LENGTH else ""
    if digitos.startswith(PHONE_LANDLINE_PREFIX):
        return digitos if len(digitos) == PHONE_LANDLINE_LENGTH else ""
    return ""


def clean_monto(valor) -> float:
    """Parse amounts robustly handling comma/dot decimal separators."""
    if pd.isna(valor):
        return 0.0

    if isinstance(valor, (int, float)):
        return round(float(valor), 2)

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = texto.replace("$", "").replace(" ", "")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return round(float(texto), 2)
    except ValueError:
        return 0.0


def clean_email(valor) -> str:
    """Clean email by stripping and lowercasing; invalid values return empty."""
    if pd.isna(valor):
        return ""

    texto = str(valor).strip().lower()
    if not texto:
        return ""
    if "@" not in texto:
        return ""
    return texto


def extract_dni(valor) -> str:
    """Preserve DNI text representation from source input."""
    if pd.isna(valor):
        return ""
    if isinstance(valor, float):
        if valor.is_integer():
            return str(int(valor))
        return str(valor)
    if isinstance(valor, int):
        return str(valor)
    return str(valor)


def extract_dias_mora(cajon) -> int:
    """Extract days in arrears from CAJON text (example M90 -> 90)."""
    if pd.isna(cajon):
        return 0
    match = re.search(r"(\d+)", str(cajon))
    return int(match.group(1)) if match else 0


def prioritize_emails(e1, e2, e3) -> tuple[str, str, str]:
    """Prioritize duplicated emails first, then unique ones by appearance order."""
    values = [e1, e2, e3]
    non_empty = [v for v in values if v]

    duplicated_unique: list[str] = []
    for value in non_empty:
        if non_empty.count(value) > 1 and value not in duplicated_unique:
            duplicated_unique.append(value)

    non_duplicated: list[str] = []
    for value in non_empty:
        if non_empty.count(value) == 1:
            non_duplicated.append(value)

    prioritized = (duplicated_unique + non_duplicated)[:3]
    prioritized.extend([""] * (3 - len(prioritized)))
    return prioritized[0], prioritized[1], prioritized[2]


def normalize_upper_snake(value) -> str:
    """Normalize free text to uppercase snake case."""
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    text = text.strip("_")
    return text.upper()

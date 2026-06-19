from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from math import isnan


def _is_na(value: object) -> bool:
    if isinstance(value, float):
        try:
            if isnan(value):
                return True
        except ValueError:
            pass
    return str(value).strip().upper() == "#N/A"


def to_clean_str(value: object) -> str:
    if value is None:
        return ""
    if _is_na(value):
        return ""
    return str(value).strip()


def to_input_str_preserve(value: object) -> str:
    if value is None:
        return ""
    if _is_na(value):
        return ""
    return str(value)


def normalize_upper_snake(value: object) -> str:
    text = unicodedata.normalize("NFD", to_clean_str(value))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return text.strip("_").upper()


def format_fecha_compromiso(value: object) -> str:
    raw = to_clean_str(value)
    if not raw:
        return ""
    try:
        return datetime.strptime(raw, "%d/%m/%y").strftime("%Y%m%d")
    except ValueError:
        return ""


def resolve_fecha_promesa(fecha_tc: object, fecha_nd: object) -> str:
    tc = to_clean_str(fecha_tc)
    if tc:
        return tc
    nd = to_clean_str(fecha_nd)
    if nd:
        return nd
    return ""


def truncate_observaciones(text: object, max_chars: int = 1500) -> str:
    clean = to_clean_str(text).replace('""', " ").replace("|", " ").replace("\\", " ")
    if len(clean) <= max_chars:
        return clean
    chunk = clean[:max_chars]
    idx = chunk.rfind(" ")
    if idx == -1:
        return chunk
    return chunk[:idx]

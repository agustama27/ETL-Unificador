from __future__ import annotations

import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from .constants import (
    COLUMN_ALIASES,
    OPTIONAL_SOURCE_COLUMNS,
    OUTPUT_COLUMNS,
    OUTPUT_FILENAME_EXTENSION,
    OUTPUT_FILENAME_PREFIX,
    REQUIRED_SOURCE_COLUMNS,
    USUOLOS_OUTPUT_COLS,
)
from .validators import validate_required_columns


def _normalize_alias(value: str) -> str:
    text = unicodedata.normalize("NFD", value)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return text.strip("_").upper()


def _load_delimited(path: Path) -> list[dict[str, str]]:
    sample = path.read_text(encoding="utf-8", errors="replace")
    delimiters = [",", ";", "\t", None]
    for delimiter in delimiters:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            if delimiter is None:
                try:
                    dialect = csv.Sniffer().sniff(sample[:4096])
                except csv.Error:
                    continue
            else:
                dialect = type(
                    "_Dialect",
                    (csv.excel,),
                    {
                        "delimiter": delimiter,
                    },
                )

            reader = csv.DictReader(fh, dialect=dialect)
            rows = [dict(row) for row in reader]
            if reader.fieldnames and len(reader.fieldnames) > 1:
                return rows
    raise ValueError(f"Failed to read input file: {path}")


def _coalesce(values: list[str]) -> str:
    for value in values:
        if str(value).strip() != "":
            return str(value)
    return ""


def _canonicalize_rows(raw_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not raw_rows:
        validate_required_columns([], REQUIRED_SOURCE_COLUMNS)

    input_columns: list[str] = list(raw_rows[0].keys()) if raw_rows else []
    by_normalized: dict[str, list[str]] = {}
    for col in input_columns:
        by_normalized.setdefault(_normalize_alias(str(col)), []).append(col)

    canonical_map: dict[str, list[str]] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        found: list[str] = []
        for alias in aliases:
            found.extend(by_normalized.get(_normalize_alias(alias), []))
        if found:
            dedup = list(dict.fromkeys(found))
            canonical_map[canonical] = dedup

    validate_required_columns(list(canonical_map.keys()), REQUIRED_SOURCE_COLUMNS)

    all_columns = REQUIRED_SOURCE_COLUMNS + OPTIONAL_SOURCE_COLUMNS
    canonical_rows: list[dict[str, str]] = []
    for row in raw_rows:
        mapped: dict[str, str] = {}
        for canonical in all_columns:
            source_cols = canonical_map.get(canonical, [])
            if source_cols:
                mapped[canonical] = _coalesce([str(row.get(src, "")) for src in source_cols])
            else:
                mapped[canonical] = ""
        canonical_rows.append(mapped)
    return canonical_rows


def load_input(filepath: str | Path) -> list[dict[str, str]]:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in (".csv", ".txt"):
        return _canonicalize_rows(_load_delimited(path))
    if suffix in (".xlsx", ".xls"):
        raise ValueError("Unsupported input extension without pandas/openpyxl runtime")
    raise ValueError(f"Unsupported input extension: {suffix}")


def save_output(rows: list[dict[str, str]], output_dir: str | Path) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{OUTPUT_FILENAME_PREFIX}{datetime.now():%Y%m%d}{OUTPUT_FILENAME_EXTENSION}"
    output_path = out_dir / filename

    run_ts = datetime.now().strftime("%Y%m%d%H%M%S")

    event_map = {
        "12": "PROMISE",
        "47": "PAYMENT DIFFICULTY",
        "37": "PAID",
        "7": "NO ANSWER",
        "28": "MESSAGE",
        "29": "HANGUP",
        "8": "CONTACTO",
        "15": "NOT RECOGNIZED DEBT",
        "16": "DECEASED",
        "17": "NO WILLINGNESS TO PAY",
        "26": "NO ANSWER",
        "61": "WRONG HOLDER",
    }

    with output_path.open("w", encoding="cp1252", newline="") as fh:
        writer = csv.writer(
            fh,
            delimiter="|",
            lineterminator="\n",
            quoting=csv.QUOTE_NONE,
            escapechar="\\",
        )
        for row in rows:
            cols = ["" for _ in range(USUOLOS_OUTPUT_COLS)]
            cols[0] = run_ts
            cols[1] = row.get("DNI", "")
            cols[2] = "NARANJA"
            cols[7] = "USUEVOLTIS"
            cols[8] = "N"
            cols[9] = "MAKE CALL"
            cols[10] = event_map.get(row.get("TIPIFICACION", ""), row.get("TIPIFICACION", ""))
            cols[11] = "VOICEBOT"
            cols[27] = row.get("MONTO_PROMESA", "")
            cols[28] = f"{row.get('FECHA_PROMESA', '')}000000" if row.get("FECHA_PROMESA", "") else ""
            cols[30] = "N"
            cols[35] = "EVOLTIS"
            cols[36] = "1"
            cols[38] = "PENDING"
            cols[39] = run_ts
            writer.writerow(cols)

    return output_path

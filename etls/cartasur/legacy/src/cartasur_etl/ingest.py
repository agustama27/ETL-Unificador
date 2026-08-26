from __future__ import annotations

from pathlib import Path

import pandas as pd


class IngestError(ValueError):
    """Raised when input ingest cannot continue."""


def read_input(path: str | Path, config: dict) -> pd.DataFrame:
    input_path = Path(path)
    if not input_path.exists():
        raise IngestError(f"Input file not found: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        df = _read_csv(input_path)
    elif suffix in {".xlsx", ".xlsm"}:
        df = pd.read_excel(input_path, dtype=str, keep_default_na=False, engine="openpyxl")
    else:
        raise IngestError(f"Unsupported input format: {input_path.suffix}. Use .xlsx or .csv")

    columns = config["columns"]
    missing_raw = [raw for raw in columns.values() if raw not in df.columns]
    if missing_raw:
        raise IngestError(f"Missing required columns: {', '.join(missing_raw)}")

    internal = df[list(columns.values())].rename(columns={raw: key for key, raw in columns.items()})
    for col in internal.columns:
        internal[col] = internal[col].map(_clean_cell)
    internal["source_row_number"] = range(2, len(internal) + 2)
    internal["row_type"] = internal.apply(classify_row, axis=1)
    return internal


def read_workbook(path: str | Path, config: dict) -> pd.DataFrame:
    return read_input(path, config)


def _read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise IngestError(f"Could not decode CSV input as UTF-8 or cp1252: {path}")


def classify_row(row: pd.Series) -> str:
    has_loan = bool(row.get("id_producto")) and bool(row.get("nro_cuota")) and bool(row.get("saldo_exigible"))
    has_insurance = bool(row.get("seguro_descripcion")) and bool(row.get("importe_seguro"))
    if has_loan and not has_insurance:
        return "LOAN"
    if has_insurance and not has_loan:
        return "INSURANCE"
    if has_loan:
        return "LOAN"
    if has_insurance:
        return "INSURANCE"
    return "UNKNOWN"


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text

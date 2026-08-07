from __future__ import annotations

import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import OrderedDict


BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR / "base_recibida"
OUTPUT_DIR = BASE_DIR / "base_generada"
DEFAULT_COUNTRY_CODE = "54"
# Salida siempre en UTF-8 (sin BOM), legible y estándar para intercambio.
OUTPUT_ENCODING = "utf-8"


def _find_input_csv(input_dir: Path) -> Path:
    csv_files = list(input_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No se encontro ningun CSV en: {input_dir}")
    return max(csv_files, key=lambda p: p.stat().st_mtime)


def _detect_delimiter(csv_path: Path) -> str:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        return dialect.delimiter
    except csv.Error:
        return ";"


def _normalize_phone_e164(phone: str, default_country_code: str = DEFAULT_COUNTRY_CODE) -> str:
    raw = (phone or "").strip()
    if not raw:
        return ""

    # Conservamos solo + y digitos; luego armamos un formato E.164.
    cleaned = re.sub(r"[^\d+]", "", raw)
    if not cleaned:
        return ""

    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"

    if cleaned.startswith("+"):
        digits = re.sub(r"\D", "", cleaned[1:])
        return f"+{digits}" if digits else ""

    digits = re.sub(r"\D", "", cleaned)
    if not digits:
        return ""

    # Si ya trae codigo de pais (ej. 54...), solo agregamos el +.
    if digits.startswith(default_country_code):
        return f"+{digits}"

    # Si viene con prefijo local, quitamos ceros iniciales y aplicamos pais por defecto.
    digits = digits.lstrip("0")
    if not digits:
        return ""

    return f"+{default_country_code}{digits}"


def _build_output_path(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    return output_dir / f"SOCIAL_ARG_CARTERA_{date_str}.csv"


def _normalize_key(value: str) -> str:
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _find_column_name(fieldnames: list[str], candidates: list[str]) -> str:
    normalized_map = {_normalize_key(field): field for field in fieldnames}
    for candidate in candidates:
        match = normalized_map.get(_normalize_key(candidate))
        if match:
            return match
    raise KeyError(f"No se encontro la columna esperada. Candidatas: {candidates}")


def _to_snake_case(value: str) -> str:
    text = (value or "").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    if not text:
        return "col"
    if text[0].isdigit():
        text = f"col_{text}"
    return text


def _parse_amount(raw_value: str) -> float:
    raw = (raw_value or "").strip()
    if not raw:
        return 0.0
    # Tomamos solo signo y digitos; los montos fuente no tienen decimales confiables.
    normalized = re.sub(r"[^\d-]", "", raw)
    if not normalized or normalized == "-":
        return 0.0
    return float(normalized)


def _parse_percentage(raw_value: str) -> float:
    raw = (raw_value or "").strip()
    if not raw:
        return 0.0
    normalized = raw.replace("%", "").replace(",", ".").strip()
    normalized = re.sub(r"[^0-9.\-]", "", normalized)
    if not normalized or normalized == "-":
        return 0.0
    return float(normalized)


def _parse_int(raw_value: str) -> int:
    raw = (raw_value or "").strip()
    if not raw:
        return 0
    normalized = re.sub(r"[^\d-]", "", raw)
    if not normalized or normalized == "-":
        return 0
    return int(normalized)


def _sanitize_cell(value: object) -> str:
    """Evita bytes nulos y normaliza a str; el módulo csv escapa comillas y delimitadores."""
    if value is None:
        return ""
    text = str(value).replace("\x00", "")
    return text


def _validate_output_csv(path: Path, delimiter: str, expected_data_rows: int) -> None:
    """
    Re-lee el archivo con el mismo delimitador y comprueba que el parseo sea coherente
    (mismo número de columnas en todas las filas). Así se detectan líneas rotas por
    comillas o delimitadores mal cerrados.
    """
    with path.open("r", encoding=OUTPUT_ENCODING, newline="") as handle:
        reader = csv.reader(
            handle,
            delimiter=delimiter,
            quoting=csv.QUOTE_MINIMAL,
            doublequote=True,
        )
        rows = list(reader)
    if not rows:
        raise ValueError(f"CSV de salida vacio: {path}")
    header_len = len(rows[0])
    for idx, row in enumerate(rows[1:], start=2):
        if len(row) != header_len:
            raise ValueError(
                f"CSV invalido en {path}: fila {idx} tiene {len(row)} columnas, "
                f"se esperaban {header_len} (revisar comillas o separadores dentro de campos)."
            )
    data_rows = len(rows) - 1
    if data_rows != expected_data_rows:
        raise ValueError(
            f"CSV de salida inconsistente en {path}: {data_rows} filas de datos, "
            f"se esperaban {expected_data_rows}."
        )


def generate_base(input_path: Optional[Path] = None, output_path: Optional[Path] = None) -> Path:
    input_csv = input_path or _find_input_csv(INPUT_DIR)
    output_csv = output_path or _build_output_path(OUTPUT_DIR)
    delimiter = _detect_delimiter(input_csv)

    with input_csv.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError(f"El archivo no tiene cabeceras: {input_csv}")

        source_fieldnames = reader.fieldnames
        apellido_column = _find_column_name(source_fieldnames, ["APELLIDO"])
        nombre_column = _find_column_name(source_fieldnames, ["NOMBRE"])
        documento_column = _find_column_name(source_fieldnames, ["DOCUMENTO"])
        monto_cuota_column = _find_column_name(source_fieldnames, ["Monto Cuota", "MONTO"])
        monto_column = _find_column_name(source_fieldnames, ["MONTO"])
        descuento_column = _find_column_name(source_fieldnames, ["% Descuento", "PORCENTAJE_BECA"])
        dias_mora_column = _find_column_name(source_fieldnames, ["Dias Mora", "DIAS_VENCIDO"])

        fieldnames: list[str] = []
        for field in source_fieldnames:
            if field == apellido_column:
                fieldnames.append("customer_name")
                continue
            if field == nombre_column:
                continue
            if field == monto_cuota_column and monto_cuota_column != monto_column:
                continue
            fieldnames.append(field)

        for extra_field in ["monto_deuda", "cantidad_cuotas", "monto_deuda_descuento"]:
            if extra_field not in fieldnames:
                fieldnames.append(extra_field)

        output_fieldnames = [_to_snake_case(name) for name in fieldnames]
        header_map = dict(zip(fieldnames, output_fieldnames))

        grouped_rows: "OrderedDict[str, dict]" = OrderedDict()
        for row in reader:
            documento = (row.get(documento_column) or "").strip()
            if not documento:
                continue

            nombre = (row.get(nombre_column) or "").strip()
            apellido = (row.get(apellido_column) or "").strip()
            row["customer_name"] = " ".join(part for part in [nombre, apellido] if part)
            row["CELULAR"] = _normalize_phone_e164(row.get("CELULAR", ""))

            monto_cuota = _parse_amount(row.get(monto_cuota_column, ""))
            descuento = _parse_percentage(row.get(descuento_column, ""))

            if documento not in grouped_rows:
                grouped_rows[documento] = {
                    "row": row,
                    "monto_deuda": 0.0,
                    "cantidad_cuotas": 0,
                    "descuento": descuento,
                    "dias_mora_max": _parse_int(row.get(dias_mora_column, "")),
                }

            grouped_rows[documento]["monto_deuda"] += monto_cuota
            grouped_rows[documento]["cantidad_cuotas"] += 1
            grouped_rows[documento]["dias_mora_max"] = max(
                grouped_rows[documento]["dias_mora_max"],
                _parse_int(row.get(dias_mora_column, "")),
            )

            # Si en filas posteriores hay un descuento informado distinto de vacio, lo usamos.
            if descuento > 0:
                grouped_rows[documento]["descuento"] = descuento

        with output_csv.open("w", encoding=OUTPUT_ENCODING, newline="") as target_file:
            writer = csv.DictWriter(
                target_file,
                fieldnames=output_fieldnames,
                delimiter=delimiter,
                quoting=csv.QUOTE_MINIMAL,
                doublequote=True,
                escapechar=None,
                extrasaction="ignore",
            )
            writer.writeheader()

            for group in grouped_rows.values():
                row = group["row"]
                monto_deuda = group["monto_deuda"]
                descuento = group["descuento"]
                monto_deuda_descuento = monto_deuda * (1 - (descuento / 100))

                row["monto_deuda"] = f"{monto_deuda:.2f}"
                row["cantidad_cuotas"] = str(group["cantidad_cuotas"])
                row["monto_deuda_descuento"] = f"{monto_deuda_descuento:.2f}"
                row[dias_mora_column] = str(group["dias_mora_max"])
                sanitized = {key: _sanitize_cell(row.get(key)) for key in fieldnames}
                if monto_column in fieldnames:
                    sanitized[monto_column] = f"{_parse_amount(row.get(monto_column, '')):.2f}"
                output_row = {header_map[key]: sanitized.get(key, "") for key in fieldnames}
                writer.writerow(output_row)

        _validate_output_csv(output_csv, delimiter, len(grouped_rows))

    return output_csv


if __name__ == "__main__":
    generated_file = generate_base()
    print(f"Archivo generado: {generated_file}")

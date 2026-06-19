"""Validador de calidad para archivos LOGCALL."""

from __future__ import annotations

import csv
import re
from pathlib import Path


REQUIRED_COLUMNS = ("LOGDATE", "LOGTIME", "PHONE", "RESULT", "ACTIGROUP", "CALLREFID")


def detect_delimiter(path: Path) -> str:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        sample = handle.read(4096)
    for delimiter in (";", ",", "|"):
        if delimiter in sample:
            return delimiter
    return ";"


def _is_scientific(phone: str) -> bool:
    return bool(re.search(r"[eE]", (phone or "").strip()))


def _digits(phone: str) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def validar_logcall(path: Path, max_scientific_ratio: float = 0.05) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, [f"ERROR: no existe el archivo: {path}"]

    delimiter = detect_delimiter(path)
    messages: list[str] = [f"Archivo: {path}", f"Delimitador detectado: '{delimiter}'"]

    total_rows = 0
    scientific_phone = 0
    empty_phone = 0
    empty_callrefid = 0
    bad_actigroup = 0

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        header = reader.fieldnames or []

        missing = [col for col in REQUIRED_COLUMNS if col not in header]
        if missing:
            return False, messages + [f"ERROR: faltan columnas obligatorias: {', '.join(missing)}"]

        for row in reader:
            total_rows += 1

            phone = (row.get("PHONE") or "").strip()
            if not phone:
                empty_phone += 1
            elif _is_scientific(phone):
                scientific_phone += 1

            if not (row.get("CALLREFID") or "").strip():
                empty_callrefid += 1

            if (row.get("ACTIGROUP") or "").strip() != "M":
                bad_actigroup += 1

    if total_rows == 0:
        return False, messages + ["ERROR: el archivo no tiene filas de datos."]

    sci_ratio = scientific_phone / total_rows
    ok = True

    messages.extend(
        [
            f"Filas totales: {total_rows}",
            f"PHONE vacio: {empty_phone}",
            f"PHONE cientifico: {scientific_phone} ({sci_ratio:.2%})",
            f"CALLREFID vacio: {empty_callrefid}",
            f"ACTIGROUP != 'M': {bad_actigroup}",
            f"Umbral PHONE cientifico: {max_scientific_ratio:.2%}",
        ]
    )

    if sci_ratio > max_scientific_ratio:
        ok = False
        messages.append("ERROR: PHONE en notacion cientifica supera el umbral.")

    if empty_callrefid > 0:
        ok = False
        messages.append("ERROR: hay filas con CALLREFID vacio.")

    if empty_phone > 0:
        ok = False
        messages.append("ERROR: hay filas con PHONE vacio.")

    if ok:
        messages.append("OK: LOGCALL apto para procesar.")

    return ok, messages


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Validador de calidad para LOGCALL")
    parser.add_argument("archivo", type=Path, help="Ruta al archivo LOGCALL")
    parser.add_argument(
        "--max-scientific-ratio",
        type=float,
        default=0.05,
        help="Umbral maximo (0..1) permitido para PHONE en notacion cientifica",
    )
    args = parser.parse_args()

    ok, messages = validar_logcall(args.archivo, args.max_scientific_ratio)
    for line in messages:
        print(line)

    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

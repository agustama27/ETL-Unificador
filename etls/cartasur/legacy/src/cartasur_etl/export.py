from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from cartasur_etl.validate import Issue, REPORT_COLUMNS


def output_filename(run_date: date) -> str:
    return f"CARTA_SUR_ROMAN_{run_date:%y%m%d}.csv"


def e1kia_output_filename(run_date: date) -> str:
    return f"CARTA_SUR_E1KIA_{run_date:%y%m%d}.csv"


def write_outputs(records: list[dict], issues: list[Issue], output_dir: str | Path, config: dict, run_date: date) -> dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / output_filename(run_date)
    e1kia_csv_path = out / e1kia_output_filename(run_date)
    report_csv_path = out / "validation_report.csv"
    report_json_path = out / "validation_report.json"
    write_dynamic_csv(records, csv_path, config["output_columns"])
    write_e1kia_phone_csv(records, e1kia_csv_path)
    write_validation_report(issues, report_csv_path, report_json_path)
    return {"csv": csv_path, "e1kia_csv": e1kia_csv_path, "validation_report_csv": report_csv_path, "validation_report_json": report_json_path}


def write_dynamic_csv(records: list[dict], path: str | Path, output_columns: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=output_columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column, "") for column in output_columns})


def write_e1kia_phone_csv(records: list[dict], path: str | Path) -> None:
    fixed, cellular = collect_e1kia_phones(records)
    rows = max(len(fixed), len(cellular))
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["tel_fijo", "tel_celular"], delimiter=";", lineterminator="\n")
        writer.writeheader()
        for index in range(rows):
            writer.writerow(
                {
                    "tel_fijo": fixed[index] if index < len(fixed) else "",
                    "tel_celular": cellular[index] if index < len(cellular) else "",
                }
            )


def collect_e1kia_phones(records: list[dict]) -> tuple[list[str], list[str]]:
    fixed_by_base: dict[str, str] = {}
    cellular_by_base: dict[str, str] = {}

    for record in records:
        for field in ("tel_fijo", "telefono_fijo"):
            _add_e1kia_phone(record.get(field), "fixed", fixed_by_base, cellular_by_base)
        for field in ("tel_celular", "telefono_celular"):
            _add_e1kia_phone(record.get(field), "cellular", fixed_by_base, cellular_by_base)
        _add_e1kia_phone(record.get("tel_cliente"), "inferred", fixed_by_base, cellular_by_base)

    for base in cellular_by_base:
        fixed_by_base.pop(base, None)
    return list(fixed_by_base.values()), list(cellular_by_base.values())


def _add_e1kia_phone(value: object, kind: str, fixed_by_base: dict[str, str], cellular_by_base: dict[str, str]) -> None:
    digits = "".join(char for char in str(value or "") if char.isdigit())
    if not _is_valid_e1kia_phone(digits):
        return

    base = _phone_equivalence_key(digits)
    if kind == "cellular" or digits.startswith("549"):
        cellular_by_base.setdefault(base, _with_prefix(base, "549"))
    elif kind == "fixed" or digits.startswith("54") or base not in cellular_by_base:
        fixed_by_base.setdefault(base, _with_prefix(base, "54"))


def _is_valid_e1kia_phone(digits: str) -> bool:
    return bool(digits) and len(digits) > 3 and any(char != "0" for char in digits)


def _phone_equivalence_key(digits: str) -> str:
    if digits.startswith("549"):
        return digits[3:]
    if digits.startswith("54"):
        return digits[2:]
    return digits.lstrip("0")


def _with_prefix(base: str, prefix: str) -> str:
    return f"{prefix}{base.lstrip('0')}"


def write_validation_report(issues: list[Issue], csv_path: str | Path, json_path: str | Path) -> None:
    rows = [issue.to_dict() for issue in issues]
    with Path(csv_path).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with Path(json_path).open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

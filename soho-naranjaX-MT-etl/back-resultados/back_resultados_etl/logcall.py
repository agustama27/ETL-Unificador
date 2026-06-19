from __future__ import annotations

import csv
from pathlib import Path

from .cleaners import to_clean_str


def _first_present(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = to_clean_str(row.get(key, ""))
        if value:
            return value
    return ""


def _clean_phone(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if digits.startswith("549"):
        return digits[3:]
    if digits.startswith("54"):
        return digits[2:]
    return digits


def build_logcall_input(logcall_path: str | Path, cruce_path: str | Path | None = None) -> list[dict[str, str]]:
    path = Path(logcall_path)
    if not path.exists():
        raise FileNotFoundError(f"LOGCALL file not found: {path}")

    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = [h or "" for h in (reader.fieldnames or [])]
        if not any(h in headers for h in ["CALLREFID", "CALL_REFID", "callrefid", "call_refid"]):
            raise ValueError("Missing required LOGCALL column: CALLREFID")

        rows: list[dict[str, str]] = []
        for row in reader:
            call_refid = _first_present(row, ["CALLREFID", "CALL_REFID", "callrefid", "call_refid"])
            if not call_refid:
                continue
            phone = _first_present(row, ["PHONE", "phone", "msisdn", "user_number"])
            phone_norm = _clean_phone(phone)
            rows.append(
                {
                    "call_id": call_refid,
                    "call_refid": call_refid,
                    "id_cliente": "",
                    "phone_norm": phone_norm,
                    "tipificaciones": "LOGCALL",
                    "observaciones": "Cliente no responde. Intento de contacto sin exito.",
                    "fecha_compromiso_tc": "",
                    "fecha_compromiso_nd": "",
                    "monto_compromiso": "",
                    "id_nro_producto": "",
                }
            )

    if cruce_path is None:
        for row in rows:
            if not row.get("id_cliente"):
                row["id_cliente"] = row.get("phone_norm", "")
            row.pop("phone_norm", None)
        return rows

    cruce_file = Path(cruce_path)
    if not cruce_file.exists():
        raise FileNotFoundError(f"Cruce file not found: {cruce_file}")

    with cruce_file.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        cruce_reader = csv.DictReader(fh)
        cruce_rows = [dict(r) for r in cruce_reader]

    by_callref: dict[str, dict[str, str]] = {}
    by_phone: dict[str, dict[str, str]] = {}
    for cruce in cruce_rows:
        call_refid = _first_present(cruce, ["call_refid", "CALL_REFID", "CALLREFID", "call_id", "Call ID"])
        id_cliente = _first_present(cruce, ["id_cliente", "id_dni", "customer_id", "user_number", "msisdn"])
        id_nro_producto = _first_present(cruce, ["id_nro_producto", "id_producto", "nro_producto", "NROPRODUCTO"])
        phone_norm = _clean_phone(_first_present(cruce, ["phone", "PHONE", "msisdn", "user_number"]))

        payload = {
            "id_cliente": id_cliente,
            "id_nro_producto": id_nro_producto,
        }
        if call_refid and call_refid not in by_callref:
            by_callref[call_refid] = payload
        if phone_norm and phone_norm not in by_phone:
            by_phone[phone_norm] = payload

    for row in rows:
        ref = by_callref.get(row.get("call_refid", ""))
        if ref:
            row["id_cliente"] = ref.get("id_cliente", "")
            row["id_nro_producto"] = ref.get("id_nro_producto", "")

    for row in rows:
        if row.get("id_cliente"):
            continue
        phone_norm = row.get("phone_norm", "")
        ref = by_phone.get(phone_norm)
        if ref:
            row["id_cliente"] = ref.get("id_cliente", "")
            if not row.get("id_nro_producto"):
                row["id_nro_producto"] = ref.get("id_nro_producto", "")

    for row in rows:
        if not row.get("id_cliente"):
            row["id_cliente"] = row.get("phone_norm", "")
        row.pop("phone_norm", None)

    return rows

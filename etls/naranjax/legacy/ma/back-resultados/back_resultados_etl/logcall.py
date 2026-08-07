"""LOGCALL ingestion and enrichment for back resultados flow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import _load_raw_input


def _clean_phone(value: str) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if digits.startswith("549"):
        return digits[3:]
    if digits.startswith("54"):
        return digits[2:]
    return digits


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lowered_map = {str(col).strip().lower(): str(col) for col in df.columns}
    for candidate in candidates:
        found = lowered_map.get(candidate.lower())
        if found:
            return found
    return None


def _pick_phone_columns(df: pd.DataFrame) -> list[str]:
    candidates = [
        "[Entrada] user_number",
        "user_number",
        "[Entrada] msisdn",
        "msisdn",
        "PHONE",
        "phone",
        "tel_1",
        "tel_2",
        "tel_3",
        "TEL_1",
        "TEL_2",
        "TEL_3",
    ]
    lowered_map = {str(col).strip().lower(): str(col) for col in df.columns}
    selected: list[str] = []
    for candidate in candidates:
        found = lowered_map.get(candidate.lower())
        if found and found not in selected:
            selected.append(found)

    for col in df.columns:
        col_name = str(col).strip().lower()
        if col_name.startswith("tel_") and str(col) not in selected:
            selected.append(str(col))
    return selected


def build_logcall_input(logcall_path: Path, cruce_path: Path | None) -> pd.DataFrame:
    logcall_raw = _load_raw_input(str(logcall_path))
    if logcall_raw.empty:
        raise ValueError("LOGCALL vacio o sin filas")

    callref_col = _pick_column(logcall_raw, ["CALLREFID", "CALL_REFID", "callrefid", "call_refid"])
    phone_col = _pick_column(logcall_raw, ["PHONE", "phone", "msisdn", "user_number"])
    if not callref_col:
        raise ValueError("LOGCALL no contiene columna CALLREFID")

    base = pd.DataFrame(
        {
            "call_refid": logcall_raw[callref_col].astype(str).str.strip(),
            "phone_norm": logcall_raw[phone_col].astype(str).map(_clean_phone) if phone_col else "",
            "tipificaciones": "LOGCALL",
            "observaciones": "Cliente no responde. Intento de contacto sin éxito.",
        }
    )

    base["id_cliente"] = ""
    base["id_nro_producto"] = ""
    base["monto_compromiso"] = ""
    base["fecha_compromiso_tc"] = ""
    base["fecha_compromiso_nd"] = ""
    base["call_id"] = base["call_refid"]

    if cruce_path is None:
        return base

    cruce_raw = _load_raw_input(str(cruce_path))
    cruce_canon = pd.DataFrame()
    ref_col = _pick_column(cruce_raw, ["call_refid", "CALL_REFID", "Call ID", "call_id", "CALLREFID"])
    dni_col = _pick_column(cruce_raw, ["[Entrada] id_dni", "id_dni", "[Entrada] id_cliente", "id_cliente", "DNI"])
    product_col = _pick_column(cruce_raw, ["[Entrada] id_producto", "id_producto", "id_nro_producto", "NROPRODUCTO"])
    cruce_canon["call_refid"] = cruce_raw[ref_col].astype(str).str.strip() if ref_col else ""
    cruce_canon["id_cliente"] = cruce_raw[dni_col].astype(str) if dni_col else ""
    cruce_canon["id_nro_producto"] = cruce_raw[product_col].astype(str) if product_col else ""

    cruce_phone_cols = _pick_phone_columns(cruce_raw)
    cruce_phone = pd.Series([""] * len(cruce_raw), index=cruce_raw.index, dtype="string")
    for col in cruce_phone_cols:
        candidate = cruce_raw[col].astype(str)
        cruce_phone = cruce_phone.where(cruce_phone.str.strip() != "", candidate)
    cruce_canon["phone_norm"] = cruce_phone.map(_clean_phone)

    by_ref = cruce_canon[["call_refid", "id_cliente", "id_nro_producto"]].drop_duplicates(subset=["call_refid"])
    merged = base.merge(by_ref, on="call_refid", how="left", suffixes=("", "_x"))
    merged["id_cliente"] = merged["id_cliente_x"].fillna(merged["id_cliente"])
    merged["id_nro_producto"] = merged["id_nro_producto_x"].fillna(merged["id_nro_producto"])
    merged = merged.drop(columns=["id_cliente_x", "id_nro_producto_x"])

    unresolved = (merged["id_cliente"].astype(str).str.strip() == "") & (merged["phone_norm"].astype(str).str.strip() != "")
    if unresolved.any():
        by_phone = cruce_canon[["phone_norm", "id_cliente", "id_nro_producto"]]
        by_phone = by_phone[by_phone["phone_norm"].astype(str).str.strip() != ""]
        by_phone = by_phone.drop_duplicates(subset=["phone_norm"])
        merged2 = merged.loc[unresolved, ["phone_norm"]].merge(by_phone, on="phone_norm", how="left")
        merged.loc[unresolved, "id_cliente"] = merged2["id_cliente"].fillna("").values
        merged.loc[unresolved, "id_nro_producto"] = merged2["id_nro_producto"].fillna("").values

    unresolved_after_match = merged["id_cliente"].astype(str).str.strip() == ""
    if unresolved_after_match.any():
        merged.loc[unresolved_after_match, "id_cliente"] = merged.loc[unresolved_after_match, "phone_norm"]

    return merged.drop(columns=["phone_norm"])

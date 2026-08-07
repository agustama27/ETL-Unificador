"""Utilities to pivot daily plans to one row per product."""

from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd

from .cleaners import clean_monto
from .constants import ALLOWED_PLAN_INSTALLMENTS, MAX_DYNAMIC_PLANS, get_plan_column_names


ALLOWED_PLAN_INSTALLMENTS_SET = set(ALLOWED_PLAN_INSTALLMENTS)
INVALID_PRODUCT_KEYS = {"", "nan", "none", "null", "naranja"}


def _extract_plan_installments(value) -> int:
    if pd.isna(value):
        return 999999
    digits = re.findall(r"\d+", str(value))
    if not digits:
        return 999999
    return int(digits[0])


def _empty_pivot() -> pd.DataFrame:
    result = pd.DataFrame(columns=["nroproducto", "dni_doc", "cajon_planes", "deuda_total_planes", "deuda_vencida_planes"])
    result.attrs["max_plans"] = 0
    result.attrs["plan_columns"] = []
    result.attrs["excluded_nroproductos_can"] = []
    result.attrs["input_plan_rows"] = 0
    return result


def _normalize_product_key(value: object) -> str:
    key = "" if pd.isna(value) else str(value).strip()
    if re.fullmatch(r"\d+\.0+", key):
        key = key.split(".", 1)[0]
    if key.lower() in INVALID_PRODUCT_KEYS:
        return ""
    return key


def _normalize_doc_key(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    digits = re.sub(r"\D", "", text)
    return digits


def _iter_chunks(df_planes: pd.DataFrame | Iterable[pd.DataFrame]) -> Iterable[pd.DataFrame]:
    if isinstance(df_planes, pd.DataFrame):
        yield df_planes
        return

    yield from df_planes


def pivot_planes(df_planes: pd.DataFrame | Iterable[pd.DataFrame] | None) -> pd.DataFrame:
    """Return one row by nroproducto with dynamic plan columns."""
    if df_planes is None:
        return _empty_pivot()

    if isinstance(df_planes, pd.DataFrame) and df_planes.empty:
        return _empty_pivot()

    excluded_can: dict[str, None] = {}
    plans_by_product: dict[str, list[tuple[int, str, object, object, str, object, object]]] = {}
    merge_context: dict[str, tuple[str, str]] = {}
    input_plan_rows = 0

    for chunk in _iter_chunks(df_planes):
        if chunk is None or chunk.empty:
            continue

        input_plan_rows += len(chunk)
        working = chunk.copy()
        working["nroproducto"] = working["nroproducto"].astype(str).str.strip()
        working["cajon"] = working["cajon"].astype(str).str.strip()

        can_rows = working[working["cajon"].str.upper() == "CAN"]
        for nroproducto in can_rows["nroproducto"].dropna().astype(str).str.strip():
            if nroproducto:
                excluded_can[nroproducto] = None

        working = working[working["cajon"].str.upper() != "CAN"]
        if working.empty:
            continue

        for row in working.itertuples(index=False):
            nroproducto = _normalize_product_key(getattr(row, "nroproducto", ""))
            dni_doc = _normalize_doc_key(getattr(row, "nro_doc", ""))
            if not nroproducto and not dni_doc:
                continue

            merge_key = nroproducto if nroproducto else f"dni:{dni_doc}"
            merge_context.setdefault(merge_key, (nroproducto, dni_doc))
            product_plans = plans_by_product.setdefault(merge_key, [])
            plan_value = getattr(row, "plan", None)
            installments = _extract_plan_installments(plan_value)
            if installments not in ALLOWED_PLAN_INSTALLMENTS_SET:
                continue
            product_plans.append(
                (
                    installments,
                    "" if pd.isna(plan_value) else str(plan_value).strip(),
                    getattr(row, "importe_entrega", None),
                    getattr(row, "importe_cuota", None),
                    "" if pd.isna(getattr(row, "cajon", None)) else str(getattr(row, "cajon", "")).strip(),
                    getattr(row, "deuda_total", None),
                    getattr(row, "deuda_vencida", None),
                )
            )

    plans_by_product = {nroproducto: plans for nroproducto, plans in plans_by_product.items() if plans}

    if not plans_by_product:
        result = _empty_pivot()
        result.attrs["excluded_nroproductos_can"] = list(excluded_can.keys())
        result.attrs["input_plan_rows"] = input_plan_rows
        return result

    records: list[dict[str, object]] = []
    max_plans = 0

    for merge_key, product_plans in plans_by_product.items():
        product_plans.sort(key=lambda item: (item[0], item[1]))
        product_plans = product_plans[:MAX_DYNAMIC_PLANS]

        plan_count = len(product_plans)
        max_plans = max(max_plans, plan_count)

        nroproducto, dni_doc = merge_context.get(merge_key, ("", ""))
        first_plan = product_plans[0]
        record: dict[str, object] = {
            "nroproducto": nroproducto,
            "dni_doc": dni_doc,
            "cajon_planes": first_plan[4],
            "deuda_total_planes": clean_monto(first_plan[5]),
            "deuda_vencida_planes": clean_monto(first_plan[6]),
        }

        for index, plan_data in enumerate(product_plans, start=1):
            record[f"plan_{index}_cuotas"] = plan_data[1]
            record[f"plan_{index}_entrega"] = clean_monto(plan_data[2])
            record[f"plan_{index}_cuota_mensual"] = clean_monto(plan_data[3])

        records.append(record)

    plan_columns = get_plan_column_names(max_plans)
    fixed_columns = ["nroproducto", "dni_doc", "cajon_planes", "deuda_total_planes", "deuda_vencida_planes"]
    pivoted = pd.DataFrame(records)

    for column in plan_columns:
        if column not in pivoted.columns:
            pivoted[column] = ""
        else:
            pivoted[column] = pivoted[column].fillna("")

    pivoted = pivoted[fixed_columns + plan_columns]
    pivoted.attrs["max_plans"] = max_plans
    pivoted.attrs["plan_columns"] = plan_columns
    pivoted.attrs["excluded_nroproductos_can"] = list(excluded_can.keys())
    pivoted.attrs["input_plan_rows"] = input_plan_rows
    return pivoted

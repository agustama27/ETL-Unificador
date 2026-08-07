"""Merge base, plans and payments into an enriched daily state."""

from __future__ import annotations

import logging

import pandas as pd


def _normalize_key(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _extract_digits_key(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.replace(r"\D", "", regex=True).str.strip()


def _clean_amount(series: pd.Series) -> pd.Series:
    normalized = (
        series.fillna("0")
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace("$", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(normalized, errors="coerce").fillna(0.0)


def update_estado(
    df_base: pd.DataFrame,
    df_planes_pivot: pd.DataFrame | None,
    df_pagos: pd.DataFrame | None,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """Combine monthly base with daily PLANES and apply PAGOS effects."""
    active_logger = logger or logging.getLogger("etl_naranjax")
    estado = df_base.copy()
    estado["nroproducto"] = _normalize_key(estado["nroproducto"])

    if "recupero" not in estado.columns:
        estado["recupero"] = ""
    if "tipo_pago" not in estado.columns:
        estado["tipo_pago"] = ""

    if df_planes_pivot is not None:
        excluded_can = {
            str(value).strip()
            for value in df_planes_pivot.attrs.get("excluded_nroproductos_can", [])
            if str(value).strip()
        }
        if excluded_can:
            estado = estado[~estado["nroproducto"].isin(list(excluded_can))].copy()

    if df_planes_pivot is not None and not df_planes_pivot.empty:

        planes = df_planes_pivot.copy()
        planes["nroproducto"] = _normalize_key(planes["nroproducto"])
        plan_columns = list(planes.attrs.get("plan_columns", []))
        if plan_columns:
            existing_plan_columns = [column for column in estado.columns if column in plan_columns]
            if existing_plan_columns:
                active_logger.info(
                    "Dropping %s existing plan_* columns before PLANES merge to avoid stale collisions",
                    len(existing_plan_columns),
                )
                estado = estado.drop(columns=existing_plan_columns)
        planes_by_product = planes[planes["nroproducto"].fillna("").astype(str).str.strip() != ""].copy()
        planes_by_doc = planes.copy()
        if "dni_doc" in planes_by_doc.columns:
            planes_by_doc["dni_doc"] = _extract_digits_key(planes_by_doc["dni_doc"])
            planes_by_doc = planes_by_doc[planes_by_doc["dni_doc"] != ""].copy()

        merged = estado.merge(planes_by_product, on="nroproducto", how="left")
        has_plan_match = merged["deuda_total_planes"].notna()

        if not planes_by_doc.empty and "dni" in merged.columns and "dni_doc" in planes_by_doc.columns:
            merged["dni_doc_base"] = _extract_digits_key(merged["dni"])
            planes_doc_indexed = planes_by_doc.drop_duplicates(subset=["dni_doc"], keep="first").set_index("dni_doc")
            missing_mask = ~has_plan_match
            for helper_column in ["cajon_planes", "deuda_total_planes", "deuda_vencida_planes", *plan_columns]:
                if helper_column not in merged.columns:
                    merged[helper_column] = pd.NA
                mapped = merged.loc[missing_mask, "dni_doc_base"].map(planes_doc_indexed[helper_column])
                merged.loc[missing_mask, helper_column] = merged.loc[missing_mask, helper_column].combine_first(mapped)
            has_plan_match = merged["deuda_total_planes"].notna()
        merged.loc[has_plan_match, "total_deuda"] = merged.loc[has_plan_match, "deuda_total_planes"]
        merged.loc[has_plan_match, "total_vencida"] = merged.loc[has_plan_match, "deuda_vencida_planes"]
        merged.loc[has_plan_match, "cajon"] = merged.loc[has_plan_match, "cajon_planes"]

        for column in plan_columns:
            if column not in merged.columns:
                merged[column] = ""
            merged[column] = merged[column].fillna("")

        missing_count = int((~has_plan_match).sum())
        if missing_count > 0:
            active_logger.warning(
                "PLANES missing for %s base rows; monthly amounts were kept",
                missing_count,
            )

        estado = merged.drop(columns=["dni_doc_base"], errors="ignore")

    if df_pagos is not None and not df_pagos.empty:
        pagos = df_pagos.copy()
        pagos["nroproducto"] = _normalize_key(pagos["nroproducto"])
        if "recupero" not in pagos.columns:
            pagos["recupero"] = ""
        if "tipo_pago" not in pagos.columns:
            pagos["tipo_pago"] = ""
        if "importe_pago" not in pagos.columns:
            pagos["importe_pago"] = 0

        pagos["recupero"] = pagos["recupero"].fillna("").astype(str).str.strip()
        pagos["tipo_pago"] = pagos["tipo_pago"].fillna("").astype(str).str.strip()
        pagos["importe_pago"] = _clean_amount(pagos["importe_pago"])

        pagos_agg = (
            pagos.groupby("nroproducto", as_index=False)
            .agg(
                recupero=("recupero", "last"),
                tipo_pago=("tipo_pago", "last"),
                importe_pago=("importe_pago", "sum"),
            )
        )

        estado = estado.merge(pagos_agg, on="nroproducto", how="left", suffixes=("", "_pagos"))
        estado["recupero"] = estado["recupero_pagos"].combine_first(estado["recupero"])
        estado["tipo_pago"] = estado["tipo_pago_pagos"].combine_first(estado["tipo_pago"])

        descuento_mask = estado["importe_pago"].notna() & (estado["importe_pago"] > 0)
        if descuento_mask.any():
            estado["total_deuda"] = pd.to_numeric(estado["total_deuda"], errors="coerce").fillna(0.0)
            estado["total_vencida"] = pd.to_numeric(estado["total_vencida"], errors="coerce").fillna(0.0)
            estado.loc[descuento_mask, "total_deuda"] = (
                estado.loc[descuento_mask, "total_deuda"] - estado.loc[descuento_mask, "importe_pago"]
            ).clip(lower=0)
            estado.loc[descuento_mask, "total_vencida"] = (
                estado.loc[descuento_mask, "total_vencida"] - estado.loc[descuento_mask, "importe_pago"]
            ).clip(lower=0)

        estado = estado.drop(columns=["recupero_pagos", "tipo_pago_pagos", "importe_pago"], errors="ignore")
        active_logger.info("PAGOS applied rows=%s products=%s", len(pagos), len(pagos_agg))

    estado["recupero"] = estado["recupero"].fillna("").astype(str).str.strip()
    estado["tipo_pago"] = estado["tipo_pago"].fillna("").astype(str).str.strip()

    recupero_si_mask = estado["recupero"].str.upper() == "SI"
    recupero_si_count = int(recupero_si_mask.sum())
    if recupero_si_count > 0:
        active_logger.info(
            "Excluding %s clients with RECUPERO=SI from persistent state",
            recupero_si_count,
        )
        estado = estado[~recupero_si_mask].copy()

    for helper_column in ["cajon_planes", "deuda_total_planes", "deuda_vencida_planes"]:
        if helper_column in estado.columns:
            estado = estado.drop(columns=[helper_column])

    if "fuente_deuda" not in estado.columns:
        estado["fuente_deuda"] = "api"

    plan_cols_present = [column for column in estado.columns if column.startswith("plan_") and column.endswith("_cuotas")]
    if plan_cols_present:
        tiene_plan_mask = (
            estado[plan_cols_present]
            .fillna("")
            .astype(str)
            .apply(lambda series: series.str.strip())
            .ne("")
            .any(axis=1)
        )
        estado.loc[tiene_plan_mask, "fuente_deuda"] = "planes"

    recupero_mask = estado["recupero"].fillna("").astype(str).str.strip().ne("")
    estado.loc[recupero_mask & (estado["fuente_deuda"] == "api"), "fuente_deuda"] = "pagos"

    return estado

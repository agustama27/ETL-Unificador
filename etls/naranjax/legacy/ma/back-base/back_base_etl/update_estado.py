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


def _last_non_empty_value(series: pd.Series) -> str:
    cleaned = series.fillna("").astype(str).str.strip()
    non_empty = cleaned[cleaned != ""]
    if non_empty.empty:
        return ""
    return str(non_empty.iloc[-1])


def _normalize_cajon(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.upper()


def _is_blank(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip() == ""


def _drop_legacy_merge_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [column for column in columns if column in df.columns]
    if existing:
        df = df.drop(columns=existing)
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()].copy()
    return df


def _build_recupero_exclusion_mask(estado: pd.DataFrame) -> pd.Series:
    recupero_si_mask = estado["recupero"].fillna("").astype(str).str.strip().str.upper() == "SI"
    if "cajon_actual_prod" not in estado.columns:
        return pd.Series(False, index=estado.index)
    cajon_actual_blank_mask = _is_blank(estado["cajon_actual_prod"])
    return recupero_si_mask & cajon_actual_blank_mask


def update_estado(
    df_base: pd.DataFrame,
    df_planes_pivot: pd.DataFrame | None,
    df_pagos: pd.DataFrame | None,
    logger: logging.Logger | None = None,
) -> pd.DataFrame:
    """Combine monthly base with daily PLANES and apply PAGOS effects."""
    active_logger = logger or logging.getLogger("etl_naranjax")
    estado = _drop_legacy_merge_columns(df_base.copy(), ["dni_doc_x", "dni_doc_y"])
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

        planes = _drop_legacy_merge_columns(df_planes_pivot.copy(), ["dni_doc_x", "dni_doc_y"])
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

        product_merge_suffix = "__planes_product"
        stale_product_merge_columns = [
            column for column in estado.columns if column.endswith(product_merge_suffix)
        ]
        if stale_product_merge_columns:
            active_logger.info(
                "Dropping %s stale PLANES merge columns before product merge",
                len(stale_product_merge_columns),
            )
            estado = estado.drop(columns=stale_product_merge_columns)

        merged = estado.merge(
            planes_by_product,
            on="nroproducto",
            how="left",
            suffixes=("", product_merge_suffix),
        )
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
        if "dt_actual" not in pagos.columns:
            pagos["dt_actual"] = ""
        if "dv_actual" not in pagos.columns:
            pagos["dv_actual"] = ""
        if "cajon_asig_prod" not in pagos.columns:
            pagos["cajon_asig_prod"] = ""
        if "cajon_actual_prod" not in pagos.columns:
            pagos["cajon_actual_prod"] = ""

        pagos["recupero"] = pagos["recupero"].fillna("").astype(str).str.strip()
        pagos["tipo_pago"] = pagos["tipo_pago"].fillna("").astype(str).str.strip()
        pagos["cajon_actual_prod"] = pagos["cajon_actual_prod"].fillna("").astype(str).str.strip()
        pagos["dt_actual"] = pagos["dt_actual"].fillna("").astype(str).str.strip()
        pagos["dv_actual"] = pagos["dv_actual"].fillna("").astype(str).str.strip()
        pagos["importe_pago"] = _clean_amount(pagos["importe_pago"])

        pagos_rows_total = len(pagos)
        cajon_asig_m90_mask = _normalize_cajon(pagos["cajon_asig_prod"]) == "M90"
        cajon_actual_scope_mask = _normalize_cajon(pagos["cajon_actual_prod"]).isin(["M60", "M90"])
        pagos_include_mask = cajon_asig_m90_mask & cajon_actual_scope_mask

        pagos_cajon = pagos[cajon_asig_m90_mask].copy()
        pagos_cajon_agg = (
            pagos_cajon.groupby("nroproducto", as_index=False)
            .agg(
                cajon_actual_prod=("cajon_actual_prod", _last_non_empty_value),
                recupero_cajon=("recupero", "last"),
            )
        )

        pagos = pagos[pagos_include_mask].copy()
        pagos_excluded_asig = int((~cajon_asig_m90_mask).sum())
        pagos_excluded_actual = int((~cajon_actual_scope_mask).sum())
        pagos_excluded_total = int((~pagos_include_mask).sum())
        active_logger.info(
            "PAGOS filter rows_total=%s included=%s excluded_total=%s excluded_cajon_asig_not_m90=%s excluded_cajon_actual_not_in_scope=%s",
            pagos_rows_total,
            len(pagos),
            pagos_excluded_total,
            pagos_excluded_asig,
            pagos_excluded_actual,
        )

        estado = estado.merge(pagos_cajon_agg, on="nroproducto", how="left", suffixes=("", "_pagos_cajon"))
        estado["cajon"] = estado["cajon_actual_prod"].replace("", pd.NA).combine_first(estado["cajon"])

        if pagos.empty:
            estado["recupero"] = estado["recupero"].fillna("").astype(str).str.strip()
            estado["tipo_pago"] = estado["tipo_pago"].fillna("").astype(str).str.strip()
            recupero_si_mask = _build_recupero_exclusion_mask(estado)
            recupero_si_count = int(recupero_si_mask.sum())
            if recupero_si_count > 0:
                active_logger.info(
                    "Excluding %s clients with RECUPERO=SI and CAJON_ACTUAL_PROD blank from persistent state",
                    recupero_si_count,
                )
                estado = estado[~recupero_si_mask].copy()

            for helper_column in ["cajon_planes", "deuda_total_planes", "deuda_vencida_planes"]:
                if helper_column in estado.columns:
                    estado = estado.drop(columns=[helper_column])

            return estado

        pagos_agg = (
            pagos.groupby("nroproducto", as_index=False)
            .agg(
                recupero=("recupero", "last"),
                tipo_pago=("tipo_pago", "last"),
                importe_pago=("importe_pago", "sum"),
                dt_actual=("dt_actual", _last_non_empty_value),
                dv_actual=("dv_actual", _last_non_empty_value),
            )
        )

        estado = estado.merge(pagos_agg, on="nroproducto", how="left", suffixes=("", "_pagos"))
        estado["recupero"] = estado["recupero_pagos"].combine_first(estado["recupero_cajon"]).combine_first(estado["recupero"])
        estado["tipo_pago"] = estado["tipo_pago_pagos"].combine_first(estado["tipo_pago"])

        estado["total_deuda"] = pd.to_numeric(estado["total_deuda"], errors="coerce").fillna(0.0)
        estado["total_vencida"] = pd.to_numeric(estado["total_vencida"], errors="coerce").fillna(0.0)

        dt_raw = estado["dt_actual"].fillna("").astype(str).str.strip()
        dv_raw = estado["dv_actual"].fillna("").astype(str).str.strip()
        dt_provided_mask = dt_raw != ""
        dv_provided_mask = dv_raw != ""

        if dt_provided_mask.any():
            estado.loc[dt_provided_mask, "total_deuda"] = _clean_amount(dt_raw[dt_provided_mask])
        if dv_provided_mask.any():
            estado.loc[dv_provided_mask, "total_vencida"] = _clean_amount(dv_raw[dv_provided_mask])

        descuento_total_deuda_mask = (~dt_provided_mask) & estado["importe_pago"].notna() & (estado["importe_pago"] > 0)
        if descuento_total_deuda_mask.any():
            estado.loc[descuento_total_deuda_mask, "total_deuda"] = (
                estado.loc[descuento_total_deuda_mask, "total_deuda"]
                - estado.loc[descuento_total_deuda_mask, "importe_pago"]
            ).clip(lower=0)

        descuento_total_vencida_mask = (~dv_provided_mask) & estado["importe_pago"].notna() & (estado["importe_pago"] > 0)
        if descuento_total_vencida_mask.any():
            estado.loc[descuento_total_vencida_mask, "total_vencida"] = (
                estado.loc[descuento_total_vencida_mask, "total_vencida"]
                - estado.loc[descuento_total_vencida_mask, "importe_pago"]
            ).clip(lower=0)

        estado = estado.drop(
            columns=["recupero_pagos", "recupero_cajon", "tipo_pago_pagos", "importe_pago", "dt_actual", "dv_actual"],
            errors="ignore",
        )
        active_logger.info("PAGOS applied rows=%s products=%s", len(pagos), len(pagos_agg))

    estado["recupero"] = estado["recupero"].fillna("").astype(str).str.strip()
    estado["tipo_pago"] = estado["tipo_pago"].fillna("").astype(str).str.strip()

    recupero_si_mask = _build_recupero_exclusion_mask(estado)
    recupero_si_count = int(recupero_si_mask.sum())
    if recupero_si_count > 0:
        active_logger.info(
            "Excluding %s clients with RECUPERO=SI and CAJON_ACTUAL_PROD blank from persistent state",
            recupero_si_count,
        )
        estado = estado[~recupero_si_mask].copy()

    for helper_column in ["cajon_planes", "deuda_total_planes", "deuda_vencida_planes", "cajon_actual_prod"]:
        if helper_column in estado.columns:
            estado = estado.drop(columns=[helper_column])

    return estado

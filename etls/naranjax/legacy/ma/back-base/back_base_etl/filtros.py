"""Business filters for the daily Mora Avanzada output."""

from __future__ import annotations

import logging

import pandas as pd


DEFAULT_CAJONES_SCOPE = ("M60", "M90")


def aplicar_filtros(
    df: pd.DataFrame,
    scope_cajones: tuple[str, ...] = DEFAULT_CAJONES_SCOPE,
    logger: logging.Logger | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Filter rows by allowed cajon scope and return exclusion summary."""
    active_logger = logger or logging.getLogger("etl_naranjax")
    scope = {str(value).strip().upper() for value in scope_cajones if str(value).strip()}
    if not scope:
        raise ValueError("scope_cajones cannot be empty")

    if "cajon" not in df.columns:
        raise KeyError("Column 'cajon' is required to apply Mora Avanzada filters")

    working = df.copy()
    cajon_normalizado = working["cajon"].fillna("").astype(str).str.strip().str.upper()
    include_mask = cajon_normalizado.isin(scope)
    excluded_count = int((~include_mask).sum())

    if excluded_count > 0:
        active_logger.info(
            "Excluding %s clients with cajon out of scope %s",
            excluded_count,
            sorted(scope),
        )

    filtrado = working[include_mask].copy()
    resumen = {
        "cajon_fuera_scope": excluded_count,
        "total_incluidos": int(include_mask.sum()),
        "total_excluidos": excluded_count,
    }
    return filtrado, resumen

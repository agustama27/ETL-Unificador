from __future__ import annotations

import logging
from pathlib import Path
import sys

import pandas as pd


BACK_BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_BASE_DIR))
from back_base_etl.update_estado import update_estado  # noqa: E402


def test_update_estado_applies_planes_precedence_and_pagos_discount() -> None:
    df_base = pd.DataFrame(
        [
            {
                "nroproducto": "1",
                "total_deuda": 1000.0,
                "total_vencida": 300.0,
                "cajon": "M60",
            },
            {
                "nroproducto": "2",
                "total_deuda": 2000.0,
                "total_vencida": 400.0,
                "cajon": "M90",
            },
            {
                "nroproducto": "3",
                "total_deuda": 1500.0,
                "total_vencida": 350.0,
                "cajon": "M30",
            },
        ]
    )

    df_planes_pivot = pd.DataFrame(
        [
            {
                "nroproducto": "1",
                "cajon_planes": "M45",
                "deuda_total_planes": 1111.0,
                "deuda_vencida_planes": 222.0,
                "plan_1_cuotas": "3",
                "plan_1_entrega": 100.0,
                "plan_1_cuota_mensual": 337.0,
            }
        ]
    )
    df_planes_pivot.attrs["plan_columns"] = [
        "plan_1_cuotas",
        "plan_1_entrega",
        "plan_1_cuota_mensual",
    ]
    df_planes_pivot.attrs["excluded_nroproductos_can"] = ["3"]

    df_pagos = pd.DataFrame(
        [
            {
                "nroproducto": "1",
                "recupero": "SI",
                "tipo_pago": "TRANSFER",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M90",
            },
            {
                "nroproducto": "2",
                "recupero": "NO",
                "tipo_pago": "PAGO_LINK",
                "importe_pago": "100",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M60",
            },
        ]
    )

    result = update_estado(df_base, df_planes_pivot, df_pagos)

    assert set(result["nroproducto"]) == {"1", "2"}

    row_2 = result[result["nroproducto"] == "2"].iloc[0]
    assert row_2["total_deuda"] == 1900.0
    assert row_2["total_vencida"] == 300.0
    assert row_2["cajon"] == "M60"
    assert row_2["recupero"] == "NO"
    assert row_2["tipo_pago"] == "PAGO_LINK"


def test_update_estado_warns_when_planes_missing_for_base_rows(caplog) -> None:
    caplog.set_level(logging.WARNING)

    df_base = pd.DataFrame(
        [
            {"nroproducto": "1", "total_deuda": 1000.0, "total_vencida": 100.0, "cajon": "M60"},
            {"nroproducto": "2", "total_deuda": 2000.0, "total_vencida": 200.0, "cajon": "M90"},
        ]
    )
    df_planes_pivot = pd.DataFrame(
        [
            {
                "nroproducto": "1",
                "cajon_planes": "M45",
                "deuda_total_planes": 900.0,
                "deuda_vencida_planes": 90.0,
            }
        ]
    )
    df_planes_pivot.attrs["plan_columns"] = []
    df_planes_pivot.attrs["excluded_nroproductos_can"] = []

    result = update_estado(df_base, df_planes_pivot, df_pagos=None)

    row_2 = result[result["nroproducto"] == "2"].iloc[0]
    assert row_2["total_deuda"] == 2000.0
    assert row_2["total_vencida"] == 200.0

    assert "PLANES missing for 1 base rows" in caplog.text


def test_update_estado_keeps_rows_when_recupero_only_comes_from_pagos() -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "1", "total_deuda": 1000.0, "total_vencida": 100.0, "cajon": "M60"},
            {"nroproducto": "2", "total_deuda": 900.0, "total_vencida": 90.0, "cajon": "M30"},
        ]
    )
    df_pagos = pd.DataFrame(
        [
            {
                "nroproducto": "1",
                "recupero": " si ",
                "tipo_pago": "TRANSFER",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M90",
            },
            {
                "nroproducto": "2",
                "recupero": "NO",
                "tipo_pago": "PAGO_LINK",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M60",
            },
        ]
    )

    result = update_estado(df_base, df_planes_pivot=None, df_pagos=df_pagos)

    assert list(result["nroproducto"]) == ["1", "2"]
    assert list(result["recupero"]) == ["si", "NO"]
    assert list(result["tipo_pago"]) == ["TRANSFER", "PAGO_LINK"]


def test_update_estado_regression_pagos_content_changes_output() -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "100", "total_deuda": 500.0, "total_vencida": 50.0, "cajon": "M60"},
            {"nroproducto": "101", "total_deuda": 600.0, "total_vencida": 60.0, "cajon": "M90"},
        ]
    )
    df_planes_pivot = pd.DataFrame(
        [
            {
                "nroproducto": "100",
                "cajon_planes": "M45",
                "deuda_total_planes": 700.0,
                "deuda_vencida_planes": 70.0,
            }
        ]
    )
    df_planes_pivot.attrs["plan_columns"] = []
    df_planes_pivot.attrs["excluded_nroproductos_can"] = []

    pagos_a = pd.DataFrame([
        {"nroproducto": "100", "recupero": "SI", "tipo_pago": "TRANSFER", "cajon_asig_prod": "M90", "cajon_actual_prod": "M90"}
    ])
    pagos_b = pd.DataFrame([
        {"nroproducto": "101", "recupero": "NO", "tipo_pago": "PAGO_LINK", "cajon_asig_prod": "M90", "cajon_actual_prod": "M60"}
    ])

    result_a = update_estado(df_base, df_planes_pivot, df_pagos=pagos_a)
    result_b = update_estado(df_base, df_planes_pivot, df_pagos=pagos_b)

    assert set(result_a["nroproducto"]) == {"100", "101"}
    assert set(result_b["nroproducto"]) == {"100", "101"}


def test_update_estado_applies_pagos_discount_from_importe_pago() -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "200", "total_deuda": 1200.0, "total_vencida": 500.0, "cajon": "M90"},
        ]
    )
    df_pagos = pd.DataFrame(
        [
            {"nroproducto": "200", "recupero": "NO", "tipo_pago": "LINK", "importe_pago": "300"},
            {"nroproducto": "200", "recupero": "NO", "tipo_pago": "LINK", "importe_pago": "250"},
        ]
    )
    df_pagos["cajon_asig_prod"] = "M90"
    df_pagos["cajon_actual_prod"] = "M90"

    result = update_estado(df_base, df_planes_pivot=None, df_pagos=df_pagos)
    row = result.iloc[0]

    assert row["total_deuda"] == 650.0
    assert row["total_vencida"] == 0.0


def test_update_estado_prioritizes_dt_dv_actual_over_importe_pago() -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "300", "total_deuda": 2000.0, "total_vencida": 800.0, "cajon": "M90"},
        ]
    )
    df_pagos = pd.DataFrame(
        [
            {
                "nroproducto": "300",
                "recupero": "NO",
                "tipo_pago": "LINK",
                "importe_pago": "300",
                "dt_actual": "1100",
                "dv_actual": "450",
            }
        ]
    )
    df_pagos["cajon_asig_prod"] = "M90"
    df_pagos["cajon_actual_prod"] = "M60"

    result = update_estado(df_base, df_planes_pivot=None, df_pagos=df_pagos)
    row = result.iloc[0]

    assert row["total_deuda"] == 1100.0
    assert row["total_vencida"] == 450.0


def test_update_estado_uses_importe_pago_as_fallback_when_only_one_actual_amount_is_present() -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "301", "total_deuda": 2000.0, "total_vencida": 800.0, "cajon": "M90"},
        ]
    )
    df_pagos = pd.DataFrame(
        [
            {
                "nroproducto": "301",
                "recupero": "NO",
                "tipo_pago": "LINK",
                "importe_pago": "300",
                "dt_actual": "1500",
                "dv_actual": "",
            }
        ]
    )
    df_pagos["cajon_asig_prod"] = "M90"
    df_pagos["cajon_actual_prod"] = "M90"

    result = update_estado(df_base, df_planes_pivot=None, df_pagos=df_pagos)
    row = result.iloc[0]

    assert row["total_deuda"] == 1500.0
    assert row["total_vencida"] == 500.0


def test_update_estado_filtra_pagos_por_cajon_asig_m90_y_cajon_actual_en_scope(caplog) -> None:
    caplog.set_level(logging.INFO)
    df_base = pd.DataFrame(
        [
            {"nroproducto": "400", "total_deuda": 1000.0, "total_vencida": 300.0, "cajon": "M90"},
        ]
    )
    df_pagos = pd.DataFrame(
        [
            {
                "nroproducto": "400",
                "recupero": "NO",
                "tipo_pago": "LINK",
                "importe_pago": "100",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M60",
            },
            {
                "nroproducto": "400",
                "recupero": "SI",
                "tipo_pago": "TRANSFER",
                "importe_pago": "100",
                "cajon_asig_prod": "M60",
                "cajon_actual_prod": "M90",
            },
            {
                "nroproducto": "400",
                "recupero": "SI",
                "tipo_pago": "TRANSFER",
                "importe_pago": "100",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "",
            },
        ]
    )

    result = update_estado(df_base, df_planes_pivot=None, df_pagos=df_pagos)
    row = result.iloc[0]

    assert row["total_deuda"] == 900.0
    assert row["total_vencida"] == 200.0
    assert row["recupero"] == "NO"
    assert row["cajon"] == "M60"
    assert "excluded_cajon_asig_not_m90=1" in caplog.text


def test_update_estado_ignores_pagos_not_present_in_base_mensual() -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "700", "total_deuda": 500.0, "total_vencida": 100.0, "cajon": "M90"},
        ]
    )
    df_pagos = pd.DataFrame(
        [
            {
                "nroproducto": "999",
                "recupero": "NO",
                "tipo_pago": "LINK",
                "importe_pago": "200",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M90",
            },
        ]
    )

    result = update_estado(df_base, df_planes_pivot=None, df_pagos=df_pagos)
    row = result.iloc[0]

    assert len(result) == 1
    assert row["nroproducto"] == "700"
    assert row["total_deuda"] == 500.0
    assert row["total_vencida"] == 100.0


def test_update_estado_excludes_only_recupero_si_with_blank_cajon_actual() -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "800", "total_deuda": 1000.0, "total_vencida": 300.0, "cajon": "M90"},
            {"nroproducto": "801", "total_deuda": 900.0, "total_vencida": 250.0, "cajon": "M90"},
        ]
    )
    df_pagos = pd.DataFrame(
        [
            {
                "nroproducto": "800",
                "recupero": "SI",
                "tipo_pago": "LINK",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M60",
            },
            {
                "nroproducto": "801",
                "recupero": "SI",
                "tipo_pago": "LINK",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "",
            },
        ]
    )

    result = update_estado(df_base, df_planes_pivot=None, df_pagos=df_pagos)

    assert set(result["nroproducto"]) == {"800"}


def test_update_estado_applies_cajon_actual_prod_from_pagos_when_present() -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "500", "total_deuda": 1000.0, "total_vencida": 300.0, "cajon": "M90"},
        ]
    )
    df_pagos = pd.DataFrame(
        [
            {
                "nroproducto": "500",
                "recupero": "NO",
                "tipo_pago": "LINK",
                "importe_pago": "0",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M30",
            },
        ]
    )

    result = update_estado(df_base, df_planes_pivot=None, df_pagos=df_pagos)
    row = result.iloc[0]

    assert row["cajon"] == "M30"


def test_update_estado_replaces_stale_plan_columns_from_estado() -> None:
    df_base = pd.DataFrame(
        [
            {
                "nroproducto": "10",
                "total_deuda": 1000.0,
                "total_vencida": 100.0,
                "cajon": "M60",
                "plan_1_cuotas": "",
                "plan_1_entrega": "",
                "plan_1_cuota_mensual": "",
            }
        ]
    )
    df_planes_pivot = pd.DataFrame(
        [
            {
                "nroproducto": "10",
                "cajon_planes": "M45",
                "deuda_total_planes": 900.0,
                "deuda_vencida_planes": 90.0,
                "plan_1_cuotas": "3",
                "plan_1_entrega": 120.0,
                "plan_1_cuota_mensual": 260.0,
            }
        ]
    )
    df_planes_pivot.attrs["plan_columns"] = [
        "plan_1_cuotas",
        "plan_1_entrega",
        "plan_1_cuota_mensual",
    ]
    df_planes_pivot.attrs["excluded_nroproductos_can"] = []

    result = update_estado(df_base, df_planes_pivot, df_pagos=None)
    row = result.iloc[0]

    assert row["plan_1_cuotas"] == "3"
    assert row["plan_1_entrega"] == 120.0
    assert row["plan_1_cuota_mensual"] == 260.0


def test_update_estado_applies_planes_by_dni_when_nroproducto_is_not_canonical() -> None:
    df_base = pd.DataFrame(
        [
            {
                "dni": "DU35214453",
                "nroproducto": "DU00035214453",
                "total_deuda": 1000.0,
                "total_vencida": 200.0,
                "cajon": "M60",
            }
        ]
    )
    df_planes_pivot = pd.DataFrame(
        [
            {
                "nroproducto": "",
                "dni_doc": "35214453",
                "cajon_planes": "M120",
                "deuda_total_planes": 1500.0,
                "deuda_vencida_planes": 350.0,
                "plan_1_cuotas": "3",
                "plan_1_entrega": 0.0,
                "plan_1_cuota_mensual": 500.0,
            }
        ]
    )
    df_planes_pivot.attrs["plan_columns"] = [
        "plan_1_cuotas",
        "plan_1_entrega",
        "plan_1_cuota_mensual",
    ]
    df_planes_pivot.attrs["excluded_nroproductos_can"] = []

    result = update_estado(df_base, df_planes_pivot, df_pagos=None)
    row = result.iloc[0]

    assert row["total_deuda"] == 1500.0
    assert row["total_vencida"] == 350.0
    assert row["cajon"] == "M120"
    assert row["plan_1_cuotas"] == "3"

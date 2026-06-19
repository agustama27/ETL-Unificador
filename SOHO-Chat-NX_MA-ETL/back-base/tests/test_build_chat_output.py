from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


BACK_BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_BASE_DIR))
from back_base_etl.transformers import build_chat_output  # noqa: E402


def _roman_row(**overrides: str) -> dict[str, str]:
    base = {
        "id_dni": "30123456",
        "nombre_cliente": "JUAN GOMEZ",
        "id_producto": "TC-001",
        "tipo_marca_plan": "Sin",
        "monto_deuda_tc": "100.0",
        "monto_deuda_nd": "0.0",
        "monto_deuda_total": "100.0",
        "tipo_cajon": "M90",
        "tipo_ecosistema": "PURO",
        "tipo_estrategia": "NORMAL",
        "fecha_limite_sistema": "2026-05-26",
        "fuente_deuda": "api",
        "plan_1_cuotas": "",
        "plan_1_entrega": "",
        "plan_1_cuota_mensual": "",
    }
    base.update(overrides)
    return base


def test_build_chat_output_consolidacion() -> None:
    df_roman = pd.DataFrame(
        [
            _roman_row(id_dni="30123456", id_producto="TC-001", monto_deuda_total="100.0", monto_deuda_tc="100.0"),
            _roman_row(id_dni="30123456", id_producto="ND-002", monto_deuda_total="50.0", monto_deuda_nd="50.0"),
            _roman_row(id_dni="30999888", id_producto="TC-003", monto_deuda_total="30.0", monto_deuda_tc="30.0"),
        ]
    )

    out = build_chat_output(df_roman, plan_columns=["plan_1_cuotas", "plan_1_entrega", "plan_1_cuota_mensual"])

    assert len(out) == 2
    row = out[out["id_dni"] == "30123456"].iloc[0]
    assert row["cantidad_productos"] == "2"
    assert '"TC-001"' in row["productos_json"]
    assert '"ND-002"' in row["productos_json"]


def test_build_chat_output_fuente_planes() -> None:
    df_roman = pd.DataFrame(
        [
            _roman_row(
                fuente_deuda="planes",
                monto_deuda_total="150.0",
                plan_1_cuotas="3",
                plan_1_entrega="10",
                plan_1_cuota_mensual="50",
                tipo_marca_plan="Con",
            )
        ]
    )

    out = build_chat_output(df_roman, plan_columns=["plan_1_cuotas", "plan_1_entrega", "plan_1_cuota_mensual"])
    row = out.iloc[0]

    assert row["fuente_deuda"] == "planes"
    assert float(row["monto_total_vencido"]) == 150.0
    assert row["tiene_planes"] == "True"


def test_build_chat_output_fuente_pagos() -> None:
    df_roman = pd.DataFrame([_roman_row(fuente_deuda="pagos", monto_deuda_total="120.0")])

    out = build_chat_output(df_roman)
    row = out.iloc[0]

    assert row["fuente_deuda"] == "pagos"
    assert float(row["monto_total_vencido"]) == 120.0


def test_build_chat_output_fuente_api() -> None:
    df_roman = pd.DataFrame([_roman_row(fuente_deuda="api", monto_deuda_total="999.0")])

    out = build_chat_output(df_roman)
    row = out.iloc[0]

    assert row["fuente_deuda"] == "api"
    assert float(row["monto_total_vencido"]) == 0.0


def test_build_chat_output_sin_planes_hoy() -> None:
    df_roman = pd.DataFrame(
        [
            _roman_row(
                fuente_deuda="planes",
                plan_1_cuotas="3",
                plan_1_entrega="100",
                plan_1_cuota_mensual="40",
            )
        ]
    )

    out = build_chat_output(
        df_roman,
        plan_columns=["plan_1_cuotas", "plan_1_entrega", "plan_1_cuota_mensual"],
        planes_disponibles_hoy=False,
    )
    row = out.iloc[0]

    assert row["tiene_planes"] == "False"


def test_build_chat_output_prelegal() -> None:
    df_roman = pd.DataFrame([_roman_row(tipo_estrategia="gestion_prelegal_especial")])

    out = build_chat_output(df_roman)
    row = out.iloc[0]

    assert row["estado_prelegal"] in {"Si", "Sí"}

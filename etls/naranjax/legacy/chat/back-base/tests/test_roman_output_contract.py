from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BACK_BASE_DIR = REPO_ROOT / "back-base"
sys.path.insert(0, str(BACK_BASE_DIR))

from back_base_etl.constants import OUTPUT_COLUMNS_ROMAN  # noqa: E402
from back_base_etl.transformers import sort_roman_rows, transform  # noqa: E402


def _base_row() -> dict[str, str]:
    return {
        "dni": "DU 20.333.444",
        "nombre_apellido": "Cliente Test",
        "deuda_vencida_tc": "10",
        "deuda_vencida_nd": "20",
        "total_vencida": "30",
        "deuda_total_tc": "50",
        "deuda_total_nd": "150",
        "total_deuda": "200",
        "estrategia": "M90",
        "nroproducto": " 1003 ",
        "marca_plan": "SIN PLAN",
        "telefono1": "",
        "telefono2": "",
        "telefono3": "",
        "telefono4": "",
        "email1": "",
        "email2": "",
        "email3": "",
        "cajon": "M30",
        "ecosistema": "PURO",
        "asignacion": "Elite",
    }


def test_roman_output_includes_id_producto_after_id_dni() -> None:
    df = pd.DataFrame([_base_row()])

    roman = transform(df, output_columns_base=OUTPUT_COLUMNS_ROMAN)

    assert "id_producto" in roman.columns
    row = roman.iloc[0]
    assert row["id_producto"] == "1003"

    columns = roman.columns.tolist()
    assert columns.index("id_producto") == columns.index("id_dni") + 1
    assert columns.index("tipo_marca_plan") == columns.index("id_producto") + 1


def test_roman_tipo_marca_plan_is_con_when_any_plan_column_has_data() -> None:
    row = _base_row()
    row["plan_1_cuotas"] = "6"
    row["plan_1_entrega"] = ""
    row["plan_1_cuota_mensual"] = ""

    roman = transform(
        pd.DataFrame([row]),
        plan_columns=["plan_1_cuotas", "plan_1_entrega", "plan_1_cuota_mensual"],
        output_columns_base=OUTPUT_COLUMNS_ROMAN,
    )

    assert roman.iloc[0]["tipo_marca_plan"] == "Con"


def test_roman_tipo_marca_plan_is_sin_when_no_plan_columns_exist() -> None:
    roman = transform(pd.DataFrame([_base_row()]), output_columns_base=OUTPUT_COLUMNS_ROMAN)
    assert roman.iloc[0]["tipo_marca_plan"] == "Sin"


def test_roman_tipo_marca_plan_does_not_depend_on_marca_plan_raw() -> None:
    row = _base_row()
    row["marca_plan"] = "CON PLAN"
    row["plan_1_cuotas"] = ""
    row["plan_1_entrega"] = ""
    row["plan_1_cuota_mensual"] = ""

    roman = transform(
        pd.DataFrame([row]),
        plan_columns=["plan_1_cuotas", "plan_1_entrega", "plan_1_cuota_mensual"],
        output_columns_base=OUTPUT_COLUMNS_ROMAN,
    )

    assert roman.iloc[0]["tipo_marca_plan"] == "Sin"


def test_roman_output_preserves_raw_dni_with_prefix() -> None:
    row = _base_row()
    row["dni"] = "DU26373245"
    df = pd.DataFrame([row])

    roman = transform(df, output_columns_base=OUTPUT_COLUMNS_ROMAN)

    assert roman.iloc[0]["id_dni"] == "DU26373245"


def test_roman_output_is_sorted_by_tel3_dni_producto_with_empty_tel3_last() -> None:
    rows = []

    row_a = _base_row()
    row_a["dni"] = "20333446"
    row_a["nroproducto"] = "1002"
    row_a["telefono3"] = ""
    rows.append(row_a)

    row_b = _base_row()
    row_b["dni"] = "20333445"
    row_b["nroproducto"] = "1003"
    row_b["telefono3"] = "5491122223333"
    rows.append(row_b)

    row_c = _base_row()
    row_c["dni"] = "20333444"
    row_c["nroproducto"] = "1001"
    row_c["telefono3"] = "5491122223333"
    rows.append(row_c)

    row_d = _base_row()
    row_d["dni"] = "20333446"
    row_d["nroproducto"] = "1001"
    row_d["telefono3"] = "5491122223333"
    rows.append(row_d)

    roman = transform(pd.DataFrame(rows), output_columns_base=OUTPUT_COLUMNS_ROMAN)
    sorted_roman = sort_roman_rows(roman)

    keys = [
        (str(r["tel_3"]).strip(), str(r["id_dni"]).strip(), str(r["id_producto"]).strip())
        for _, r in sorted_roman.iterrows()
    ]
    assert keys == [
        ("5491122223333", "20333444", "1001"),
        ("5491122223333", "20333445", "1003"),
        ("5491122223333", "20333446", "1001"),
        ("", "20333446", "1002"),
    ]

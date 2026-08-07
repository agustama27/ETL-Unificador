from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


BACK_BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_BASE_DIR))
from back_base_etl.planes_pivot import pivot_planes  # noqa: E402
from back_base_etl.io import iter_planes_chunks  # noqa: E402


def test_pivot_planes_orders_by_installments_and_generates_dynamic_columns() -> None:
    df = pd.DataFrame(
        [
            {"nroproducto": "1", "cajon": "M60", "deuda_total": "1000", "deuda_vencida": "200", "plan": "12", "importe_entrega": "120", "importe_cuota": "80"},
            {"nroproducto": "1", "cajon": "M60", "deuda_total": "1000", "deuda_vencida": "200", "plan": "3", "importe_entrega": "200", "importe_cuota": "300"},
            {"nroproducto": "1", "cajon": "M60", "deuda_total": "1000", "deuda_vencida": "200", "plan": "6", "importe_entrega": "150", "importe_cuota": "150"},
            {"nroproducto": "2", "cajon": "M30", "deuda_total": "500", "deuda_vencida": "100", "plan": "3", "importe_entrega": "500", "importe_cuota": "0"},
        ]
    )

    result = pivot_planes(df)

    assert result.attrs["max_plans"] == 3
    assert result.attrs["plan_columns"] == [
        "plan_1_cuotas",
        "plan_1_entrega",
        "plan_1_cuota_mensual",
        "plan_2_cuotas",
        "plan_2_entrega",
        "plan_2_cuota_mensual",
        "plan_3_cuotas",
        "plan_3_entrega",
        "plan_3_cuota_mensual",
    ]

    row_1 = result[result["nroproducto"] == "1"].iloc[0]
    assert row_1["plan_1_cuotas"] == "3"
    assert row_1["plan_2_cuotas"] == "6"
    assert row_1["plan_3_cuotas"] == "12"

    row_2 = result[result["nroproducto"] == "2"].iloc[0]
    assert row_2["plan_1_cuotas"] == "3"
    assert row_2["plan_2_cuotas"] == ""


def test_pivot_planes_excludes_can_products_and_marks_them_for_downstream_filter() -> None:
    df = pd.DataFrame(
        [
            {"nroproducto": "10", "cajon": "CAN", "deuda_total": "100", "deuda_vencida": "50", "plan": "3", "importe_entrega": "10", "importe_cuota": "30"},
            {"nroproducto": "11", "cajon": "M30", "deuda_total": "200", "deuda_vencida": "80", "plan": "2", "importe_entrega": "20", "importe_cuota": "90"},
        ]
    )

    result = pivot_planes(df)

    assert "10" not in set(result["nroproducto"])
    assert result.attrs["excluded_nroproductos_can"] == ["10"]


def test_pivot_planes_accepts_chunks_without_functional_differences() -> None:
    base_df = pd.DataFrame(
        [
            {"nroproducto": "A", "cajon": "M30", "deuda_total": "1200", "deuda_vencida": "120", "plan": "12", "importe_entrega": "200", "importe_cuota": "100"},
            {"nroproducto": "A", "cajon": "M30", "deuda_total": "1200", "deuda_vencida": "120", "plan": "6", "importe_entrega": "300", "importe_cuota": "150"},
            {"nroproducto": "B", "cajon": "M60", "deuda_total": "900", "deuda_vencida": "90", "plan": "3", "importe_entrega": "450", "importe_cuota": "200"},
            {"nroproducto": "C", "cajon": "CAN", "deuda_total": "100", "deuda_vencida": "10", "plan": "1", "importe_entrega": "100", "importe_cuota": "0"},
        ]
    )

    chunk_iterable = (
        base_df.iloc[start : start + 2].copy()
        for start in range(0, len(base_df), 2)
    )

    from_df = pivot_planes(base_df)
    from_chunks = pivot_planes(chunk_iterable)

    pd.testing.assert_frame_equal(from_df, from_chunks)
    assert from_chunks.attrs["max_plans"] == from_df.attrs["max_plans"]
    assert from_chunks.attrs["plan_columns"] == from_df.attrs["plan_columns"]
    assert from_chunks.attrs["excluded_nroproductos_can"] == from_df.attrs["excluded_nroproductos_can"]


def test_pivot_planes_large_volume_chunks_preserve_all_plan_rows() -> None:
    rows: list[dict[str, str]] = []
    products = 2000
    plans_per_product = 5

    for product_idx in range(1, products + 1):
        nroproducto = f"P{product_idx:05d}"
        for cuotas in [24, 18, 12, 6, 3]:
            rows.append(
                {
                    "nroproducto": nroproducto,
                    "cajon": "M30",
                    "deuda_total": "1500",
                    "deuda_vencida": "150",
                    "plan": str(cuotas),
                    "importe_entrega": "300",
                    "importe_cuota": "120",
                }
            )

    df = pd.DataFrame(rows)
    chunk_iterable = (
        df.iloc[start : start + 400].copy()
        for start in range(0, len(df), 400)
    )

    result = pivot_planes(chunk_iterable)

    assert len(result) == products
    assert result.attrs["max_plans"] == plans_per_product
    assert result.attrs["input_plan_rows"] == products * plans_per_product
    assert bool(result["plan_1_cuotas"].eq("3").all())
    assert bool(result["plan_5_cuotas"].eq("24").all())


def test_pivot_planes_limits_dynamic_columns_to_allowed_seven() -> None:
    df = pd.DataFrame(
        [
            {"nroproducto": "1", "cajon": "M30", "deuda_total": "1000", "deuda_vencida": "100", "plan": str(cuotas), "importe_entrega": "50", "importe_cuota": "20"}
            for cuotas in [3, 6, 9, 12, 18, 24, 36, 48, 60]
        ]
    )

    result = pivot_planes(df)
    row = result.iloc[0]

    assert result.attrs["max_plans"] == 7
    assert row["plan_1_cuotas"] == "3"
    assert row["plan_7_cuotas"] == "36"
    assert "plan_8_cuotas" not in result.columns


def test_pivot_planes_ignores_non_allowed_installments() -> None:
    df = pd.DataFrame(
        [
            {"nroproducto": "10", "cajon": "M30", "deuda_total": "500", "deuda_vencida": "50", "plan": "8", "importe_entrega": "10", "importe_cuota": "10"},
            {"nroproducto": "10", "cajon": "M30", "deuda_total": "500", "deuda_vencida": "50", "plan": "12", "importe_entrega": "10", "importe_cuota": "10"},
        ]
    )

    result = pivot_planes(df)
    row = result.iloc[0]

    assert result.attrs["max_plans"] == 1
    assert row["plan_1_cuotas"] == "12"


def test_iter_planes_chunks_streams_excel_and_pivots(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {"nroproducto": "900", "cajon": "M30", "deuda_total": "1000", "deuda_vencida": "100", "plan": "12", "importe_entrega": "100", "importe_cuota": "90"},
            {"nroproducto": "900", "cajon": "M30", "deuda_total": "1000", "deuda_vencida": "100", "plan": "6", "importe_entrega": "200", "importe_cuota": "140"},
            {"nroproducto": "901", "cajon": "M60", "deuda_total": "800", "deuda_vencida": "80", "plan": "3", "importe_entrega": "300", "importe_cuota": "200"},
        ]
    )
    workbook = tmp_path / "planes.xlsx"
    df.to_excel(workbook, sheet_name="default_1", index=False)

    chunks = list(iter_planes_chunks(str(workbook), chunk_size=2))
    assert len(chunks) == 2
    assert sum(len(chunk) for chunk in chunks) == 3

    result = pivot_planes(iter_planes_chunks(str(workbook), chunk_size=2))
    assert len(result) == 2
    row_900 = result[result["nroproducto"] == "900"].iloc[0]
    assert row_900["plan_1_cuotas"] == "6"
    assert row_900["plan_2_cuotas"] == "12"


def test_iter_planes_chunks_supports_planes_29_04_equivalent_format(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "DNI/NRODOC": "1001",
                "ENTIDAD": "PX-01",
                "CAJON_ASIGNACION_CLIENTE": "M30",
                "DEUDA_TOTAL": "1000",
                "DEUDA_VENCIDA": "150",
                "PLAN": "6",
                "IMPORTE_CUOTA": "200",
            },
            {
                "DNI/NRODOC": "1001",
                "ENTIDAD": "PX-01",
                "CAJON_ASIGNACION_CLIENTE": "M30",
                "DEUDA_TOTAL": "1000",
                "DEUDA_VENCIDA": "150",
                "PLAN": "3",
                "IMPORTE_CUOTA": "300",
            },
        ]
    )
    workbook = tmp_path / "planes_29_04.xlsx"
    df.to_excel(workbook, sheet_name="default_1", index=False)

    result = pivot_planes(iter_planes_chunks(str(workbook), chunk_size=1))
    row = result[result["nroproducto"] == "1001"].iloc[0]

    assert row["plan_1_cuotas"] == "3"
    assert row["plan_1_entrega"] == 0.0
    assert row["plan_2_cuotas"] == "6"


def test_iter_planes_chunks_defaults_importe_entrega_when_missing(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "nroproducto": "900",
                "cajon": "M30",
                "deuda_total": "1000",
                "deuda_vencida": "100",
                "plan": "3",
                "importe_cuota": "90",
            }
        ]
    )
    workbook = tmp_path / "planes_sin_entrega.xlsx"
    df.to_excel(workbook, sheet_name="default_1", index=False)

    result = pivot_planes(iter_planes_chunks(str(workbook), chunk_size=10))
    row = result.iloc[0]

    assert row["plan_1_cuotas"] == "3"
    assert row["plan_1_entrega"] == 0.0


def test_iter_planes_chunks_reports_unsupported_format_only_when_not_mappable(tmp_path: Path) -> None:
    df = pd.DataFrame([{"foo": "1", "bar": "2"}])
    workbook = tmp_path / "planes_invalid.xlsx"
    df.to_excel(workbook, sheet_name="default_1", index=False)

    with pytest.raises(ValueError, match="Unsupported PLANES format"):
        list(iter_planes_chunks(str(workbook), chunk_size=10))


def test_iter_planes_chunks_prefers_nro_doc_over_producto_for_nroproducto(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "NRO_DOC": "DU00035214453",
                "PRODUCTO": "NARANJA",
                "CAJON_ASIGNACION_CLIENTE": "M60",
                "DEUDA_TOTAL": "5000",
                "DEUDA_VENCIDA": "900",
                "PLAN": "3",
                "IMPORTE_CUOTA": "700",
            }
        ]
    )
    workbook = tmp_path / "planes_29_04_aliases.xlsx"
    df.to_excel(workbook, sheet_name="default_1", index=False)

    result = pivot_planes(iter_planes_chunks(str(workbook), chunk_size=10))

    assert list(result["nroproducto"]) == ["DU00035214453"]

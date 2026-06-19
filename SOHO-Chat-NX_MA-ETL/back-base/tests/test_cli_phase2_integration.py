from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BACK_BASE_DIR = REPO_ROOT / "back-base"
ENTRYPOINT = BACK_BASE_DIR / "etl_naranjax.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

sys.path.insert(0, str(BACK_BASE_DIR))


from back_base_etl.constants import OUTPUT_COLUMNS, OUTPUT_COLUMNS_ROMAN  # noqa: E402


def _build_input_workbook(tmp_path: Path) -> Path:
    source = FIXTURES_DIR / "input_asignacion_phase2.csv"
    df_input = pd.read_csv(source, sep=";")
    workbook = tmp_path / "input_asignacion.xlsx"
    df_input.to_excel(workbook, sheet_name="Asignacion", index=False)
    return workbook


def _build_planes_workbook(tmp_path: Path) -> Path:
    source = FIXTURES_DIR / "diario_planes_phase2.csv"
    df_planes = pd.read_csv(source, sep=";")
    workbook = tmp_path / "diario_planes.xlsx"
    df_planes.to_excel(workbook, sheet_name="default_1", index=False)
    return workbook


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENTRYPOINT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_single_output(output_dir: Path, prefix: str) -> pd.DataFrame:
    outputs = sorted(output_dir.glob(f"{prefix}*.csv"))
    assert outputs, f"No output files with prefix {prefix!r}"
    return pd.read_csv(outputs[-1], sep=";", dtype=str, keep_default_na=False)


def _as_float(value: str) -> float:
    return float(str(value).replace(",", "."))


def test_cli_phase2_with_planes_and_pagos_ignores_pagos_for_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "out_with_diarios"
    input_workbook = _build_input_workbook(tmp_path)
    planes_workbook = _build_planes_workbook(tmp_path)
    pagos_file = tmp_path / "diario_pagos_phase2.csv"
    pd.DataFrame(
        [
                {
                "nroproducto": "9999",
                "recupero": "NO",
                "tipo_pago": "PAGO_LINK",
                "importe_pago": "100",
                "cajon_actual_prod": "M10",
            }
        ]
    ).to_csv(pagos_file, sep=";", index=False, lineterminator="\n")

    run = _run_cli(
        "--input",
        str(input_workbook),
        "--output_dir",
        str(output_dir),
        "--planes",
        str(planes_workbook),
        "--pagos",
        str(pagos_file),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"CLI failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

    result = _load_single_output(output_dir, "NARANJAX_MA_ROMAN_")
    expected_renamed_plan_columns = [
        "monto_entrega_3",
        "monto_cuota_3",
        "monto_entrega_6",
        "monto_cuota_6",
    ]
    assert list(result.columns) == OUTPUT_COLUMNS_ROMAN + expected_renamed_plan_columns
    assert "recupero" not in result.columns
    assert "tipo_pago" not in result.columns
    for idx in range(1, 8):
        assert f"plan_{idx}_cuotas" not in result.columns

    assert len(result) == 2
    row = result[result["nombre_cliente"] == "Cliente Dos"].iloc[0]
    assert row["nombre_cliente"] == "Cliente Dos"
    assert _as_float(row["monto_deuda_tc"]) == 50.0
    assert _as_float(row["monto_deuda_nd"]) == 150.0
    assert _as_float(row["monto_deuda_total"]) == 200.0
    assert row["tel_1"] == ""
    assert row["tel_2"] == ""
    assert row["tel_3"] == ""
    assert row["id_dni"] == "20333444"
    assert set(result["id_producto"]) == {"1001", "1002"}
    columns = result.columns.tolist()
    tel_3_idx = columns.index("tel_3")
    id_dni_idx = columns.index("id_dni")
    id_producto_idx = columns.index("id_producto")
    assert id_dni_idx == tel_3_idx + 1
    assert id_producto_idx == id_dni_idx + 1
    assert columns.index("tipo_marca_plan") == id_producto_idx + 1
    assert row["monto_entrega_3"] == ""
    assert row["tipo_marca_plan"] == "Sin Plan"

    row_with_plan = result[result["id_producto"] == "1001"].iloc[0]
    assert _as_float(row_with_plan["monto_entrega_3"]) == 200.0
    assert _as_float(row_with_plan["monto_cuota_3"]) == 200.0
    assert row_with_plan["tipo_marca_plan"] == "Con Plan"

    actual_keys = [
        (
            (value["tel_3"] or "").strip(),
            (value["id_dni"] or "").strip(),
            (value["id_producto"] or "").strip(),
        )
        for value in result.to_dict("records")
    ]
    expected_keys = sorted(actual_keys, key=lambda key: (key[0] == "", key[0], key[1], key[2]))
    assert actual_keys == expected_keys


def test_cli_phase2_without_diarios_keeps_monthly_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "out_without_diarios"
    input_workbook = _build_input_workbook(tmp_path)

    run = _run_cli(
        "--input",
        str(input_workbook),
        "--output_dir",
        str(output_dir),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"CLI failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

    result = _load_single_output(output_dir, "NARANJAX_CARTERA_")
    assert list(result.columns) == OUTPUT_COLUMNS
    assert set(result["id_nro_producto"]) == {"1001", "1002", "1003"}

    row_1003 = result[result["id_nro_producto"] == "1003"].iloc[0]
    assert _as_float(row_1003["monto_deuda_total_ars"]) == 200.0
    assert _as_float(row_1003["monto_total_vencido_ars"]) == 20.0
    assert row_1003["tipo_cajon"] == "M30"
    assert row_1003["recupero"] == ""
    assert row_1003["tipo_pago"] == ""

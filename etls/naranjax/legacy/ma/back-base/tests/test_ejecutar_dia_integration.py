from __future__ import annotations

import subprocess
import sys
from shutil import copy2
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BACK_BASE_DIR = REPO_ROOT / "back-base"
ENTRYPOINT = BACK_BASE_DIR / "ejecutar_dia.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _build_input_workbook(tmp_path: Path) -> Path:
    source = FIXTURES_DIR / "input_asignacion_phase2.csv"
    df_input = pd.read_csv(source, sep=";")
    workbook = tmp_path / "input_asignacion.xlsx"
    df_input.to_excel(workbook, sheet_name="Asignacion", index=False)
    return workbook


def _write_pagos(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    pagos_path = tmp_path / "diario_pagos.csv"
    df_pagos = pd.DataFrame(rows)
    df_pagos.to_csv(pagos_path, sep=";", index=False, lineterminator="\n")
    return pagos_path


def _copy_fixture(fixture_name: str, destination: Path, output_name: str | None = None) -> Path:
    source = FIXTURES_DIR / fixture_name
    target = destination / (output_name or fixture_name)
    copy2(source, target)
    return target


def _write_planes_fixture_xlsx(destination: Path, output_name: str) -> Path:
    source = FIXTURES_DIR / "diario_planes_phase2.csv"
    df_planes = pd.read_csv(source, sep=";")
    target = destination / output_name
    df_planes.to_excel(target, sheet_name="default_1", index=False)
    return target


def _run_daily(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENTRYPOINT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_single_output(output_dir: Path) -> pd.DataFrame:
    outputs = sorted(output_dir.glob("NARANJAX_MA_ROMAN_*.csv"))
    assert outputs, "No ROMAN outputs generated"
    return pd.read_csv(outputs[-1], sep=";", dtype=str, keep_default_na=False)


def test_ejecutar_dia_aplica_pagos_y_mantiene_estado_sin_planes(tmp_path: Path) -> None:
    input_workbook = _build_input_workbook(tmp_path)
    diarios_dir = tmp_path / "diarios"
    diarios_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "out"
    estado_dir = tmp_path / "estados"
    logs_dir = tmp_path / "logs"
    procesados_dir = tmp_path / "procesados"

    pagos_path = _write_pagos(
        diarios_dir,
        [
            {
                "nroproducto": "1002",
                "recupero": "NO",
                "tipo_pago": "PAGO_LINK",
                "importe_pago": "100",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M90",
            }
        ],
    )

    run = _run_daily(
        "--fecha",
        "20260418",
        "--input",
        str(input_workbook),
        "--diarios_dir",
        str(diarios_dir),
        "--estado_dir",
        str(estado_dir),
        "--output_dir",
        str(output_dir),
        "--logs_dir",
        str(logs_dir),
        "--procesados_dir",
        str(procesados_dir),
        "--pagos",
        str(pagos_path),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"Daily run failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

    roman = _load_single_output(output_dir)
    assert len(roman) == 1

    estado_vigente = pd.read_csv(estado_dir / "estado_202604.csv", sep=";", dtype=str, keep_default_na=False)
    assert set(estado_vigente["nroproducto"]) == {"1002"}
    row_1002 = estado_vigente[estado_vigente["nroproducto"] == "1002"].iloc[0]
    assert row_1002["cajon"] == "M90"
    assert row_1002["recupero"] == "NO"
    assert row_1002["tipo_pago"] == "PAGO_LINK"


def test_ejecutar_dia_aplica_dt_dv_actual_y_usa_importe_pago_como_fallback(tmp_path: Path) -> None:
    input_workbook = _build_input_workbook(tmp_path)
    diarios_dir = tmp_path / "diarios"
    diarios_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "out"
    estado_dir = tmp_path / "estados"
    logs_dir = tmp_path / "logs"
    procesados_dir = tmp_path / "procesados"

    pagos_path = _write_pagos(
        diarios_dir,
        [
            {
                "nroproducto": "1002",
                "recupero": "NO",
                "tipo_pago": "PAGO_LINK",
                "importe_pago": "100",
                "dt_actual": "999",
                "dv_actual": "",
                "cajon_asig_prod": "M90",
                    "cajon_actual_prod": "M90",
            }
        ],
    )

    run = _run_daily(
        "--fecha",
        "20260418",
        "--input",
        str(input_workbook),
        "--diarios_dir",
        str(diarios_dir),
        "--estado_dir",
        str(estado_dir),
        "--output_dir",
        str(output_dir),
        "--logs_dir",
        str(logs_dir),
        "--procesados_dir",
        str(procesados_dir),
        "--pagos",
        str(pagos_path),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"Daily run failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

    estado_vigente = pd.read_csv(estado_dir / "estado_202604.csv", sep=";", dtype=str, keep_default_na=False)
    row_1002 = estado_vigente[estado_vigente["nroproducto"] == "1002"].iloc[0]
    assert row_1002["total_deuda"] == "999"
    assert row_1002["total_vencida"] == "0"

    roman = _load_single_output(output_dir)
    roman_row = roman[roman["id_producto"] == "1002"].iloc[0]
    assert roman_row["monto_deuda_total"] == "999.0"
    if "monto_deuda_vencida" in roman.columns:
        assert roman_row["monto_deuda_vencida"] == "0.0"


def test_ejecutar_dia_persiste_vigente_y_snapshot(tmp_path: Path) -> None:
    input_workbook = _build_input_workbook(tmp_path)
    diarios_dir = tmp_path / "diarios"
    diarios_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "out"
    estado_dir = tmp_path / "estados"
    logs_dir = tmp_path / "logs"
    procesados_dir = tmp_path / "procesados"

    run = _run_daily(
        "--fecha",
        "20260419",
        "--input",
        str(input_workbook),
        "--diarios_dir",
        str(diarios_dir),
        "--estado_dir",
        str(estado_dir),
        "--output_dir",
        str(output_dir),
        "--logs_dir",
        str(logs_dir),
        "--procesados_dir",
        str(procesados_dir),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"Daily run failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

    path_vigente = estado_dir / "estado_202604.csv"
    path_snapshot = estado_dir / "estado_20260419.csv"
    assert path_vigente.exists()
    assert path_snapshot.exists()

    df_vigente = pd.read_csv(path_vigente, sep=";", dtype=str, keep_default_na=False)
    df_snapshot = pd.read_csv(path_snapshot, sep=";", dtype=str, keep_default_na=False)
    pd.testing.assert_frame_equal(df_vigente, df_snapshot)


def test_ejecutar_dia_es_compatible_si_faltan_diarios(tmp_path: Path) -> None:
    input_workbook = _build_input_workbook(tmp_path)
    diarios_dir = tmp_path / "diarios"
    diarios_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "out"
    estado_dir = tmp_path / "estados"
    logs_dir = tmp_path / "logs"
    procesados_dir = tmp_path / "procesados"

    run = _run_daily(
        "--fecha",
        "20260420",
        "--input",
        str(input_workbook),
        "--diarios_dir",
        str(diarios_dir),
        "--estado_dir",
        str(estado_dir),
        "--output_dir",
        str(output_dir),
        "--logs_dir",
        str(logs_dir),
        "--procesados_dir",
        str(procesados_dir),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"Daily run failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

    roman = _load_single_output(output_dir)
    assert "recupero" not in roman.columns
    assert "tipo_pago" not in roman.columns
    assert len(roman) == 1
    assert set(roman["nombre_cliente"]) == {"Cliente Dos"}
    assert set(roman["id_dni"]) == {"20333444"}
    assert set(roman["id_producto"]) == {"1002"}
    columns = roman.columns.tolist()
    assert columns.index("id_dni") == columns.index("tel_4") + 1
    assert columns.index("id_producto") == columns.index("id_dni") + 1


def test_ejecutar_dia_crea_log_y_copia_insumos_en_exito(tmp_path: Path) -> None:
    input_workbook = _build_input_workbook(tmp_path)
    diarios_dir = tmp_path / "diarios"
    diarios_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "out"
    estado_dir = tmp_path / "estados"
    logs_dir = tmp_path / "logs"
    procesados_dir = tmp_path / "procesados"

    planes_path = diarios_dir / "planes_20260421.xlsx"
    pd.DataFrame(
        [
            {
                "nroproducto": "1002",
                "cajon": "M90",
                "deuda_total": "1200",
                "deuda_vencida": "200",
                "plan": "3",
                "importe_entrega": "200",
                "importe_cuota": "400",
            }
        ]
    ).to_excel(planes_path, sheet_name="default_1", index=False)
    pagos_path = _write_pagos(
        diarios_dir,
        [
            {
                "nroproducto": "1002",
                "recupero": "NO",
                "tipo_pago": "PAGO_LINK",
                "cajon_asig_prod": "M90",
                "cajon_actual_prod": "M90",
            }
        ],
    )

    run = _run_daily(
        "--fecha",
        "20260421",
        "--input",
        str(input_workbook),
        "--diarios_dir",
        str(diarios_dir),
        "--estado_dir",
        str(estado_dir),
        "--output_dir",
        str(output_dir),
        "--logs_dir",
        str(logs_dir),
        "--procesados_dir",
        str(procesados_dir),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"Daily run failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

    log_file = logs_dir / "20260421.log"
    assert log_file.exists()
    log_content = log_file.read_text(encoding="utf-8")
    assert "Starting daily execution fecha=20260421 mes=202604" in log_content
    assert "Daily summary -" in log_content
    assert "Finished daily execution fecha=20260421 status=success" in log_content

    copied_dir = procesados_dir / "20260421"
    assert copied_dir.exists()
    assert planes_path.exists()
    assert pagos_path.exists()
    assert (copied_dir / "planes_20260421.xlsx").exists()
    assert (copied_dir / "diario_pagos.csv").exists()


def test_ejecutar_dia_aplica_transformaciones_solo_en_salida_roman(tmp_path: Path) -> None:
    input_workbook = _build_input_workbook(tmp_path)
    diarios_dir = tmp_path / "diarios"
    diarios_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "out"
    estado_dir = tmp_path / "estados"
    logs_dir = tmp_path / "logs"
    procesados_dir = tmp_path / "procesados"

    planes_path = diarios_dir / "planes_20260421.xlsx"
    pd.DataFrame(
        [
            {
                "nroproducto": "1002",
                "cajon": "M90",
                "deuda_total": "1200",
                "deuda_vencida": "200",
                "plan": "3",
                "importe_entrega": "200",
                "importe_cuota": "400",
            }
        ]
    ).to_excel(planes_path, sheet_name="default_1", index=False)

    run = _run_daily(
        "--fecha",
        "20260421",
        "--input",
        str(input_workbook),
        "--diarios_dir",
        str(diarios_dir),
        "--estado_dir",
        str(estado_dir),
        "--output_dir",
        str(output_dir),
        "--logs_dir",
        str(logs_dir),
        "--procesados_dir",
        str(procesados_dir),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"Daily run failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

    roman = _load_single_output(output_dir)
    for idx in range(1, 8):
        assert f"plan_{idx}_cuotas" not in roman.columns
    assert "monto_entrega_3" in roman.columns
    assert "monto_cuota_3" in roman.columns
    assert set(roman["plan_ok"]) <= {"si", "no"}

    estado_vigente = pd.read_csv(estado_dir / "estado_202604.csv", sep=";", dtype=str, keep_default_na=False)
    assert "plan_1_entrega" in estado_vigente.columns
    assert "plan_1_cuota_mensual" in estado_vigente.columns
    assert "monto_entrega_3" not in estado_vigente.columns
    assert "monto_cuota_3" not in estado_vigente.columns


def test_ejecutar_dia_con_pagos_invalido_no_falla_por_columnas_default(tmp_path: Path) -> None:
    input_workbook = _build_input_workbook(tmp_path)
    diarios_dir = tmp_path / "diarios"
    diarios_dir.mkdir(parents=True, exist_ok=True)
    output_dir = tmp_path / "out"
    estado_dir = tmp_path / "estados"
    logs_dir = tmp_path / "logs"
    procesados_dir = tmp_path / "procesados"

    pagos_invalido = diarios_dir / "pagos_invalido.csv"
    pagos_invalido.write_text("nroproducto;otro\n1001;X\n", encoding="utf-8")

    run = _run_daily(
        "--fecha",
        "20260422",
        "--input",
        str(input_workbook),
        "--diarios_dir",
        str(diarios_dir),
        "--estado_dir",
        str(estado_dir),
        "--output_dir",
        str(output_dir),
        "--logs_dir",
        str(logs_dir),
        "--procesados_dir",
        str(procesados_dir),
        "--pagos",
        str(pagos_invalido),
        cwd=REPO_ROOT,
    )

    assert run.returncode == 0, f"Daily run failed\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}"

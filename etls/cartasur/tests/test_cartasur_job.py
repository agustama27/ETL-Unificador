"""Runs the real legacy pipeline through the unified job wrapper."""

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("pandas")
pytest.importorskip("holidays")

WORKSPACE = Path(__file__).resolve().parents[3]
LEGACY = WORKSPACE / "etls/cartasur/legacy"
WRAPPER = WORKSPACE / "etls/cartasur/job.py"

HEADERS = ["CUIL", "NOMBRE APELLIDO", "NRO DE DOCUMENTO", "NRO DE PRODUCTO",
           "NRO DE CUOTA", "SALDO EXIGIBLE", "DIAS DE MORA",
           "CANTIDAD DE CUOTAS A VENCER", "SEGURO DESCRIPCION",
           "IMPORTE A ABONAR POR SEGURO", "TELEFONO CLIENTE"]


def _write_input(tmp_path: Path) -> Path:
    path = tmp_path / "base.csv"
    rows = [
        ["20123456786", "CLIENTE SINTETICO", "12345678", "P001", "3",
         "1500,50", "5", "2", "SEGURO DE VIDA", "100,00", "3517710632"],
        ["27222333440", "OTRO CLIENTE", "22233344", "P002", "1",
         "800,00", "20", "1", "", "0", "3514400185"],
    ]
    lines = [";".join(HEADERS)] + [";".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return path


def _run(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WRAPPER), *arguments],
        cwd=LEGACY, capture_output=True, text=True, timeout=300,
    )


def test_job_generates_roman_and_e1kia_in_sandbox_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "run" / "output"
    output_dir.mkdir(parents=True)

    result = _run(["--input", str(_write_input(tmp_path)),
                   "--output_dir", str(output_dir)])

    stamp = date.today().strftime("%y%m%d")
    roman = output_dir / f"CARTA_SUR_ROMAN_{stamp}.csv"
    e1kia = output_dir / f"CARTA_SUR_E1KIA_{stamp}.csv"
    assert result.returncode == 0, result.stderr or result.stdout
    assert roman.exists() and roman.stat().st_size > 0
    assert e1kia.exists()
    assert e1kia.read_text(encoding="utf-8").splitlines()[0] == "tel_fijo;tel_celular"
    assert (output_dir / "validation_report.csv").exists()
    assert not (LEGACY / "out").exists()


def test_job_fails_fast_on_missing_required_column(tmp_path: Path) -> None:
    path = tmp_path / "base.csv"
    headers = [name for name in HEADERS if name != "CUIL"]
    path.write_text(";".join(headers) + "\n" + ";".join(["x"] * len(headers)) + "\n",
                    encoding="utf-8-sig")
    output_dir = tmp_path / "run" / "output"
    output_dir.mkdir(parents=True)

    result = _run(["--input", str(path), "--output_dir", str(output_dir)])

    assert result.returncode == 1
    assert "Error" in result.stderr

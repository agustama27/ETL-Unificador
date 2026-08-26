"""Runs the real legacy pipeline through the unified job wrapper."""

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("pandas")
pytest.importorskip("pypdf")
pytest.importorskip("xlrd")
xlwt = pytest.importorskip("xlwt")
pytest.importorskip("reportlab")

WORKSPACE = Path(__file__).resolve().parents[3]
LEGACY = WORKSPACE / "etls/alvarezmaquinarias/legacy"
WRAPPER = WORKSPACE / "etls/alvarezmaquinarias/job.py"


def _sample_inputs(tmp_path: Path) -> Path:
    sys.path.insert(0, str(LEGACY))
    try:
        from scripts.generate_sample_data import generate_sample_data
        return generate_sample_data(tmp_path, date.today())
    finally:
        sys.path.remove(str(LEGACY))


def _run(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WRAPPER), *arguments],
        cwd=LEGACY, capture_output=True, text=True, timeout=300,
    )


def test_job_generates_roman_and_e1kia_in_sandbox_output(tmp_path: Path) -> None:
    inputs = _sample_inputs(tmp_path)
    output_dir = tmp_path / "run" / "output"
    output_dir.mkdir(parents=True)

    result = _run(["--input", str(inputs / "saldos.xls"),
                   "--maquinarias", str(inputs / "maquinarias.xlsx"),
                   "--servicios", str(inputs / "servicios.xlsx"),
                   "--repuestos", str(inputs / "repuestos.pdf"),
                   "--output_dir", str(output_dir)])

    stamp = date.today().strftime("%y%m%d")
    roman = output_dir / f"ALVAREZ_MAQUINARIAS_ROMAN_{stamp}.csv"
    e1kia = output_dir / f"ALVAREZ_MAQUINARIAS_E1KIA_{stamp}.csv"
    assert result.returncode == 0, result.stderr
    assert roman.exists() and roman.stat().st_size > 0
    assert e1kia.exists()
    assert e1kia.read_text(encoding="utf-8").splitlines()[0] == "TelefonoCliente"
    assert sorted(item.name for item in output_dir.iterdir()) == [e1kia.name, roman.name]
    assert not (LEGACY / "outputs").exists()


def test_job_fails_fast_on_missing_input(tmp_path: Path) -> None:
    inputs = _sample_inputs(tmp_path)
    output_dir = tmp_path / "run" / "output"
    output_dir.mkdir(parents=True)

    result = _run(["--input", str(inputs / "no-existe.xls"),
                   "--maquinarias", str(inputs / "maquinarias.xlsx"),
                   "--servicios", str(inputs / "servicios.xlsx"),
                   "--repuestos", str(inputs / "repuestos.pdf"),
                   "--output_dir", str(output_dir)])

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert tuple(output_dir.iterdir()) == ()

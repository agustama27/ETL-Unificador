"""Runs the real legacy tabla-integradora pipeline through job_base.py."""

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("pandas")
pytest.importorskip("yaml")

WORKSPACE = Path(__file__).resolve().parents[3]
LEGACY = WORKSPACE / "etls/petersen/legacy_base"
WRAPPER = WORKSPACE / "etls/petersen/job_base.py"

DAY = "20260721"


def _write_inputs(tmp_path: Path) -> Path:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / f"{DAY}_AG002_BSFC3BUC_INTEGRACION.csv").write_text(
        "DAT3;NOMBRE;TEL1;TEL2;TEL3;TEL4\n"
        "1001;CLIENTE SINTETICO;3517710632;3514400185;;\n"
        "1002;OTRO CLIENTE;3512223344;;;\n",
        encoding="latin-1")
    (incoming / f"{DAY}_AG002_BSFC3BUC_PRODCLI_DEELO.csv").write_text(
        "NUMERO CLIENTE;TIPO DE PRODUCTO;DEUDA VENCIDA;SUCURSAL\n"
        "1001;PRESTAMO;5000;1\n"
        "1001;TARJETA;1200;1\n"
        "1002;PRESTAMO;800;2\n",
        encoding="latin-1")
    (incoming / f"{DAY}_AG002_BSFC3BUC_MAILCLI.xls").write_text(
        "NUMERO CLIENTE\tRAZON SOCIAL\tEMAIL\n"
        "1001\tCLIENTE SINTETICO\tcliente@sintetico.com\n",
        encoding="latin-1")
    return incoming


def _run(arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(WRAPPER), *arguments],
        cwd=LEGACY, capture_output=True, text=True, timeout=600,
    )


def test_job_generates_the_five_artifacts_in_sandbox_output(tmp_path: Path) -> None:
    incoming = _write_inputs(tmp_path)
    output_dir = tmp_path / "run" / "output"
    output_dir.mkdir(parents=True)

    result = _run(["--input", str(incoming), "--output_dir", str(output_dir)])

    assert result.returncode == 0, result.stderr or result.stdout
    produced = sorted(item.name for item in output_dir.iterdir())
    assert len(produced) == 5, produced
    tabla = next(name for name in produced if name.startswith("tabla_integradora_"))
    assert f"_{DAY}_" in tabla
    content = (output_dir / tabla).read_text(encoding="utf-8-sig")
    assert "1001" in content
    telefonos_txt = next(name for name in produced
                         if name.startswith("telefonos_petersen_2"))
    assert "+549" in (output_dir / telefonos_txt).read_text(encoding="utf-8-sig")
    assert not (LEGACY / "data").exists()


def test_job_fails_fast_when_no_recognizable_files(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "cualquiera.csv").write_text("A;B\n1;2\n", encoding="utf-8")
    output_dir = tmp_path / "run" / "output"
    output_dir.mkdir(parents=True)

    result = _run(["--input", str(incoming), "--output_dir", str(output_dir)])

    assert result.returncode == 1
    assert "Error" in result.stderr
    assert tuple(output_dir.iterdir()) == ()

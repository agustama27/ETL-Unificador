import csv
import subprocess
import sys
from pathlib import Path

import pytest


WORKSPACE = Path(__file__).resolve().parents[3]
WRAPPER = WORKSPACE / "etls/encuestacx/job.py"
LEGACY = WORKSPACE / "etls/encuestacx/legacy"

INPUT_COLUMNS = [
    "Tier", "Cliente", "Gerencia Cliente", "Vertical de negocio", "Nombre",
    "Apellido", "Puesto", "Referente", "Jerarquia", "Mail", "Teléfono",
    "Provincia", "País", "Evoltis: Referente operativo",
    "Evoltis: Referente de negocio",
]
OUTPUT_COLUMNS = [
    "Status de encuesta", "Tier", "cliente", "Gerencia Cliente",
    "Vertical de negocio", "customer_name", "Puesto", "Referente",
    "Jerarquia", "Mail", "phone number", "Provincia", "País",
    "Evoltis: Referente operativo", "Evoltis: Referente de negocio",
]


def _run(input_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WRAPPER), "--input", str(input_path),
         "--output_dir", str(output_dir)],
        cwd=LEGACY, capture_output=True, text=True, check=False,
    )


def _write_input(tmp_path: Path) -> Path:
    pandas = pytest.importorskip("pandas")
    path = tmp_path / "encuesta.xlsx"
    frame = pandas.DataFrame([{
        "Tier": "Premium", "Cliente": "Cliente Sintetico", "Gerencia Cliente": "G",
        "Vertical de negocio": "Banca", "Nombre": "Carolina", "Apellido": "Aguirre",
        "Puesto": "Head", "Referente": "R", "Jerarquia": "Senior",
        "Mail": "c@sintetico.com", "Teléfono": "+54 9 351 771-0632",
        "Provincia": "Córdoba", "País": "Argentina",
        "Evoltis: Referente operativo": "Op", "Evoltis: Referente de negocio": "Biz",
    }], columns=INPUT_COLUMNS)
    frame.to_excel(path, index=False)
    return path


def test_valid_input_generates_both_csvs_in_sandbox(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)
    output = run_dir / "output"

    result = _run(_write_input(tmp_path), output)

    assert result.returncode == 0, result.stderr or result.stdout
    standard = output / "base_encuesta.csv"
    e164 = output / "base_encuesta_e164.csv"
    assert standard.exists() and e164.exists()
    with standard.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0].keys()) == OUTPUT_COLUMNS
    assert rows[0]["customer_name"] == "Carolina Aguirre"
    assert rows[0]["phone number"] == "5493517710632"
    assert "+5493517710632" in e164.read_text(encoding="utf-8-sig")


def test_missing_input_fails_like_legacy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "logs").mkdir(parents=True)

    result = _run(tmp_path / "ausente.xlsx", run_dir / "output")

    assert result.returncode == 1

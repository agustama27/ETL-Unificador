import csv
import subprocess
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
WRAPPER = WORKSPACE / "adapters/petersen/gestiones_job.py"
LEGACY = WORKSPACE / "soho-petersen-cobranzas-resultados"
AG002 = ["AG002_45.csv", "AG002_46.csv", "AG002_47.csv", "AG002_48.csv"]


def _run(input_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WRAPPER), "--input", str(input_path),
         "--output_dir", str(output_dir)],
        cwd=LEGACY, capture_output=True, text=True, check=False,
    )


def _write_input(tmp_path: Path, *, banks: list[str]) -> Path:
    path = tmp_path / "roman.csv"
    manana = (date.today() + timedelta(days=1)).strftime("%d/%m/%Y")
    base = {
        "[Salida] EFECTO": "PROMESA DE PAGO", "[Salida] MONTO PROMESA": "4500",
        "[Salida] FECHA PROMESA": manana, "[Salida] CANAL DE PAGO": "CAJA",
        "[Salida] MOTIVO ATRASO": "DESEMPLEO",
        "[Salida] OBSERVACIONES GESTION": "ok",
        "[Salida] OBSERVACIONES PROMESA": "ok",
        "[Entrada] Sucursal": "1", "[Entrada] Nro Producto": "P01",
        "[Entrada] Producto": "PRESTAMO", "[Entrada] Deuda Vencida": "5000",
    }
    rows = []
    for index, bank in enumerate(banks, start=1):
        row = dict(base)
        row["[Salida] BANCO GESTIONADO"] = bank
        row["[Entrada] Nro Cliente"] = str(1000 + index)
        rows.append(row)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_four_bank_roman_produces_complete_ag002_zip(tmp_path: Path) -> None:
    output = tmp_path / "run" / "output"
    output.mkdir(parents=True)
    banks = ["Santa Fe", "Entre Ríos", "Santa Cruz", "San Juan"]

    result = _run(_write_input(tmp_path, banks=banks), output)

    assert result.returncode == 0, result.stderr or result.stdout
    zip_path = next(output.glob("Gestiones_Petersen_*.zip"))
    with zipfile.ZipFile(zip_path) as archive:
        assert archive.namelist() == AG002


def test_missing_bank_fails_fast_before_publishing(tmp_path: Path) -> None:
    output = tmp_path / "run" / "output"
    output.mkdir(parents=True)

    result = _run(_write_input(tmp_path, banks=["Santa Fe"]), output)

    assert result.returncode == 1
    assert "AG002" in result.stderr
    assert not list(output.glob("*.zip"))

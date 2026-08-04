import csv
import subprocess
import sys
from datetime import date
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
WRAPPER = WORKSPACE / "adapters/epec/base_job.py"
LEGACY = WORKSPACE / "soho-EPEC"


def _run(input_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WRAPPER), "--input", str(input_path),
         "--output_dir", str(output_dir)],
        cwd=LEGACY, capture_output=True, text=True, check=False,
    )


def _write_input(tmp_path: Path, *, drop: str | None = None) -> Path:
    path = tmp_path / "base.csv"
    row = {
        "SUMINISTRO": "S001", "CONTRATO": "C001", "RAZON_SOCIAL": "CLIENTE SINTETICO",
        "BARRIO": "CENTRO", "DIRECCION": "CALLE FALSA 123",
        "FECHA_EJECUCION": "01/08/2026", "TELEFONO": "3514400185",
        "TELEFONO_CELULAR": "3517710632", "MOTIVO": "CORTE",
        "MEDIDOR": "M123", "ORD_FECHA_FIN": "02/08/2026",
    }
    if drop:
        row.pop(drop)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    return path


def test_valid_input_generates_roman_and_e1kia(tmp_path: Path) -> None:
    output = tmp_path / "run" / "output"
    output.mkdir(parents=True)

    result = _run(_write_input(tmp_path), output)

    assert result.returncode == 0, result.stderr or result.stdout
    today = date.today().strftime("%y%m%d")
    roman = output / f"EPEC_ROMAN_{today}.csv"
    e1kia = output / f"EPEC_E1KIA_{today}.csv"
    assert roman.exists() and e1kia.exists()
    assert "nombre_cliente" in roman.read_text("utf-8", errors="replace").splitlines()[0]
    assert not list(LEGACY.glob(f"back-base/base-generada/EPEC_*_{today}.csv"))


def test_missing_required_column_fails_fast(tmp_path: Path) -> None:
    output = tmp_path / "run" / "output"
    output.mkdir(parents=True)

    result = _run(_write_input(tmp_path, drop="SUMINISTRO"), output)

    assert result.returncode == 1
    assert "Error" in result.stderr


def test_missing_input_fails_fast(tmp_path: Path) -> None:
    result = _run(tmp_path / "ausente.csv", tmp_path / "run" / "output")

    assert result.returncode == 1

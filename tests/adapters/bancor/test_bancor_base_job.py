import csv
import subprocess
import sys
from datetime import date
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
WRAPPER = WORKSPACE / "adapters/bancor/base_job.py"
LEGACY = WORKSPACE / "soho-bancor-cobranzas-etl"


def _run(input_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(WRAPPER), "--input", str(input_path),
         "--output_dir", str(output_dir)],
        cwd=LEGACY, capture_output=True, text=True, check=False,
    )


def _write_input(tmp_path: Path, *, modulo: str = "201") -> Path:
    path = tmp_path / "base.csv"
    row = {
        "Cliente_BT": "BT001", "CUIL": "20123456789", "NumeroDocumento": "12345678",
        "ClienteNombre": "CLIENTE SINTETICO", "NumeroTelefono": "3517710632",
        "NumeroTrabajo": "", "NumeroCelular": "3517710633", "Mail": "x@sintetico.com",
        "Nro Cuenta": "100200", "Cuenta": "CA", "Sucursal_Cuenta": "1",
        "AgrupadorProducto": "Tarjeta", "Campana_Ref": "C1", "Tipo_Asignacion": "A",
        "Gestion_Descripcion": "", "ModuloCodigo": modulo, "NumeroOperacion": "OP1",
        "Dias_Mora": "30", "MontoAdeudado": "1000,50", "MontoVencido": "500,25",
        "SaldoCapital": "800", "InteresAdeudado": "100", "IVAInteresAdeudado": "21",
        "OFERTA_Importe": "900,00", "Tasa_40": "0,4",
        "Gestion_Estado": "01. Sin gestion", "Fecha_Gestion": "01/08/2026",
        "Estado Cuenta": "Activa",
    }
    with path.open("w", encoding="latin-1", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row), delimiter=";")
        writer.writeheader()
        writer.writerow(row)
    return path


def test_valid_input_generates_all_four_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    output = run_dir / "output"
    output.mkdir(parents=True)

    result = _run(_write_input(tmp_path), output)

    assert result.returncode == 0, result.stderr or result.stdout
    today_ddmmyyyy = date.today().strftime("%d%m%Y")
    today_yyyymmdd = date.today().strftime("%Y%m%d")
    assert (output / "con-filtros" / f"base_bancor_{today_ddmmyyyy}.csv").exists()
    assert (output / "con-filtros" / f"telefonos_x_cliente_{today_ddmmyyyy}.csv").exists()
    assert (output / "sin-filtros" / f"BANCOR_ROMAN_{today_yyyymmdd}.csv").exists()
    assert (output / "sin-filtros" / f"BANCOR_E1KIA_{today_yyyymmdd}_sinestrategia.csv").exists()
    roman = (output / "sin-filtros" / f"BANCOR_ROMAN_{today_yyyymmdd}.csv").read_text("utf-8", errors="replace")
    assert "id_cliente_bt" in roman.splitlines()[0]
    assert not list(LEGACY.glob(f"back-base/base-generada/*/base_bancor_{today_ddmmyyyy}.csv"))


def test_filtered_out_module_fails_fast_without_partial_success(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    output = run_dir / "output"
    output.mkdir(parents=True)

    result = _run(_write_input(tmp_path, modulo="999"), output)

    assert result.returncode == 1
    assert "Error" in result.stderr


def test_missing_input_fails_like_legacy(tmp_path: Path) -> None:
    result = _run(tmp_path / "ausente.csv", tmp_path / "run" / "output")

    assert result.returncode == 1

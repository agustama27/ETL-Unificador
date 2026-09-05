import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest


WORKSPACE = Path(__file__).resolve().parents[3]
WRAPPER = WORKSPACE / "etls/bancor/job.py"
LEGACY = WORKSPACE / "etls/bancor/legacy"


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
        "PreVenta": "APLICA OFERTA", "OFERTA_PREVENTA": "700,00", "BanconUsr": "Activo",
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


# --- Campania OFERTA_PREVENTA y contrato ROMAN de 32 columnas -------------------
#
# Upstream: soho-bancor-cobranzas-etl @ feature/oferta-preventa-bancor (deb2cb0..d6e3990).

CONTRATO_ROMAN = [
    "id_cliente_bt", "id_cuil", "id_nro_documento", "customer_name",
    "tel_fijo", "tel_laboral", "tel_celular", "txt_mail",
    "id_nro_cuenta", "tipo_cuenta", "id_sucursal_cuenta", "tipo_campana_ref",
    "tipo_asignacion", "txt_gestion_descripcion", "tipo_estado_cuenta", "fecha_gestion",
    "monto_adeudado_ars", "monto_entrega_ars", "oferta_importe", "resumen_productos",
    "cnt_dias_mora_max", "aplica_quita", "monto_quita_ars", "fecha_limite_quita",
    "oferta_preventa", "monto_total_preventa", "alcance_preventa",
    "tipo_tna_refi_preventa", "medio_pago_preventa", "fecha_limite_preventa",
    "tipo_bancon_usr", "monto_vencido_ars",
]

DERIVADAS_PREVENTA = [
    "monto_total_preventa", "alcance_preventa", "tipo_tna_refi_preventa",
    "medio_pago_preventa", "fecha_limite_preventa",
]


def _write_input_multiproducto(tmp_path: Path) -> Path:
    """Dos productos bajo el mismo CUIL: ejercita la consolidacion por grupo."""
    path = tmp_path / "base_multiproducto.csv"
    row = {
        "Cliente_BT": "BT001", "CUIL": "20123456789", "NumeroDocumento": "12345678",
        "ClienteNombre": "CLIENTE SINTETICO", "NumeroTelefono": "3517710632",
        "NumeroTrabajo": "", "NumeroCelular": "3517710633", "Mail": "x@sintetico.com",
        "Nro Cuenta": "100200", "Cuenta": "CA", "Sucursal_Cuenta": "1",
        "AgrupadorProducto": "Tarjeta", "Campana_Ref": "30", "Tipo_Asignacion": "A",
        "Gestion_Descripcion": "", "ModuloCodigo": "201", "NumeroOperacion": "OP1",
        "Dias_Mora": "400", "MontoAdeudado": "1000,50", "MontoVencido": "500,25",
        "SaldoCapital": "800", "InteresAdeudado": "100", "IVAInteresAdeudado": "21",
        "OFERTA_Importe": "900,00", "Tasa_40": "0,4",
        "Gestion_Estado": "01. Sin gestion", "Fecha_Gestion": "01/08/2026",
        "Estado Cuenta": "Activa",
        "PreVenta": "APLICA OFERTA", "OFERTA_PREVENTA": "700,00", "BanconUsr": "Activo",
    }
    segundo = dict(row, **{
        "Nro Cuenta": "100201", "NumeroOperacion": "OP2", "Dias_Mora": "600",
        "MontoAdeudado": "2000,00", "MontoVencido": "300,00", "OFERTA_PREVENTA": "800,00",
    })
    with path.open("w", encoding="latin-1", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row), delimiter=";")
        writer.writeheader()
        writer.writerow(row)
        writer.writerow(segundo)
    return path


def _roman_rows(output: Path) -> list[dict[str, str]]:
    """Filas de BANCOR_ROMAN_*.csv. Se parsea con csv: hay campos entrecomillados."""
    name = f"BANCOR_ROMAN_{date.today().strftime('%Y%m%d')}.csv"
    with (output / "sin-filtros" / name).open(encoding="utf-8", errors="replace",
                                              newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def _run_ok(tmp_path: Path, source: Path) -> Path:
    output = tmp_path / "run" / "output"
    output.mkdir(parents=True)
    result = _run(source, output)
    assert result.returncode == 0, result.stderr or result.stdout
    return output


def test_roman_emite_el_contrato_de_32_columnas(tmp_path: Path) -> None:
    """24 -> 32 columnas: las originales conservan posicion, las 8 nuevas van al final."""
    output = _run_ok(tmp_path, _write_input(tmp_path))

    assert list(_roman_rows(output)[0]) == CONTRATO_ROMAN


def test_monto_vencido_ars_se_consolida_sumando_por_cuil(tmp_path: Path) -> None:
    """Es dato a nivel producto: se suma, no se toma de la primera fila del grupo."""
    output = _run_ok(tmp_path, _write_input_multiproducto(tmp_path))

    filas = _roman_rows(output)
    assert len(filas) == 1
    # 500,25 (OP1) + 300,00 (OP2). Tomar grupo.iloc[0] daria 500.25.
    assert float(filas[0]["monto_vencido_ars"]) == 800.25


def test_preventa_cumple_las_invariantes_del_contrato(tmp_path: Path) -> None:
    """Las invariantes de `validar_contrato_roman`, sea cual sea el lado de la vigencia.

    No fija el valor de `oferta_preventa`: depende de la fecha de corrida y de que la
    fila sea elegible. Fija la relacion entre columnas, que no depende del calendario.
    """
    output = _run_ok(tmp_path, _write_input_multiproducto(tmp_path))

    fila = _roman_rows(output)[0]
    assert fila["oferta_preventa"] in {"si", "no"}

    if fila["oferta_preventa"] == "si":
        assert fila["monto_total_preventa"]
        assert fila["alcance_preventa"] in {"total", "parcial"}
        assert fila["fecha_limite_preventa"]
        assert fila["medio_pago_preventa"] == "cupon"
        adeudado = float(fila["monto_adeudado_ars"])
        assert float(fila["monto_total_preventa"]) <= adeudado
    else:
        assert all(fila[columna] == "" for columna in DERIVADAS_PREVENTA)


def test_monto_vencido_puede_superar_al_adeudado_sin_romper_el_pipeline(
    tmp_path: Path,
) -> None:
    """La invariante vencido <= adeudado NO se cumple en la base real (34 %).

    Esta implementada como advertencia a proposito. Este test fija ese contrato:
    una fila incoherente sale por la salida normal, con exit 0.
    """
    source = tmp_path / "incoherente.csv"
    base = _write_input(tmp_path).read_text(encoding="latin-1").splitlines()
    header, fila = base[0], base[1].replace(";1000,50;500,25;", ";100,00;500,25;")
    source.write_text(f"{header}\n{fila}\n", encoding="latin-1", newline="")

    fila_roman = _roman_rows(_run_ok(tmp_path, source))[0]

    assert float(fila_roman["monto_vencido_ars"]) > float(fila_roman["monto_adeudado_ars"])


def _base_generator():
    """El modulo legacy, importado como lo hace `job.py`."""
    sys.path.insert(0, str(LEGACY / "back-base" / "procesos"))
    import base_generator  # noqa: PLC0415

    return base_generator


def test_vigencia_de_preventa_se_evalua_contra_la_fecha_de_corrida() -> None:
    """La campania se apaga sola despues del 30/09/2026 (ADR-001).

    Las fechas van FIJAS a proposito: un test que dependa de `date.today()` empieza a
    dar otro resultado el 01/10/2026 sin que nadie toque una linea.
    """
    base_generator = _base_generator()

    assert base_generator.campania_preventa_vigente(date(2026, 9, 5)) is True
    assert base_generator.campania_preventa_vigente(date(2026, 9, 30)) is True
    assert base_generator.campania_preventa_vigente(date(2026, 10, 1)) is False


@pytest.mark.xfail(
    reason="Hueco del upstream: `procesar_base_completa` emite las 8 columnas nuevas "
           "pero no incluye PreVenta/OFERTA_PREVENTA/BanconUsr en `columnas_seleccionadas`, "
           "asi que el grupo llega sin ellas y `oferta_preventa` sale siempre 'no'. "
           "Reproducido identico en soho-bancor-cobranzas-etl@feature/oferta-preventa-bancor: "
           "no es un defecto del port. Escalado al upstream; cuando lo arreglen esto pasa a "
           "XPASS y hay que sacar el marker.",
    strict=True,
)
def test_la_salida_sin_filtros_activa_la_campania_preventa(tmp_path: Path) -> None:
    """RF-1 sobre la salida ROMAN sin-filtros, que es la unica que corre el Unificador."""
    output = _run_ok(tmp_path, _write_input_multiproducto(tmp_path))

    fila = _roman_rows(output)[0]
    assert fila["oferta_preventa"] == "si"
    assert fila["monto_total_preventa"] == "1500.00"
    assert fila["tipo_bancon_usr"] == "Activo"

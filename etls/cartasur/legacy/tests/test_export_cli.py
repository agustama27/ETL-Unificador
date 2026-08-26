from __future__ import annotations

import csv
import os
import subprocess
import sys
from datetime import date

from cartasur_etl.cli import run
from cartasur_etl.config import load_config
from cartasur_etl.export import collect_e1kia_phones, write_dynamic_csv, write_e1kia_phone_csv


FIXTURE = "tests/fixtures/CabeceraconDatos.xlsx"
MARTINEZ_TXT_PRODUCTOS = "[Producto 6590651 Saldo:224200.00 CuotasAVencer:5 NroCuota:8 ; Producto 6683756 Saldo:163000.00 CuotasAVencer:13 NroCuota:3 ; Producto 6720729 Saldo:137100.00 CuotasAVencer:12 NroCuota:1 ; Producto 6703038 Saldo:114400.00 CuotasAVencer:14 NroCuota:2]"


def test_writer_format_order_lf_no_bom(tmp_path):
    cfg = load_config()
    path = tmp_path / "out.csv"
    write_dynamic_csv([{column: "" for column in cfg["output_columns"]}], path, cfg["output_columns"])
    data = path.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in data
    header = data.decode("utf-8").split("\n", 1)[0]
    assert header == ",".join(cfg["output_columns"])


def test_e1kia_writer_format_dedupes_and_prefers_cellular(tmp_path):
    path = tmp_path / "phones.csv"
    records = [
        {"tel_cliente": "(011) 2233-4455", "tel_fijo": "54 11 2233 4455"},
        {"tel_cliente": "5491122334455"},
        {"tel_fijo": "01144445555"},
        {"tel_cliente": "0000"},
        {"tel_cliente": ""},
    ]

    write_e1kia_phone_csv(records, path)

    data = path.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in data
    assert data.decode("utf-8").splitlines() == [
        "tel_fijo;tel_celular",
        "541144445555;5491122334455",
    ]


def test_e1kia_collection_writes_uneven_phone_lists_with_blanks(tmp_path):
    path = tmp_path / "phones.csv"

    write_e1kia_phone_csv(
        [
            {"tel_fijo": "1122223333"},
            {"tel_fijo": "1133334444"},
            {"tel_cliente": "5491144445555"},
        ],
        path,
    )

    assert path.read_text(encoding="utf-8").splitlines() == [
        "tel_fijo;tel_celular",
        "541122223333;5491144445555",
        "541133334444;",
    ]


def test_e1kia_collects_current_tel_cliente_as_cellular():
    fixed, cellular = collect_e1kia_phones([{"tel_cliente": "5491121743961"}])

    assert fixed == []
    assert cellular == ["5491121743961"]


def test_e1kia_collects_current_tel_cliente_as_fixed_when_prefixed_54():
    fixed, cellular = collect_e1kia_phones([{"tel_cliente": "542204920449"}])

    assert fixed == ["542204920449"]
    assert cellular == []


def test_cli_run_deterministic_outputs(tmp_path):
    result = run(FIXTURE, tmp_path, run_date=date(2026, 6, 22))
    csv_path = tmp_path / "CARTA_SUR_ROMAN_260622.csv"
    e1kia_path = tmp_path / "CARTA_SUR_E1KIA_260622.csv"
    assert result["paths"]["csv"] == csv_path
    assert result["paths"]["e1kia_csv"] == e1kia_path
    assert csv_path.exists()
    assert e1kia_path.exists()
    assert (tmp_path / "validation_report.csv").exists()
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    martinez = next(row for row in rows if row["id_cuil"] == "27289872804")
    assert martinez["monto_total_ars"] == "638700.00"
    assert martinez["fecha_limite_sistema"] == "2026-06-25"
    assert martinez["txt_productos"] == MARTINEZ_TXT_PRODUCTOS


def test_product_detail_csv_round_trip(tmp_path):
    run(FIXTURE, tmp_path, run_date=date(2026, 6, 22))
    csv_path = tmp_path / "CARTA_SUR_ROMAN_260622.csv"

    with csv_path.open(encoding="utf-8", newline="") as fh:
        martinez = next(row for row in csv.DictReader(fh) if row["id_cuil"] == "27289872804")

    assert "," not in martinez["txt_productos"]
    assert _parse_product_detail(martinez["txt_productos"]) == [
        {"producto": "6590651", "saldo": "224200.00", "cuotas": "5", "nro_cuota": "8"},
        {"producto": "6683756", "saldo": "163000.00", "cuotas": "13", "nro_cuota": "3"},
        {"producto": "6720729", "saldo": "137100.00", "cuotas": "12", "nro_cuota": "1"},
        {"producto": "6703038", "saldo": "114400.00", "cuotas": "14", "nro_cuota": "2"},
    ]


def test_cli_module_smoke(tmp_path):
    env = {**os.environ, "PYTHONPATH": "src"}
    completed = subprocess.run(
        [sys.executable, "-m", "cartasur_etl.cli", "--input", FIXTURE, "--output-dir", str(tmp_path), "--run-date", "2026-06-22"],
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    assert "CARTA_SUR_ROMAN_260622.csv" in completed.stdout
    assert "CARTA_SUR_E1KIA_260622.csv" in completed.stdout


def _parse_product_detail(value: str) -> list[dict[str, str]]:
    assert value.startswith("[") and value.endswith("]")
    inner = value[1:-1]
    if not inner:
        return []
    parsed = []
    for segment in inner.split(" ; "):
        product_label, product, saldo, cuotas, nro_cuota = segment.split(" ")
        assert product_label == "Producto"
        parsed.append(
            {
                "producto": product,
                "saldo": saldo.removeprefix("Saldo:"),
                "cuotas": cuotas.removeprefix("CuotasAVencer:"),
                "nro_cuota": nro_cuota.removeprefix("NroCuota:"),
            }
        )
    return parsed

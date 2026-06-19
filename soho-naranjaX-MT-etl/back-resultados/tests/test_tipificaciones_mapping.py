from __future__ import annotations

import csv
from pathlib import Path

from back_resultados_etl.cleaners import format_fecha_compromiso, truncate_observaciones
from back_resultados_etl.constants import TIPIF_MAP
from back_resultados_etl.io import load_input, save_output
from back_resultados_etl.logcall import build_logcall_input
from back_resultados_etl.transformers import transform


def test_tipif_map_all_keys_present() -> None:
    assert TIPIF_MAP["LOGCALL"] == "26"
    assert TIPIF_MAP["PROMESA_DE_PAGO"] == "12"
    assert TIPIF_MAP["DIFICULTAD_DE_PAGO"] == "47"
    assert TIPIF_MAP["SIN_VOLUNTAD_DE_PAGO"] == "17"
    assert TIPIF_MAP["NO_RECONOCE_DEUDA"] == "15"
    assert TIPIF_MAP["MANIFIESTA_PAGO"] == "37"
    assert TIPIF_MAP["NOTIFICADO_TITULAR"] == "8"
    assert TIPIF_MAP["NOTIFICADO_FAMILIAR"] == "8"
    assert TIPIF_MAP["CONOCE_TITULAR"] == "8"
    assert TIPIF_MAP["NO_RESPONDE"] == "7"
    assert TIPIF_MAP["CONTESTADOR"] == "29"
    assert TIPIF_MAP["FALLECIDO"] == "16"
    assert TIPIF_MAP["NO_ES_TITULAR"] == "61"
    assert TIPIF_MAP["MENSAJE"] == "28"


def test_save_output_contract(tmp_path: Path) -> None:
    out = save_output(
        [
            {
                "DNI": "123",
                "TIPIFICACION": "12",
                "NROPRODUCTO": "X",
                "FECHA_PROMESA": "20261225",
                "MONTO_PROMESA": "1000",
                "CALL_REFID": "ABC",
                "OBSERVACIONES": "ok",
            }
        ],
        tmp_path,
    )
    data = out.read_bytes()
    text = data.decode("cp1252")
    first = text.split("\n", 1)[0]
    assert first.count("|") == 39
    assert first.split("|")[2] == "NARANJA"
    assert first.split("|")[7] == "USUOLOS"
    assert "\r\n" not in text


def test_truncate_observaciones_sanitize() -> None:
    value = 'hola "" con | y \\ final'
    out = truncate_observaciones(value, max_chars=1500)
    assert '""' not in out
    assert "|" not in out
    assert "\\" not in out


def test_load_input_missing_required_columns(tmp_path: Path) -> None:
    p = tmp_path / "input.csv"
    p.write_text("foo,bar\n1,2\n", encoding="utf-8")
    try:
        load_input(p)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Missing required source columns" in str(exc)


def test_logcall_with_cruce_and_phone_fallback(tmp_path: Path) -> None:
    logcall = tmp_path / "LOGCALL_input.csv"
    with logcall.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["CALLREFID", "PHONE"])
        writer.writeheader()
        writer.writerow({"CALLREFID": "A1", "PHONE": "5491122334455"})
        writer.writerow({"CALLREFID": "A2", "PHONE": "5491199988877"})

    cruce = tmp_path / "cruce.csv"
    with cruce.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["call_refid", "id_cliente", "id_nro_producto", "msisdn"])
        writer.writeheader()
        writer.writerow({"call_refid": "A1", "id_cliente": "30111222", "id_nro_producto": "P1", "msisdn": ""})
        writer.writerow({"call_refid": "", "id_cliente": "30999999", "id_nro_producto": "P2", "msisdn": "5491199988877"})

    rows = build_logcall_input(logcall, cruce)
    by_ref = {r["call_refid"]: r for r in rows}
    assert by_ref["A1"]["id_cliente"] == "30111222"
    assert by_ref["A2"]["id_cliente"] == "30999999"


def test_fecha_format_strict_ddmmyy() -> None:
    assert format_fecha_compromiso("25/12/26") == "20261225"
    assert format_fecha_compromiso("25/12/2026") == ""


def test_transform_basic_metrics() -> None:
    rows, metrics = transform(
        [
            {
                "call_id": "1",
                "call_refid": "1",
                "id_cliente": "30111222",
                "tipificaciones": "Promesa de pago",
                "observaciones": "ok",
                "fecha_compromiso_tc": "25/12/26",
                "fecha_compromiso_nd": "",
                "monto_compromiso": "100",
                "id_nro_producto": "P1",
            }
        ]
    )
    assert len(rows) == 1
    assert metrics["total_input_rows"] == 1
    assert metrics["total_output_rows"] == 1

from __future__ import annotations

from datetime import date

import pandas as pd

from cartasur_etl.config import load_config
from cartasur_etl.ingest import read_workbook
from cartasur_etl.normalize import (
    add_business_days,
    due_date_for_mora,
    is_business_day,
    normalize_customers,
    normalize_name,
    normalize_phone,
)
from cartasur_etl.transform import _decimal, group_customers
from cartasur_etl.validate import validate_records


FIXTURE = "tests/fixtures/CabeceraconDatos.xlsx"
MARTINEZ_TXT_PRODUCTOS = "[Producto 6590651 Saldo:224200.00 CuotasAVencer:5 NroCuota:8 ; Producto 6683756 Saldo:163000.00 CuotasAVencer:13 NroCuota:3 ; Producto 6720729 Saldo:137100.00 CuotasAVencer:12 NroCuota:1 ; Producto 6703038 Saldo:114400.00 CuotasAVencer:14 NroCuota:2]"


def _martinez_record():
    cfg = load_config()
    rows = read_workbook(FIXTURE, cfg)
    grouped = group_customers(rows, cfg)
    normalized = normalize_customers(grouped, cfg, date(2026, 6, 22))
    return next(record for record in normalized if record["id_cuil"] == "27289872804"), cfg


def test_martinez_regression_totals_exclude_insurance():
    record, _ = _martinez_record()
    assert record["monto_saldo_exigible_ars"] == "638700.00"
    assert record["cnt_cuotas_a_vencer"] == "44"
    assert record["cnt_dias_mora"] == "21"
    assert record["monto_seguro_ars"] == "5500.00"
    assert record["monto_total_ars"] == "638700.00"
    assert record["cnt_productos"] == "4"


def test_martinez_product_detail_golden_case_and_ignores_insurance():
    record, _ = _martinez_record()
    assert record["txt_productos"] == MARTINEZ_TXT_PRODUCTOS
    assert "Orígenes" not in record["txt_productos"]
    assert record["monto_seguro_ars"] == "5500.00"
    assert record["txt_seguro_descripcion"] == "Orígenes - Bolso Protegido CartaSur"


def test_single_product_detail_contains_one_segment():
    cfg = load_config()
    normalized = normalize_customers(group_customers(_rows([_loan(product="222", saldo="10", cuotas="2", nro_cuota="1")]), cfg), cfg, date(2026, 6, 22))

    assert normalized[0]["txt_productos"] == "[Producto 222 Saldo:10.00 CuotasAVencer:2 NroCuota:1]"


def test_insurance_only_customer_has_empty_product_detail():
    cfg = load_config()
    normalized = normalize_customers(group_customers(_rows([_insurance()]), cfg), cfg, date(2026, 6, 22))

    assert normalized[0]["txt_productos"] == "[]"
    assert normalized[0]["cnt_productos"] == "0"


def test_loan_row_with_embedded_insurance_preserves_insurance_and_product_detail():
    cfg = load_config()
    loan_with_insurance = _loan(product="222", saldo="1000", cuotas="2", nro_cuota="1")
    loan_with_insurance.update(
        {
            "seguro_descripcion": "Bolso Protegido CartaSur",
            "importe_seguro": "11400",
            "row_type": "LOAN",
        }
    )

    normalized = normalize_customers(group_customers(_rows([loan_with_insurance]), cfg), cfg, date(2026, 7, 13))

    assert normalized[0]["monto_saldo_exigible_ars"] == "1000.00"
    assert normalized[0]["monto_total_ars"] == "1000.00"
    assert normalized[0]["monto_seguro_ars"] == "11400.00"
    assert normalized[0]["txt_seguro_descripcion"] == "Bolso Protegido CartaSur"
    assert normalized[0]["txt_productos"] == "[Producto 222 Saldo:1000.00 CuotasAVencer:2 NroCuota:1]"


def test_missing_product_detail_fields_render_null_and_warn():
    cfg = load_config()
    normalized = normalize_customers(group_customers(_rows([_loan(cuotas="", nro_cuota="abc")]), cfg), cfg, date(2026, 6, 22))
    valid, issues = validate_records(normalized, cfg)

    assert valid == normalized
    assert normalized[0]["txt_productos"] == "[Producto 111 Saldo:100.00 CuotasAVencer:null NroCuota:null]"
    assert any(issue.code == "PRODUCT_DETAIL_MISSING_CUOTAS_A_VENCER" and issue.action == "KEEP_WITH_NULL" for issue in issues)
    assert any(issue.code == "PRODUCT_DETAIL_MISSING_NRO_CUOTA" and issue.action == "KEEP_WITH_NULL" for issue in issues)


def test_decimal_parser_keeps_decimal_dot_and_accepts_comma():
    assert _decimal("1234.50") == _decimal("1.234,50")


def test_name_phone_and_sunday_only_date_math():
    cfg = load_config()
    assert normalize_name("godoy GODOY BRUNO GUSTAVO", cfg) == "Godoy Bruno Gustavo"
    assert normalize_phone("1564408594", cfg) == "5491564408594"
    assert normalize_phone("0111564408594", cfg) == "5491164408594"
    assert normalize_phone("01144445555", cfg) == "541144445555"
    assert normalize_phone("44445555", cfg) == "5444445555"
    assert normalize_phone("2204920449", cfg) == "542204920449"
    assert normalize_phone("5491122334455", cfg) == "5491122334455"
    assert normalize_phone("541122334455", cfg) == "541122334455"
    assert add_business_days(date(2026, 6, 22), 3, ["SUNDAY"]).isoformat() == "2026-06-25"


def test_local_numbers_use_default_area_only_when_configured():
    cfg = load_config()
    cfg["phone"] = {**cfg["phone"], "default_area_code": "11"}

    assert normalize_phone("1564408594", cfg) == "5491164408594"
    assert normalize_phone("44445555", cfg) == "541144445555"


def test_ambiguous_ten_digit_phone_policy_can_keep_value():
    cfg = load_config()
    cfg["phone"] = {**cfg["phone"], "ambiguous_10_digit_policy": "keep"}

    assert normalize_phone("2204920449", cfg) == "2204920449"


def test_configured_holiday_is_skipped_in_payment_limit_date():
    cfg = load_config()
    cfg["date"] = {**cfg["date"], "exclude_holidays": ["2026-01-05"]}

    assert due_date_for_mora(21, date(2026, 1, 2), cfg).isoformat() == "2026-01-07"


def test_pre_mora_before_due_day_uses_current_month_day_10():
    cfg = load_config()

    assert due_date_for_mora(5, date(2026, 6, 5), cfg).isoformat() == "2026-06-10"


def test_pre_mora_after_due_day_uses_current_month_day_10():
    cfg = load_config()

    assert due_date_for_mora(5, date(2026, 8, 11), cfg).isoformat() == "2026-08-10"


def test_pre_mora_after_due_day_in_december_stays_current_month():
    cfg = load_config()

    assert due_date_for_mora(5, date(2025, 12, 11), cfg).isoformat() == "2025-12-10"


def test_pre_mora_due_day_on_sunday_moves_to_next_business_day():
    cfg = load_config()

    assert due_date_for_mora(5, date(2026, 5, 5), cfg).isoformat() == "2026-05-11"


def test_pre_mora_due_day_on_argentina_holiday_moves_to_next_business_day():
    cfg = load_config()

    assert due_date_for_mora(5, date(2026, 7, 5), cfg).isoformat() == "2026-07-11"


def test_pre_mora_current_month_due_day_on_sunday_moves_to_next_business_day_even_after_due_day():
    cfg = load_config()

    assert due_date_for_mora(5, date(2027, 1, 11), cfg).isoformat() == "2027-01-11"


def test_mora_temprana_skips_argentina_holiday():
    cfg = load_config()

    assert due_date_for_mora(21, date(2026, 7, 7), cfg).isoformat() == "2026-07-13"


def test_mora_temprana_does_not_skip_saturday():
    cfg = load_config()

    assert due_date_for_mora(21, date(2026, 6, 10), cfg).isoformat() == "2026-06-13"


def test_mora_temprana_crosses_year_and_skips_new_year_holiday():
    cfg = load_config()

    assert due_date_for_mora(21, date(2026, 12, 30), cfg).isoformat() == "2027-01-04"


def test_normalized_system_limit_is_populated_for_supported_mora_only():
    cfg = load_config()
    normalized = normalize_customers(
        [
            {"cnt_dias_mora": 5},
            {"cnt_dias_mora": 21},
            {"cnt_dias_mora": 0},
        ],
        cfg,
        date(2026, 6, 22),
    )

    assert [record["tipo_tramo_mora"] for record in normalized] == [
        "PRE_MORA",
        "MORA_TEMPRANA",
        "SIN_MORA",
    ]
    assert [record["fecha_limite_sistema"] for record in normalized] == [
        "2026-06-10",
        "2026-06-25",
        "",
    ]


def test_argentina_holidays_are_detected_as_non_business_days():
    cfg = load_config()

    assert not is_business_day(date(2026, 7, 9), cfg["date"])


def test_validate_excludes_mora_above_30_and_warns_assumptions():
    cfg = load_config()
    record, _ = _martinez_record()
    record = {**record, "cnt_dias_mora": "31", "tipo_tramo_mora": "FUERA_DE_ALCANCE"}
    valid, issues = validate_records([record], cfg)
    assert valid == []
    assert any(issue.code == "MORA_OUT_OF_SCOPE" and issue.action == "NO_CALL" for issue in issues)
    assert any(issue.code.startswith("ASSUMPTION_") for issue in issues)


def _rows(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _loan(product: str = "111", saldo: str = "100", cuotas: str = "1", nro_cuota: str = "1") -> dict:
    return {
        "id_cuil": "20123456789",
        "customer_name": "CLIENTE PRUEBA",
        "id_documento": "12345678",
        "id_producto": product,
        "nro_cuota": nro_cuota,
        "saldo_exigible": saldo,
        "dias_mora": "5",
        "cuotas_a_vencer": cuotas,
        "seguro_descripcion": "",
        "importe_seguro": "",
        "tel_cliente": "1122334455",
        "source_row_number": 2,
        "row_type": "LOAN",
    }


def _insurance() -> dict:
    row = _loan(product="", saldo="", cuotas="", nro_cuota="")
    row.update(
        {
            "seguro_descripcion": "Seguro Test",
            "importe_seguro": "50",
            "row_type": "INSURANCE",
        }
    )
    return row

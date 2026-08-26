from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import holidays


def normalize_customers(customers: list[dict], config: dict, run_date: date) -> list[dict]:
    return [normalize_customer(customer, config, run_date) for customer in customers]


def normalize_customer(customer: dict, config: dict, run_date: date) -> dict:
    mora = int(customer.get("cnt_dias_mora") or 0)
    record = {
        "id_llamada": build_call_id(customer.get("id_cuil", ""), run_date, config),
        "id_cuil": only_digits(customer.get("id_cuil", "")),
        "id_documento": only_digits(customer.get("id_documento", "")),
        "customer_name": normalize_name(customer.get("customer_name_raw", ""), config),
        "tel_cliente": normalize_phone(customer.get("tel_cliente_raw", ""), config),
        "monto_saldo_exigible_ars": format_money(customer.get("monto_saldo_exigible_ars", Decimal("0"))),
        "monto_seguro_ars": format_money(customer.get("monto_seguro_ars", Decimal("0"))),
        "monto_total_ars": format_money(customer.get("monto_total_ars", Decimal("0"))),
        "cnt_dias_mora": str(mora),
        "cnt_cuotas_a_vencer": str(int(customer.get("cnt_cuotas_a_vencer") or 0)),
        "cnt_productos": str(int(customer.get("cnt_productos") or 0)),
        "txt_seguro_descripcion": str(customer.get("txt_seguro_descripcion", "")),
        "txt_productos_detalle": str(customer.get("txt_productos_detalle", "")),
        "txt_productos": str(customer.get("txt_productos", "[]")),
        "tipo_tramo_mora": tramo_for_mora(mora, config),
        "fecha_hoy": run_date.isoformat(),
        "fecha_limite_sistema": due_date_for_mora(mora, run_date, config).isoformat() if mora > 0 else "",
        "source_rows": customer.get("source_rows", []),
        "product_detail_warnings": customer.get("product_detail_warnings", []),
        "assumptions": customer.get("assumptions", []),
    }
    return record


def normalize_name(value: object, config: dict) -> str:
    tokens = re.sub(r"\s+", " ", str(value or "").strip()).split(" ")
    if len(tokens) >= 2 and config.get("name", {}).get("dedupe_initial_duplicate_token", False):
        if tokens[0].casefold() == tokens[1].casefold():
            tokens = tokens[1:]
    text = " ".join(tokens)
    return text.title() if config.get("name", {}).get("title_case", True) else text


def normalize_phone(value: object, config: dict) -> str:
    digits = only_digits(value)
    if not digits:
        return ""
    phone_config = config["phone"]
    prefixes = sorted(phone_config.get("preserve_existing_country_prefixes", []), key=len, reverse=True)
    if any(digits.startswith(str(prefix)) for prefix in prefixes):
        return digits

    if phone_config.get("canonical_mobile_international", True):
        domestic_mobile = _normalize_domestic_mobile_with_trunk(digits, phone_config)
        if domestic_mobile:
            return domestic_mobile

    if digits.startswith("0") and phone_config.get("remove_leading_zero", True):
        digits = digits[1:]
        if len(digits) == 10:
            return f"{phone_config['default_fixed_country_prefix']}{digits}"

    mobile_prefixes = tuple(str(prefix) for prefix in phone_config.get("local_mobile_prefixes", []))
    default_area_code = str(phone_config.get("default_area_code", ""))
    if digits.startswith(mobile_prefixes):
        subscriber = _remove_first_matching_prefix(digits, mobile_prefixes)
        if phone_config.get("canonical_mobile_international", True) and default_area_code:
            return f"{phone_config['default_mobile_country_prefix']}{default_area_code}{subscriber}"
        return f"{phone_config['default_mobile_country_prefix']}{digits}"

    if len(digits) == 8 and default_area_code:
        return f"{phone_config['default_fixed_country_prefix']}{default_area_code}{digits}"

    if len(digits) == 10:
        policy = phone_config.get("ambiguous_10_digit_policy", "fixed")
        if policy == "fixed":
            return f"{phone_config['default_fixed_country_prefix']}{digits}"
        return digits

    if phone_config.get("assume_all_are_mobile", False):
        return f"{phone_config['default_mobile_country_prefix']}{digits}"

    return f"{phone_config['default_fixed_country_prefix']}{digits}"


def _normalize_domestic_mobile_with_trunk(digits: str, phone_config: dict) -> str:
    if not digits.startswith("0"):
        return ""
    national = digits[1:]
    mobile_prefixes = tuple(str(prefix) for prefix in phone_config.get("local_mobile_prefixes", []))
    for area_len in (2, 3, 4):
        area_code = national[:area_len]
        local = national[area_len:]
        if local.startswith(mobile_prefixes):
            subscriber = _remove_first_matching_prefix(local, mobile_prefixes)
            if len(area_code) + len(subscriber) == 10:
                return f"{phone_config['default_mobile_country_prefix']}{area_code}{subscriber}"
    return ""


def _remove_first_matching_prefix(value: str, prefixes: tuple[str, ...]) -> str:
    for prefix in sorted(prefixes, key=len, reverse=True):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def only_digits(value: object) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def format_money(value: object) -> str:
    decimal = value if isinstance(value, Decimal) else Decimal(str(value or "0"))
    return str(decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def tramo_for_mora(mora: int, config: dict) -> str:
    tramo = config["tramo"]
    if tramo["pre_mora_min"] <= mora <= tramo["pre_mora_max"]:
        return "PRE_MORA"
    if tramo["mora_temprana_min"] <= mora <= tramo["mora_temprana_max"]:
        return "MORA_TEMPRANA"
    if mora > tramo["out_of_scope_above"]:
        return "FUERA_DE_ALCANCE"
    return "SIN_MORA"


def due_date_for_mora(mora: int, run_date: date, config: dict) -> date:
    tramo = config["tramo"]
    date_config = config["date"]
    if tramo["pre_mora_min"] <= mora <= tramo["pre_mora_max"]:
        return next_business_day(
            pre_mora_due_date(run_date, int(date_config["pre_mora_due_day"])),
            date_config,
        )
    if tramo["mora_temprana_min"] <= mora <= tramo["mora_temprana_max"]:
        return add_business_days(
            run_date,
            int(date_config["mora_temprana_days_to_add"]),
            date_config,
        )
    return run_date


def pre_mora_due_date(run_date: date, due_day: int) -> date:
    return run_date.replace(day=due_day)


def add_business_days(
    start: date,
    days: int,
    date_config_or_exclude_weekdays: dict | list[str],
    exclude_holidays: list[object] | None = None,
) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if is_business_day(current, date_config_or_exclude_weekdays, exclude_holidays):
            added += 1
    return current


def next_business_day(candidate: date, date_config: dict) -> date:
    current = candidate
    while not is_business_day(current, date_config):
        current += timedelta(days=1)
    return current


def is_business_day(
    candidate: date,
    date_config_or_exclude_weekdays: dict | list[str],
    exclude_holidays: list[object] | None = None,
) -> bool:
    if isinstance(date_config_or_exclude_weekdays, dict):
        exclude_weekdays = date_config_or_exclude_weekdays.get("exclude_weekdays", [])
        configured_holidays = date_config_or_exclude_weekdays.get("exclude_holidays", [])
    else:
        exclude_weekdays = date_config_or_exclude_weekdays
        configured_holidays = exclude_holidays or []

    excluded_weekdays = {getattr(calendar, name.upper()) for name in exclude_weekdays}
    configured_holiday_dates = {_parse_holiday(value) for value in configured_holidays}
    argentina_holidays = holidays.country_holidays("AR", years=[candidate.year])

    return (
        candidate.weekday() not in excluded_weekdays
        and candidate not in configured_holiday_dates
        and candidate not in argentina_holidays
    )


def _parse_holiday(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def build_call_id(id_cuil: str, run_date: date, config: dict) -> str:
    if config.get("id_llamada", {}).get("strategy") == "CUIL_YYYYMMDD":
        return f"{only_digits(id_cuil)}_{run_date:%Y%m%d}"
    return f"{only_digits(id_cuil)}_{run_date:%Y%m%d}"

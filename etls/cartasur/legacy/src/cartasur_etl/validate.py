from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Issue:
    severity: str
    scope: str
    id_cuil: str
    row_number: str
    code: str
    message: str
    raw_value: str
    action: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


REPORT_COLUMNS = ["severity", "scope", "id_cuil", "row_number", "code", "message", "raw_value", "action"]


def validate_records(records: list[dict], config: dict) -> tuple[list[dict], list[Issue]]:
    valid: list[dict] = []
    issues: list[Issue] = []
    assumptions = config.get("assumptions") or {}
    for record in records:
        record_issues: list[Issue] = []
        id_cuil = record.get("id_cuil", "")
        row_number = ";".join(str(v) for v in record.get("source_rows", []))
        if len(id_cuil) != 11:
            record_issues.append(_issue("ERROR", record, row_number, "INVALID_CUIL", "CUIL must have 11 digits", id_cuil, "DISCARD"))
        if not record.get("customer_name"):
            record_issues.append(_issue("ERROR", record, row_number, "MISSING_NAME", "Name is required", "", "DISCARD"))
        if _money(record.get("monto_total_ars")) <= Decimal("0") or int(record.get("cnt_productos") or 0) < 1:
            record_issues.append(_issue("ERROR", record, row_number, "NO_POSITIVE_LOAN_BALANCE", "Customer needs at least one loan with positive balance", record.get("monto_total_ars", ""), "DISCARD"))
        if int(record.get("cnt_dias_mora") or 0) > int(config["tramo"]["out_of_scope_above"]):
            record_issues.append(_issue("ERROR", record, row_number, "MORA_OUT_OF_SCOPE", "Mora greater than 30 is no-call", record.get("cnt_dias_mora", ""), "NO_CALL"))
        if not record.get("tel_cliente"):
            record_issues.append(_issue("WARNING", record, row_number, "PHONE_NOT_NORMALIZABLE", "Phone is missing or not normalizable", "", "KEEP_WITH_EMPTY_PHONE"))
        for warning in record.get("product_detail_warnings", []):
            record_issues.append(
                _issue(
                    "WARNING",
                    record,
                    warning.get("row_number", row_number),
                    warning.get("code", "PRODUCT_DETAIL_WARNING"),
                    warning.get("message", "Product detail warning"),
                    warning.get("raw_value", ""),
                    "KEEP_WITH_NULL",
                )
            )
        for key, message in assumptions.items():
            record_issues.append(_issue("WARNING", record, row_number, f"ASSUMPTION_{key.upper()}", message, "", "REVIEW"))

        issues.extend(record_issues)
        blocking = [issue for issue in record_issues if issue.severity == "ERROR"]
        if not blocking:
            valid.append(record)
    return valid, issues


def _issue(severity: str, record: dict, row_number: str, code: str, message: str, raw_value: object, action: str) -> Issue:
    return Issue(severity, "customer", record.get("id_cuil", ""), row_number, code, message, str(raw_value or ""), action)


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")

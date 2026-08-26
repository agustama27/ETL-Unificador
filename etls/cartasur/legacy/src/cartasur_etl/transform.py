from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd


def group_customers(rows: pd.DataFrame, config: dict) -> list[dict]:
    customers: list[dict] = []
    for id_cuil, group in rows.groupby("id_cuil", dropna=False, sort=True):
        loan_rows = group[group["row_type"] == "LOAN"]
        insurance_rows = group[group["row_type"] == "INSURANCE"]
        rows_with_insurance = group[group["seguro_descripcion"].astype(str).str.strip().ne("") & group["importe_seguro"].astype(str).str.strip().ne("")]
        first = _first_non_empty_row(group)
        loan_balances = [_decimal(v) for v in loan_rows["saldo_exigible"].tolist()]
        insurance_amounts = [_decimal(v) for v in rows_with_insurance["importe_seguro"].tolist()]
        mora_values = [_int(v) for v in loan_rows["dias_mora"].tolist() if _is_int(v)]
        cuotas_values = [_int(v) for v in loan_rows["cuotas_a_vencer"].tolist() if _is_int(v)]
        products = [str(v).strip() for v in loan_rows["id_producto"].tolist() if str(v).strip()]
        insurance_descriptions = _unique_non_empty(rows_with_insurance["seguro_descripcion"].tolist())
        txt_productos, product_detail_warnings = _build_product_detail(loan_rows)

        saldo = sum(loan_balances, Decimal("0"))
        seguro = sum(insurance_amounts, Decimal("0"))
        customers.append(
            {
                "id_cuil": str(id_cuil).strip(),
                "id_documento": first.get("id_documento", ""),
                "customer_name_raw": first.get("customer_name", ""),
                "tel_cliente_raw": first.get("tel_cliente", ""),
                "monto_saldo_exigible_ars": saldo,
                "monto_seguro_ars": seguro,
                "monto_total_ars": saldo,
                "cnt_dias_mora": max(mora_values) if mora_values else 0,
                "cnt_cuotas_a_vencer": sum(cuotas_values),
                "cnt_productos": len(products),
                "txt_seguro_descripcion": ";".join(insurance_descriptions),
                "txt_productos_detalle": ";".join(products),
                "txt_productos": txt_productos,
                "product_detail_warnings": product_detail_warnings,
                "source_rows": group["source_row_number"].tolist(),
                "row_types": group["row_type"].tolist(),
                "assumptions": list((config.get("assumptions") or {}).keys()),
            }
        )
    return customers


def _first_non_empty_row(group: pd.DataFrame) -> dict:
    for _, row in group.iterrows():
        if row.get("customer_name") or row.get("id_documento") or row.get("tel_cliente"):
            return row.to_dict()
    return group.iloc[0].to_dict() if len(group) else {}


def _decimal(value: object) -> Decimal:
    text = str(value).strip() if value is not None else ""
    if not text:
        return Decimal("0")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def _build_product_detail(loan_rows: pd.DataFrame) -> tuple[str, list[dict[str, str]]]:
    if loan_rows.empty:
        return "[]", []

    products: list[dict[str, object]] = []
    warnings: list[dict[str, str]] = []
    for _, row in loan_rows.iterrows():
        nro_producto = str(row.get("id_producto", "")).strip()
        saldo = _decimal(row.get("saldo_exigible", ""))
        cuotas_raw = row.get("cuotas_a_vencer", "")
        nro_cuota_raw = row.get("nro_cuota", "")
        cuotas = _nullable_int(cuotas_raw)
        nro_cuota = _nullable_int(nro_cuota_raw)
        row_number = str(row.get("source_row_number", ""))

        if cuotas is None:
            warnings.append(
                {
                    "code": "PRODUCT_DETAIL_MISSING_CUOTAS_A_VENCER",
                    "message": "Product detail CuotasAVencer is missing or not an integer",
                    "raw_value": str(cuotas_raw or ""),
                    "row_number": row_number,
                }
            )
        if nro_cuota is None:
            warnings.append(
                {
                    "code": "PRODUCT_DETAIL_MISSING_NRO_CUOTA",
                    "message": "Product detail NroCuota is missing or not an integer",
                    "raw_value": str(nro_cuota_raw or ""),
                    "row_number": row_number,
                }
            )

        products.append(
            {
                "nro_producto": nro_producto,
                "saldo": saldo,
                "cuotas": cuotas,
                "nro_cuota": nro_cuota,
            }
        )

    products.sort(key=lambda product: (-product["saldo"], str(product["nro_producto"])))
    segments = [
        " ".join(
            [
                f"Producto {product['nro_producto']}",
                f"Saldo:{_format_money(product['saldo'])}",
                f"CuotasAVencer:{_format_nullable_int(product['cuotas'])}",
                f"NroCuota:{_format_nullable_int(product['nro_cuota'])}",
            ]
        )
        for product in products
    ]
    return f"[{(' ; ').join(segments)}]", warnings


def _nullable_int(value: object) -> int | None:
    try:
        text = str(value).strip()
        if not text:
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


def _format_nullable_int(value: object) -> str:
    return "null" if value is None else str(int(value))


def _format_money(value: object) -> str:
    decimal = value if isinstance(value, Decimal) else Decimal(str(value or "0"))
    return str(decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _is_int(value: object) -> bool:
    try:
        int(str(value).strip())
        return True
    except (TypeError, ValueError):
        return False


def _int(value: object) -> int:
    return int(str(value).strip())


def _unique_non_empty(values: list[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result

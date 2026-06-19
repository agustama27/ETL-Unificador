"""Constants used across Naranja X ETL modules."""

from __future__ import annotations

INPUT_SHEET_NAME = "Asignacion"
INPUT_SHEET_ALIASES = (
    "Asignacion",
    "Asignación",
    "ASIGNACION",
)
INPUT_COLUMN_COUNT = 21
INPUT_USECOLS = list(range(INPUT_COLUMN_COUNT))

INPUT_COLUMNS = [
    "dni",
    "nombre_apellido",
    "deuda_vencida_tc",
    "deuda_vencida_nd",
    "total_vencida",
    "deuda_total_tc",
    "deuda_total_nd",
    "total_deuda",
    "estrategia",
    "nroproducto",
    "marca_plan",
    "telefono1",
    "telefono2",
    "telefono3",
    "telefono4",
    "email1",
    "email2",
    "email3",
    "cajon",
    "ecosistema",
    "asignacion",
]

# Header aliases for the base mensual sheet. Mapping canonical name -> tuple of
# accepted aliases. Aliases are matched after normalization (lowercase, accents
# stripped, non-alphanumerics removed). Centralized here so future schema drift
# (operators renaming or inserting columns) can be fixed in one place.
INPUT_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "dni": ("dni", "nrodoc", "nro_doc", "dni_nrodoc", "numero_documento", "documento", "id_dni", "id_nro_dni"),
    "nombre_apellido": ("nombre_apellido", "nombre_y_apellido", "nombre y apellido", "nombre", "customer_name", "nombre_cliente"),
    "deuda_vencida_tc": ("deuda_vencida_tc", "deuda vencida tc", "monto_deuda_vencida_tc", "monto_deuda_vencida_tc_ars"),
    "deuda_vencida_nd": ("deuda_vencida_nd", "deuda vencida nd", "monto_deuda_vencida_nd", "monto_deuda_vencida_nd_ars"),
    "total_vencida": ("total_vencida", "deuda_vencida", "deuda vencida", "monto_total_vencido", "monto_total_vencido_ars"),
    "deuda_total_tc": ("deuda_total_tc", "deuda total tc", "monto_deuda_total_tc", "monto_deuda_total_tc_ars"),
    "deuda_total_nd": ("deuda_total_nd", "deuda total nd", "monto_deuda_total_nd", "monto_deuda_total_nd_ars"),
    "total_deuda": ("total_deuda", "deuda_total", "deuda total", "monto_deuda_total", "monto_deuda_total_ars"),
    "estrategia": ("estrategia", "tipo_estrategia"),
    "nroproducto": ("nroproducto", "nro_producto", "producto", "id_producto"),
    "marca_plan": ("marca_plan", "tipo_marca_plan", "marca"),
    "telefono1": ("telefono1", "telefono_1", "tel1", "tel_1", "celular1", "celular_1"),
    "telefono2": ("telefono2", "telefono_2", "tel2", "tel_2", "celular2", "celular_2"),
    "telefono3": ("telefono3", "telefono_3", "tel3", "tel_3", "celular3", "celular_3"),
    "telefono4": ("telefono4", "telefono_4", "tel4", "tel_4", "celular4", "celular_4"),
    "email1": ("email1", "email_1", "mail1", "mail_1"),
    "email2": ("email2", "email_2", "mail2", "mail_2"),
    "email3": ("email3", "email_3", "mail3", "mail_3"),
    "cajon": ("cajon", "cajon_asignacion_cliente", "tipo_cajon"),
    "ecosistema": ("ecosistema", "tipo_ecosistema"),
    "asignacion": ("asignacion", "tipo_asignacion"),
}

# Optional canonical columns. If absent from the source, they default to NA
# instead of raising. Required columns (everything else in INPUT_COLUMNS) must
# be mappable from the source; otherwise load_input raises ValueError listing
# the missing canonical names + headers actually found.
INPUT_OPTIONAL_COLUMNS: frozenset[str] = frozenset({"asignacion", "email2"})

OUTPUT_COLUMNS = [
    "id_nro_dni",
    "customer_name",
    "tel_1",
    "tel_2",
    "tel_3",
    "tel_4",
    "txt_email_1",
    "txt_email_2",
    "txt_email_3",
    "id_nro_producto",
    "tipo_ecosistema",
    "tipo_asignacion",
    "tipo_plan",
    "tipo_cajon",
    "tipo_estrategia",
    "cnt_dias_mora",
    "monto_deuda_vencida_tc_ars",
    "monto_deuda_vencida_nd_ars",
    "monto_total_vencido_ars",
    "monto_deuda_total_tc_ars",
    "monto_deuda_total_nd_ars",
    "monto_deuda_total_ars",
    "fecha_gestion",
]

OUTPUT_COLUMNS_PHASE2_FIXED = [
    "recupero",
    "tipo_pago",
]

OUTPUT_COLUMNS = OUTPUT_COLUMNS + OUTPUT_COLUMNS_PHASE2_FIXED

# ROMAN output contract: fixed base columns + dynamic plan columns.
OUTPUT_COLUMNS_ROMAN = [
    "nombre_cliente",
    "tel_1",
    "tel_2",
    "tel_3",
    "tel_4",
    "id_dni",
    "id_producto",
    "tipo_cajon",
    "plan_ok",
    "monto_deuda_tc",
    "monto_deuda_nd",
    "monto_deuda_total",
    "monto_deuda_vencida_actual",
    "fecha_limite_sistema",
]

PHONE_COLUMNS = ["telefono1", "telefono2", "telefono3", "telefono4"]
EMAIL_COLUMNS = ["email1", "email2", "email3"]

PHONE_MOBILE_PREFIX = "549"
PHONE_LANDLINE_PREFIX = "54"
PHONE_MOBILE_LENGTH = 13
PHONE_LANDLINE_LENGTH = 12

AMOUNT_INPUT_COLS = {
    "monto_deuda_vencida_tc_ars": "deuda_vencida_tc",
    "monto_deuda_vencida_nd_ars": "deuda_vencida_nd",
    "monto_total_vencido_ars": "total_vencida",
    "monto_deuda_total_tc_ars": "deuda_total_tc",
    "monto_deuda_total_nd_ars": "deuda_total_nd",
    "monto_deuda_total_ars": "total_deuda",
}

OUTPUT_FILENAME_PREFIX = "NARANJAX_CARTERA_"
OUTPUT_FILENAME_ROMAN = "NARANJAX_MA_ROMAN_"
OUTPUT_FILENAME_E1KIA = "NARANJAX_MA_E1KIA_"

PLAN_COLUMN_PATTERN = "plan_{n}_{field}"
PLAN_FIELDS = ["cuotas", "entrega", "cuota_mensual"]
MAX_DYNAMIC_PLANS = 7
ALLOWED_PLAN_INSTALLMENTS = (3, 6, 9, 12, 18, 24, 36)

PLANES_REQUIRED_COLUMNS = [
    "nroproducto",
    "cajon",
    "deuda_total",
    "deuda_vencida",
    "plan",
    "importe_entrega",
    "importe_cuota",
]

PAGOS_REQUIRED_COLUMNS = [
    "nroproducto",
    "recupero",
    "tipo_pago",
    "cajon_asig_prod",
    "cajon_actual_prod",
]


def get_plan_column_names(max_plans: int) -> list[str]:
    """Generate dynamic output column names for plan options."""
    if max_plans <= 0:
        return []

    max_plans = min(max_plans, MAX_DYNAMIC_PLANS)

    columns: list[str] = []
    for idx in range(1, max_plans + 1):
        for field in PLAN_FIELDS:
            columns.append(PLAN_COLUMN_PATTERN.format(n=idx, field=field))
    return columns

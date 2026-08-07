"""Constants and mapping tables for tipificaciones IA voz PCT ETL."""

from __future__ import annotations

REQUIRED_SOURCE_COLUMNS = [
    "call_id",
    "id_cliente",
    "tipificaciones",
    "observaciones",
    "call_refid",
]

OPTIONAL_SOURCE_COLUMNS = [
    "fecha_compromiso_tc",
    "fecha_compromiso_nd",
    "monto_compromiso",
    "id_nro_producto",
]

OUTPUT_COLUMNS = [
    "DNI",
    "TIPIFICACION",
    "NROPRODUCTO",
    "FECHA_PROMESA",
    "MONTO_PROMESA",
    "CALL_REFID",
    "OBSERVACIONES",
]

OUTPUT_FILENAME_PREFIX = "NARANJAX_PCT_"
OUTPUT_FILENAME_EXTENSION = ".csv"
OBSERVACIONES_MAX_CHARS = 1500
OUTPUT_DELIMITER = "|"
OUTPUT_ENCODING = "cp1252"
OUTPUT_DATE_FORMAT = "yyyyMMdd"
OUTPUT_COLUMNS_COUNT = len(OUTPUT_COLUMNS)

TIPIF_MAP = {
    "LOGCALL": "26",
    "PROMESA_DE_PAGO": "12",
    "DIFICULTAD_DE_PAGO": "47",
    "SIN_VOLUNTAD_DE_PAGO": "17",
    "NO_RECONOCE_DEUDA": "15",
    "NOTIFICADO_TITULAR": "8",
    "NOTIFICADO_FAMILIAR": "8",
    "CONOCE_TITULAR": "8",
    "NO_RESPONDE": "7",
    "CONTESTADOR": "26",
    "FALLECIDO": "16",
    "NO_ES_TITULAR": "61",
    "MENSAJE": "28",
    "MENSAJE_DEUDOR": "28",
    "MENSAJE_TERCERO": "29",
    "YA_PAGO_TOTAL_MORA": "37",
    "YA_PAGO_TOTAL_CUENTA": "38",
    "YA_PAGO_PLAN_DE_PAGO": "39",
    "YA_PAGO_PLAN_DE_CUOTAS": "40",
    "YA_PAGO_MES_VENCIDO": "41",
    "DIF_DE_PAGO_BOTON_DE_PAGO": "43",
    "DIF_DE_PAGO_SIN_TRABAJO": "44",
    "DIF_DE_PAGO_PROBLEMAS_DE_SALUD": "45",
    "DIF_DE_PAGO_PROBLEMAS_CON_EL_COBRO": "46",
    "DIF_DE_PAGO_GENERAL": "47",
    "DIF_DE_PAGO_PRIORIZA_OTRAS_DEUDAS": "48",
}

COLUMN_ALIASES = {
    "call_id": ["Call ID", "call_id", "CallID", "[Entrada] call_id"],
    "call_refid": ["call_refid", "CALL_REFID", "Call ID"],
    "id_cliente": [
        "[Entrada] id_dni",
        "id_dni",
        "[Entrada] id_cliente",
        "id_cliente",
        "[Entrada] user_number",
        "user_number",
        "[Entrada] msisdn",
        "msisdn",
        "[Entrada] customer_id",
        "customer_id",
    ],
    "tipificaciones": [
        "[Salida] Tipificaciones",
        "[Salida] tipificaciones",
        "[Salida] categoria",
        "Tipificaciones",
    ],
    "observaciones": [
        "[Salida] observaciones",
        "[Salida] OBSERVACIONES",
        "observaciones",
    ],
    "fecha_compromiso_tc": ["[Salida] fecha_compromiso_tc", "fecha_compromiso_tc"],
    "fecha_compromiso_nd": ["[Salida] fecha_compromiso_nd", "fecha_compromiso_nd"],
    "monto_compromiso": [
        "[Salida] Monto_compromiso",
        "[Salida] monto_compromiso",
        "Monto_compromiso",
    ],
    "id_nro_producto": [
        "[Entrada] id_producto",
        "id_producto",
        "id_nro_producto",
        "NROPRODUCTO",
        "nro_producto",
    ],
}

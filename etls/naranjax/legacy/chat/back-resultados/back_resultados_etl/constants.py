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

TIPIF_MAP = {
    "PROMESA_DE_PAGO": "12",
    "DIFICULTAD_DE_PAGO": "47",
    "SIN_VOLUNTAD_DE_PAGO": "17",
    "NO_RECONOCE_DEUDA": "15",
    "MANIFIESTA_PAGO": "37",
    "NOTIFICADO_TITULAR": "8",
    "NOTIFICADO_FAMILIAR": "8",
    "CONOCE_TITULAR": "8",
    "NO_RESPONDE": "11",
    "CONTESTADOR": "11",
    "FALLECIDO": "16",
    "NO_ES_TITULAR": "61",
}

COLUMN_ALIASES = {
    "call_id": ["Call ID", "call_id", "CallID", "[Entrada] call_id"],
    "call_refid": ["call_refid", "CALL_REFID", "Call ID"],
    "id_cliente": [
        "[Entrada] id_dni",
        "id_dni",
        "[Entrada] id_cliente",
        "id_cliente",
    ],
    "tipificaciones": [
        "[Salida] Tipificaciones",
        "[Salida] tipificaciones",
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

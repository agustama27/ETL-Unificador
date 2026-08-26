"""Constantes de columnas — esquema canónico intermedio y de salida.

Un solo lugar para los nombres de columna evita "magic strings" repetidos
entre extractors/transformers/loaders.
"""

# --- Esquema canónico (salida de cada extractor, entrada del transform) ---
COL_CLIENTE_RAW = "cliente_raw"
COL_CLIENTE_KEY = "cliente_key"
COL_CLIENTE_ID = "cliente_id_autologica"
COL_TELEFONO_RAW = "telefono_raw"
COL_PRODUCTO = "producto_descripcion"
COL_CONCEPTO = "concepto"
COL_FECHA = "fecha"
COL_REMITO = "remito_o_comprobante"
COL_MONTO_ORIGINAL = "monto_original"
COL_DIAS_MORA_FUENTE = "dias_mora_fuente"
COL_PRIORIDAD_RAW = "prioridad_raw"
COL_FUENTE = "fuente"

CANONICAL_COLUMNS = [
    COL_CLIENTE_RAW,
    COL_CLIENTE_KEY,
    COL_CLIENTE_ID,
    COL_TELEFONO_RAW,
    COL_PRODUCTO,
    COL_CONCEPTO,
    COL_FECHA,
    COL_REMITO,
    COL_MONTO_ORIGINAL,
    COL_DIAS_MORA_FUENTE,
    COL_PRIORIDAD_RAW,
    COL_FUENTE,
]

# --- Esquema de salida (detalle enriquecido, post-transform) ---
COL_TELEFONO = "telefono"
COL_MONTO_USD = "monto_usd"
COL_DIAS_MORA = "dias_mora"
COL_PRIORIDAD = "prioridad"

# --- Esquema de salida final (nombres de negocio, consolidado/Approach) ---
OUT_NOMBRE_APELLIDO = "NombreApellido"
OUT_TELEFONO_CLIENTE = "TelefonoCliente"
OUT_SALDO_EXIGIBLE_USD = "SaldoExigibleUSD"
OUT_CANTIDAD_PRODUCTOS = "CantidadProductos"
OUT_PRODUCTOS = "Productos"  # array "producto:monto;..." (Remitos: 1 entrada por categoria)
OUT_DIAS_MORA = "DiasMora"
OUT_FLAG_PRIORIDAD = "FlagPrioridad"
OUT_CLIENTE_ID = "ClienteIdAutologica"
OUT_PRODUCTOS_REMITOS = "ProductosRemitos"  # subconjunto de Productos originado en Remitos

OUTPUT_COLUMNS = [
    OUT_NOMBRE_APELLIDO,
    OUT_TELEFONO_CLIENTE,
    OUT_SALDO_EXIGIBLE_USD,
    OUT_CANTIDAD_PRODUCTOS,
    OUT_PRODUCTOS,
    OUT_DIAS_MORA,
    OUT_FLAG_PRIORIDAD,
    OUT_CLIENTE_ID,
    OUT_PRODUCTOS_REMITOS,
]

FUENTE_SALDOS_GENERALES = "saldos_generales"
FUENTE_MAQUINARIAS = "maquinarias"
FUENTE_REMITOS_REPUESTOS = "remitos_repuestos"
FUENTE_REMITOS_SERVICIOS = "remitos_servicios"

# Fuentes de Remitos: no traen detalle por concepto (el producto es siempre
# la categoria, "Repuestos" o "Servicios"), asi que sus deudas se consolidan
# en una entrada por categoria y se marcan en OUT_PRODUCTOS_REMITOS.
FUENTES_REMITOS = frozenset({FUENTE_REMITOS_REPUESTOS, FUENTE_REMITOS_SERVICIOS})

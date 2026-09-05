"""
Configuracion de la Oferta de Cancelacion Anticipada (OFERTA_PREVENTA) para BANCOR.

Modulo de datos puros: solo constantes y listas. No contiene logica.
Lo consumen `base_generator` (salida sin-filtros) y
`filtrosAplicados_base_BANCOR/procesos/pipeline_wfm.py` (salida ROMAN con filtros),
para mantener ambas salidas alineadas con una unica fuente de verdad.

Contexto de negocio: [BANCOR] COBRANZAS | OFERTA DE CANCELACION ANTICIPADA.
Cancelacion total de contado con quita sobre el saldo contabilizado. El importe
lo calcula Bancor y viene en la columna `OFERTA_PREVENTA`: el ETL NO lo recalcula
ni deriva porcentajes.

Ver docs/oferta-preventa/PRD-oferta-preventa-etl.md y
docs/oferta-preventa/ADR-001-vigencia-y-precedencia-preventa.md.
"""

# ── Vigencia de campania (RF-5) ─────────────────────────────────────────────────

# Ultimo dia INCLUSIVE en que la oferta se ofrece (formato 'YYYY-MM-DD').
# La vigencia se evalua contra la FECHA DE CORRIDA del ETL, no contra Fecha_Entrega.
# Desde el dia siguiente, `oferta_preventa` = "no" para todas las filas y las cinco
# columnas derivadas quedan vacias, sin tocar el conversation flow de Retell (ADR-001).
FECHA_LIMITE_PREVENTA = "2026-09-30"

# ── Elegibilidad (RF-1) ─────────────────────────────────────────────────────────

# Valor de la columna `PreVenta` (trim + upper) que habilita la oferta.
VALOR_PREVENTA_ELEGIBLE = "APLICA OFERTA"

# ── Medio de pago (RF-3) ────────────────────────────────────────────────────────

# Unico medio habilitado para esta campania. Se emite explicito para que el agente
# no tenga que inferirlo del estado de cuenta.
MEDIO_PAGO_PREVENTA = "cupon"

# ── Refinanciacion por tramo de mora (RF-2 / BLQ-1) ─────────────────────────────

# Tramos de `Dias_Mora` y su TNA asociada. Se evaluan contra el MAXIMO de Dias_Mora
# del grupo consolidado por CUIL (misma convencion que `cnt_dias_mora_max`).
TRAMOS_TNA_REFI_PREVENTA = [
    {"mora_min": 366, "mora_max": 570, "tna": "30"},
    {"mora_min": 571, "mora_max": 10**9, "tna": "20"},
]

# BLQ-1 - Fuente de verdad para rutear la TNA de refinanciacion.
#   "campana_ref" -> se toma el numero de `Campaña_REF` tal cual lo cargo Bancor.
#   "dias_mora"   -> se clasifica por TRAMOS_TNA_REFI_PREVENTA.
# Default "campana_ref": es el dato explicito y auditable, es lo que el flow ya usa
# hoy (`{{tipo_campana_ref}}`) y es lo que el banco honra cuando el cliente llama.
# Ademas `Campaña_REF` sigue sirviendo campanias fuera de la cohorte preventa
# (CAMPANA45%, CAMPANA35%), asi que el dominio de valores NO se restringe a 30/20.
# Confirmado por Bancor el 03/09/2026 (PRD, BLQ-1).
FUENTE_TNA_REFI_PREVENTA = "campana_ref"

# Si es True, se emite una advertencia ROMAN por cada fila donde el tramo de
# `Dias_Mora` no coincide con lo que dice `Campaña_REF` (291 filas / 8,5 % de la
# cohorte en la base del 02-09-2026). Es auditoria para Bancor: NO altera el ruteo.
ADVERTIR_DISCORDANCIA_TNA = True

# ── Anticipo minimo de refinanciacion (BLQ-2) ───────────────────────────────────

# Si es True y `AnticipoMinimo` no es numerico (132 filas traen el literal
# "CANCELAR") o es >= al importe de la oferta de contado (1.509 de 3.278 filas
# numericas, 46 %), se SUPRIME la refinanciacion para esa fila:
# `tipo_tna_refi_preventa` = "" y `monto_entrega_ars` = "". El agente ofrece
# entonces solo cancelacion de contado, en lugar de pedir un anticipo mayor que
# cancelar toda la deuda.
# Default conservador. Pendiente de confirmacion por Bancor.
SUPRIMIR_REFI_SI_ANTICIPO_INCOHERENTE = True

# Literal no numerico observado en `AnticipoMinimo`. Hipotesis: significa "no hay
# plan de refinanciacion, solo cancelacion". Pendiente de confirmacion por Bancor.
LITERAL_ANTICIPO_SOLO_CANCELACION = "CANCELAR"

# ── Cuenta Bancon (RF-4 / BLQ-3) ────────────────────────────────────────────────

# Valores canonicos de `BanconUsr` que se emiten sin transformar en `tipo_bancon_usr`.
VALORES_BANCON_USR = ("Activo", "NoActivo")

# BLQ-3 - Tratamiento del `BanconUsr` vacio (896 filas / 7,5 %; 240 en la cohorte
# preventa). Si es None, el vacio se emite tal cual ("") y el flow lo rutea al
# camino conservador; cuando Bancor defina, se cambia un branch del flow y no el
# pipeline. Alternativa: "NoActivo" para forzar el criterio conservador desde el ETL.
# Pendiente de confirmacion por Bancor.
VALOR_BANCON_USR_VACIO = None

# Si es True, se emite una advertencia ROMAN con el conteo de filas con
# `BanconUsr` vacio dentro de la cohorte preventa.
ADVERTIR_BANCON_USR_VACIO = True

# ── Precedencia frente a la oferta vigente (BLQ-4) ──────────────────────────────

# 1.864 filas tienen `OFERTA_Importe` > 0 Y `PreVenta` = APLICA OFERTA: son dos
# beneficios distintos sobre el mismo cliente. Precedente del repo:
# `config_quita.EXCLUIR_SI_TIENE_OFERTA = True` (no ofrecer dos beneficios al mismo
# cliente). Si es True, cuando aplica preventa se emite `oferta_importe` = "no"
# para que el flow no entre por la rama de la oferta vieja.
# Default conservador. Pendiente de confirmacion por Bancor.
PRECEDENCIA_SOBRE_OFERTA_VIGENTE = True

# Si es True, se emite una advertencia ROMAN con el conteo de clientes que tenian
# ambos beneficios y quedaron ruteados a preventa.
ADVERTIR_DOBLE_OFERTA = True

# ── Contrato de salida ──────────────────────────────────────────────────────────

# Columnas nuevas del contrato ROMAN, en orden. Se insertan DESPUES de
# `fecha_limite_oferta` para no alterar el orden relativo de las existentes.
#   `tipo_tna_refi_preventa` es DERIVADA de `tipo_campana_ref`, no un dato
#   independiente: la calcula `_tna_por_campana_ref()` en un unico lugar. Para
#   cambiar la TNA de un cliente se cambia `Campaña_REF` EN ORIGEN, nunca esta
#   columna. Existe como columna propia para que el flow resuelva la refinanciacion
#   con UN nodo parametrizado en vez de cuatro nodos casi identicos por tasa.
COLUMNAS_SALIDA_PREVENTA = [
    "oferta_preventa",
    "monto_total_preventa",
    "alcance_preventa",
    "tipo_tna_refi_preventa",
    "medio_pago_preventa",
    "fecha_limite_preventa",
    "tipo_bancon_usr",
]

# Las cinco columnas que deben quedar vacias cuando `oferta_preventa` = "no".
COLUMNAS_DERIVADAS_PREVENTA = [
    "monto_total_preventa",
    "alcance_preventa",
    "tipo_tna_refi_preventa",
    "medio_pago_preventa",
    "fecha_limite_preventa",
]

# ── Columnas crudas de la base GYM ──────────────────────────────────────────────

COL_PREVENTA = "PreVenta"
COL_OFERTA_PREVENTA = "OFERTA_PREVENTA"
COL_BANCON_USR = "BanconUsr"

# Alias de tolerancia de encabezados. La base viene con encoding inconsistente
# (`Campa�a_REF`) y el requerimiento funcional escribe `OFERTA_Preventa`, pero el
# nombre real en la base es `OFERTA_PREVENTA` en MAYUSCULAS. Mismo criterio que el
# bloque de normalizacion de headers de `base_generator.normalizar_encabezados_nuevas_columnas`.
ALIAS_ENCABEZADOS_PREVENTA = {
    "PreVenta": COL_PREVENTA,
    "Preventa": COL_PREVENTA,
    "PREVENTA": COL_PREVENTA,
    "Pre_Venta": COL_PREVENTA,
    "Pre Venta": COL_PREVENTA,
    "pre_venta": COL_PREVENTA,
    "preventa": COL_PREVENTA,
    "OFERTA_PREVENTA": COL_OFERTA_PREVENTA,
    "OFERTA_Preventa": COL_OFERTA_PREVENTA,
    "Oferta_Preventa": COL_OFERTA_PREVENTA,
    "OFERTA PREVENTA": COL_OFERTA_PREVENTA,
    "Oferta Preventa": COL_OFERTA_PREVENTA,
    "OfertaPreventa": COL_OFERTA_PREVENTA,
    "oferta_preventa": COL_OFERTA_PREVENTA,
    "BanconUsr": COL_BANCON_USR,
    "Bancon_Usr": COL_BANCON_USR,
    "Bancon Usr": COL_BANCON_USR,
    "BANCONUSR": COL_BANCON_USR,
    "bancon_usr": COL_BANCON_USR,
    "banconusr": COL_BANCON_USR,
}

# Firmas canonicas (nombre reducido a alfanumericos en minuscula, sin acentos ni
# mojibake) para tolerar variantes no enumeradas arriba.
FIRMAS_ENCABEZADOS_PREVENTA = {
    "preventa": COL_PREVENTA,
    "ofertapreventa": COL_OFERTA_PREVENTA,
    "banconusr": COL_BANCON_USR,
}

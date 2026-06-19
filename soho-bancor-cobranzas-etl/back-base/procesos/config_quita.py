"""
Configuracion de la quita de intereses para la base ROMAN (sin-filtros).

Modulo de datos puros: solo constantes y listas. No contiene logica.
Lo consume `base_generator.calcular_quita()` y, por importacion, el pipeline
de la UI (`filtrosAplicados_base_BANCOR/procesos/pipeline_wfm.py`) para mantener
ambas salidas ROMAN alineadas con una unica fuente de verdad.

Contexto de negocio: [BANCOR] COBRANZAS | QUITAS DE INTERESES (criterios 20-25).
Pago total con quita segun dias de mora y tipo de mercado, sujeto a autorizacion
posterior de Bancor.
"""

# ── Parametros de elegibilidad ──────────────────────────────────────────────────

# Tipo de mercado elegible para la quita (D1). "MA" = Mercado Abierto.
# Pendiente de confirmacion formal por Bancor.
TIPO_MERCADO_ELEGIBLE = "MA"

# Si es True, un cliente que ya tiene oferta pre-calculada NO recibe quita (D3).
# Default conservador: evita ofrecer dos beneficios distintos al mismo cliente.
EXCLUIR_SI_TIENE_OFERTA = True

# Si es True, la quita tambien condona el IVA de los intereses (D4).
# Default False: la formula base NO condona IVA. Consultar a Bancor.
QUITA_INCLUYE_IVA = False

# Fecha limite de la oferta de quita (formato 'YYYY-MM-DD'), fija de campania.
# Cambiable sin tocar codigo. Pendiente de definicion por Bancor; se usa la misma
# fecha que la oferta vigente desplegada para mantener coherencia.
FECHA_LIMITE_QUITA = "2026-06-12"

# ── Rangos de quita por dias de mora (D2) ───────────────────────────────────────
# pct_comp / pct_punit = proporcion de Compensatorio / Punitorios que se condona.
# El rango se evalua contra el MAXIMO de Dias_Mora del cliente.
RANGOS_QUITA = [
    {"mora_min": 61,  "mora_max": 90,  "pct_comp": 0.00, "pct_punit": 1.00},
    {"mora_min": 91,  "mora_max": 180, "pct_comp": 0.30, "pct_punit": 1.00},
    {"mora_min": 181, "mora_max": 365, "pct_comp": 0.50, "pct_punit": 1.00},
]

"""
Configuracion Y FORMULA de la quita de intereses para la base ROMAN.

Constantes de campania mas `calcular_quita()`, la unica implementacion de la
formula. La consumen `base_generator` (salida sin-filtros) y
`filtrosAplicados_base_BANCOR/procesos/pipeline_wfm.py` (salida con filtros),
ambos importando ESTE modulo por nombre.

Por que la formula vive aca y no en `base_generator`
----------------------------------------------------
`pipeline_wfm` cargaba `calcular_quita` desde `base_generator.py` con un loader
por path (`_load_back_base_generator_module`). En el ejecutable congelado ese
archivo no existe: el loader devolvia None, la quita defaulteaba en silencio a
"no" y el exe emitia `aplica_quita = "no"` en el 100 % de las filas, con miles de
clientes en el rango de mora elegible. El CSV salia valido y equivocado.

Este modulo no depende de pandas ni de nada del arbol de fuentes, asi que se
bundlea con el exe (ver `filtrosAplicados_base_BANCOR.spec`) y se importa por
nombre desde ambos lados. Sin loader no hay degradacion silenciosa posible.

Mantener este modulo SIN dependencias externas: es la condicion que lo hace
bundleable. Si la formula llegara a necesitar pandas, hay que resolverlo sin
volver al loader.

Contexto de negocio: [BANCOR] COBRANZAS | QUITAS DE INTERESES (criterios 20-25).
Pago total con quita segun dias de mora y tipo de mercado, sujeto a autorizacion
posterior de Bancor.
"""

import re

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


# ── Formula de la quita ─────────────────────────────────────────────────────────
# Unica implementacion. `base_generator.calcular_quita` la reexporta por
# compatibilidad; `pipeline_wfm` la importa directo desde aca.


def _es_nulo(valor) -> bool:
    """True para None, NaN, pd.NA y pd.NaT, sin importar pandas."""
    if valor is None:
        return True
    try:
        return bool(valor != valor)
    except (TypeError, ValueError):
        # pd.NA no admite bool(): es nulo por definicion.
        return True


def _parsear_decimal(valor):
    """Parsea numeros tolerando formato europeo y simbolos. Devuelve float o None.

    Replica exacta de `base_generator._parsear_decimal`, sin `pd.isna` para que
    este modulo siga siendo bundleable sin pandas. La paridad esta cubierta por
    `test_parsear_decimal_paridad_config_quita_vs_base_generator`.
    """
    if _es_nulo(valor):
        return None

    texto = str(valor).strip()
    if texto in {'', 'nan', 'NaN', 'None', 'NaT'}:
        return None

    texto = re.sub(r'[^0-9,\.\-]', '', texto)
    if texto in {'', '-', '.', ','}:
        return None

    if ',' in texto and '.' in texto:
        if texto.rfind(',') > texto.rfind('.'):
            texto = texto.replace('.', '').replace(',', '.')
        else:
            texto = texto.replace(',', '')
    elif ',' in texto:
        texto = texto.replace('.', '').replace(',', '.')

    try:
        return float(texto)
    except ValueError:
        return None


def _rango_quita_para_mora(dias_mora_max):
    """Devuelve el dict de RANGOS_QUITA que aplica para los dias de mora, o None."""
    try:
        dias = int(float(dias_mora_max))
    except (TypeError, ValueError):
        return None
    for rango in RANGOS_QUITA:
        if rango['mora_min'] <= dias <= rango['mora_max']:
            return rango
    return None


def calcular_quita(
    tipo_mercado,
    dias_mora_max,
    comp_total,
    punit_total,
    monto_adeudado,
    tiene_oferta,
    iva_totales: dict | None = None,
) -> tuple:
    """
    Calcula si un cliente es elegible para la quita de intereses y el monto final.

    Implementa la spec funcional 3.1/3.2: aplica 'si' solo si TODAS se cumplen:
      (a) Tipo_Mercado == TIPO_MERCADO_ELEGIBLE
      (b) dias_mora_max cae en algun rango de RANGOS_QUITA (61..365)
      (c) la quita calculada es > 0 (descuento real)
      (d) 0 < monto_quita_ars < monto_adeudado (sanity)
      (e) si EXCLUIR_SI_TIENE_OFERTA, el cliente no tiene oferta pre-calculada

    Nota: la vigencia NO se evalua aca. FECHA_LIMITE_QUITA se emite como dato en
    la columna `fecha_limite_quita`; no es un criterio de elegibilidad.

    Args:
        tipo_mercado: valor crudo de Tipo_Mercado del cliente.
        dias_mora_max: maximo de Dias_Mora del cliente.
        comp_total: suma de Compensatorio del cliente.
        punit_total: suma de Punitorios del cliente.
        monto_adeudado: MontoAdeudado consolidado del cliente.
        tiene_oferta: True si el cliente tiene oferta pre-calculada (oferta_importe == 'si').
        iva_totales: dict opcional {'comp': ..., 'punit': ...} con IVA + percepciones,
            usado solo si QUITA_INCLUYE_IVA es True.

    Returns:
        Tupla (aplica_quita, monto_quita_ars):
          - ('si', float redondeado a 2 decimales) si es elegible.
          - ('no', None) en caso contrario.
    """
    no_aplica = ('no', None)

    # (a) Tipo de mercado elegible
    tipo = str(tipo_mercado).strip().upper() if tipo_mercado is not None else ''
    if tipo != str(TIPO_MERCADO_ELEGIBLE).strip().upper():
        return no_aplica

    # (b) rango de mora a nivel cliente
    rango = _rango_quita_para_mora(dias_mora_max)
    if rango is None:
        return no_aplica

    # (e) exclusividad con oferta pre-calculada
    if EXCLUIR_SI_TIENE_OFERTA and tiene_oferta:
        return no_aplica

    monto = _parsear_decimal(monto_adeudado)
    if monto is None:
        return no_aplica

    comp = _parsear_decimal(comp_total) or 0.0
    punit = _parsear_decimal(punit_total) or 0.0

    quita = rango['pct_comp'] * comp + rango['pct_punit'] * punit

    if QUITA_INCLUYE_IVA and iva_totales:
        iva_comp = _parsear_decimal(iva_totales.get('comp')) or 0.0
        iva_punit = _parsear_decimal(iva_totales.get('punit')) or 0.0
        quita += rango['pct_comp'] * iva_comp + rango['pct_punit'] * iva_punit

    # (c) descuento real
    if quita <= 0:
        return no_aplica

    monto_quita = round(monto - quita, 2)

    # (d) sanity: 0 < monto_quita < monto_adeudado
    if monto_quita <= 0 or monto_quita >= round(monto, 2):
        return no_aplica

    return ('si', monto_quita)

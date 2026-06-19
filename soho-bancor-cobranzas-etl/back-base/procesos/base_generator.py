import pandas as pd
import os
import sys
from pathlib import Path
from datetime import datetime
import re
import unicodedata

# Import robusto del config de quita: inserta el directorio propio en sys.path
# para que funcione tanto en ejecucion directa como cuando el pipeline de la UI
# carga este modulo dinamicamente via importlib.
_DIRECTORIO_ACTUAL = Path(__file__).resolve().parent
if str(_DIRECTORIO_ACTUAL) not in sys.path:
    sys.path.insert(0, str(_DIRECTORIO_ACTUAL))

from config_quita import (
    TIPO_MERCADO_ELEGIBLE,
    EXCLUIR_SI_TIENE_OFERTA,
    QUITA_INCLUYE_IVA,
    FECHA_LIMITE_QUITA,
    RANGOS_QUITA,
)


COL_TIPO_ASIGNACION = 'Tipo_Asignacion'
COL_TIPO_MERCADO = 'Tipo_Mercado'
COL_COMPENSATORIO = 'Compensatorio'
COL_PUNITORIOS = 'Punitorios'
COL_GESTION_DESCRIPCION = 'GestionDescripci\u00f3n'
COL_MONTO_VENCIDO = 'MontoVencido'
COL_MONTO_ADEUDADO = 'MontoAdeudado'
COL_CAMPANA_REF = 'Campaña_REF'


def corregir_codificacion_texto(texto: str) -> str:
    """
    Corrige problemas de codificación comunes, especialmente caracteres especiales
    mal codificados (ej: CrÃ©dito -> Crédito).
    
    Esto ocurre cuando un archivo UTF-8 se lee como latin-1.
    
    Args:
        texto: String que puede tener problemas de codificación
        
    Returns:
        String con la codificación corregida
    """
    if pd.isna(texto) or texto == '':
        return texto if isinstance(texto, str) else ''
    
    texto_str = str(texto)
    
    # Si el texto contiene patrones de codificación incorrecta (como "Ã©"), intentar corregir
    if 'Ã' in texto_str:
        try:
            # Intentar decodificar como latin-1 y luego codificar como utf-8
            # Esto corrige el caso donde utf-8 fue leído como latin-1
            texto_corregido = texto_str.encode('latin-1').decode('utf-8')
            return texto_corregido
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Si falla, usar correcciones manuales para los casos más comunes
            # Usar replace directo para evitar problemas de parsing con caracteres especiales
            texto_corregido = texto_str
            texto_corregido = texto_corregido.replace('Ã¡', 'á').replace('Ã©', 'é').replace('Ã­', 'í')
            texto_corregido = texto_corregido.replace('Ã³', 'ó').replace('Ãº', 'ú').replace('Ã±', 'ñ')
            texto_corregido = texto_corregido.replace('Ã', 'Á').replace('Ã‰', 'É').replace('Ã', 'Í')
            texto_corregido = texto_corregido.replace('Ã"', 'Ó').replace('Ãš', 'Ú')
            # Corregir Ñ (usar comillas dobles para evitar problemas)
            texto_corregido = texto_corregido.replace("Ã'", "Ñ")
            texto_corregido = texto_corregido.replace('Ã¼', 'ü').replace('Ãœ', 'Ü')
            
            return texto_corregido
    
    # Si no hay problemas aparentes, retornar el texto original
    return texto_str


def normalizar_encabezados_nuevas_columnas(df):
    """
    Normaliza variantes de encabezados para mantener nombres canónicos.

    Canónicos esperados:
    - Tipo_Asignacion
    - GestionDescripción
    - MontoVencido
    """
    variantes_exactas = {
        'Tipo Asignacion': COL_TIPO_ASIGNACION,
        'TipoAsignacion': COL_TIPO_ASIGNACION,
        'Tipo_Asignación': COL_TIPO_ASIGNACION,
        'Tipo Asignación': COL_TIPO_ASIGNACION,
        'Tipo_AsignaciÃ³n': COL_TIPO_ASIGNACION,
        'Tipo AsignaciÃ³n': COL_TIPO_ASIGNACION,
        'tipo_asignacion': COL_TIPO_ASIGNACION,
        'GestionDescripcion': COL_GESTION_DESCRIPCION,
        'Gestion Descripcion': COL_GESTION_DESCRIPCION,
        'Gestion_Descripcion': COL_GESTION_DESCRIPCION,
        'GestiónDescripción': COL_GESTION_DESCRIPCION,
        'GestionDescripciÃ³n': COL_GESTION_DESCRIPCION,
        'GestionDescripci�n': COL_GESTION_DESCRIPCION,
        'Gestion DescripciÃ³n': COL_GESTION_DESCRIPCION,
        'Gestion Descripci�n': COL_GESTION_DESCRIPCION,
        'gestiondescripcion': COL_GESTION_DESCRIPCION,
        'Monto_Vencido': COL_MONTO_VENCIDO,
        'Monto Vencido': COL_MONTO_VENCIDO,
        'monto_vencido': COL_MONTO_VENCIDO,
        'TEL1': 'NumeroTelefono',
        'Tel1': 'NumeroTelefono',
        'TEL2': 'NumeroCelular',
        'Tel2': 'NumeroCelular',
        'OFERTA': 'OFERTA_Importe',
        'Campana_REF': COL_CAMPANA_REF,
        'Campaña Ref': COL_CAMPANA_REF,
        'Campana Ref': COL_CAMPANA_REF,
        'Campaña_Ref': COL_CAMPANA_REF,
        'Campana_Ref': COL_CAMPANA_REF,
        'Campa\u00f1a_REF': COL_CAMPANA_REF,
        'Campa\u00f1a_Ref': COL_CAMPANA_REF,
        'CampaÃ±a_REF': COL_CAMPANA_REF,
        'campa\u00f1a_ref': COL_CAMPANA_REF,
        'campana_ref': COL_CAMPANA_REF,
        'Tipo Mercado': COL_TIPO_MERCADO,
        'TipoMercado': COL_TIPO_MERCADO,
        'tipo_mercado': COL_TIPO_MERCADO,
    }

    firmas_canonicas = {
        'tipoasignacion': COL_TIPO_ASIGNACION,
        'gestiondescripcion': COL_GESTION_DESCRIPCION,
        'montovencido': COL_MONTO_VENCIDO,
        'campanaref': COL_CAMPANA_REF,
        'tipomercado': COL_TIPO_MERCADO,
    }

    def firma_columna(nombre_columna):
        nombre = corregir_codificacion_texto(str(nombre_columna)).strip().lower()
        nombre = unicodedata.normalize('NFKD', nombre)
        nombre = ''.join(c for c in nombre if not unicodedata.combining(c))
        nombre = ''.join(c for c in nombre if c.isalnum())
        return nombre

    renombres = {}
    columnas_actuales = list(df.columns)

    for columna in columnas_actuales:
        if columna in variantes_exactas:
            canonica = variantes_exactas[columna]
            if canonica not in df.columns and canonica not in renombres.values():
                renombres[columna] = canonica

    for columna in columnas_actuales:
        if columna in renombres or columna in firmas_canonicas.values():
            continue
        canonica = firmas_canonicas.get(firma_columna(columna))
        if canonica and canonica not in df.columns and canonica not in renombres.values():
            renombres[columna] = canonica

    if renombres:
        print(f"Columnas normalizadas a canónico: {renombres}")
        df = df.rename(columns=renombres)

    return df


def convertir_a_snake_case(nombre_columna):
    """
    Convierte un nombre de columna a snake_case en minúsculas.

    Maneja casos comunes: CamelCase/PascalCase, espacios, guiones y acentos.
    """
    nombre = corregir_codificacion_texto(str(nombre_columna)).strip()
    nombre = unicodedata.normalize('NFKD', nombre)
    nombre = ''.join(c for c in nombre if not unicodedata.combining(c))
    nombre = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', nombre)
    nombre = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', nombre)
    nombre = re.sub(r'[^0-9A-Za-z]+', '_', nombre)
    nombre = re.sub(r'_+', '_', nombre).strip('_')
    return nombre.lower()


def normalizar_columnas_snake_case(df):
    """Renombra columnas a snake_case evitando colisiones."""
    renombres = {}
    usados = set()

    for columna in df.columns:
        base = convertir_a_snake_case(columna)
        if not base:
            base = 'columna'

        nombre_final = base
        sufijo = 2
        while nombre_final in usados:
            nombre_final = f"{base}_{sufijo}"
            sufijo += 1

        renombres[columna] = nombre_final
        usados.add(nombre_final)

    return df.rename(columns=renombres)


def _nombre_columna_semantico(base_snake: str) -> str:
    """Asigna prefijo semantico a una columna en snake_case."""
    mapeo_explicito = {
        'cliente_bt': 'id_cliente_bt',
        'cuil': 'id_cuil',
        'numero_documento': 'id_nro_documento',
        'cliente_nombre': 'customer_name',
        'numero_telefono': 'tel_fijo',
        'numero_trabajo': 'tel_laboral',
        'numero_celular': 'tel_celular',
        'mail': 'txt_mail',
        'nro_cuenta': 'id_nro_cuenta',
        'cuenta': 'tipo_cuenta',
        'sucursal_cuenta': 'id_sucursal_cuenta',
        'agrupador_producto': 'tipo_agrupador_producto',
        'campana_ref': 'tipo_campana_ref',
        'tipo_asignacion': 'tipo_asignacion',
        'gestion_descripcion': 'txt_gestion_descripcion',
        'modulo_codigo': 'id_modulo_codigo',
        'numero_operacion': 'id_nro_operacion',
        'dias_mora': 'cnt_dias_mora',
        'monto_adeudado': 'monto_adeudado_ars',
        'monto_vencido': 'monto_vencido_ars',
        'saldo_capital': 'monto_saldo_capital_ars',
        'interes_adeudado': 'monto_interes_adeudado_ars',
        'iva_interes_adeudado': 'monto_impuesto_valor_agregado_interes_adeudado_ars',
        'oferta_importe': 'oferta_importe',
        'aplica_quita': 'aplica_quita',
        'monto_quita_ars': 'monto_quita_ars',
        'fecha_limite_quita': 'fecha_limite_quita',
        'anticipo_minimo': 'monto_entrega_ars',
        'resumen_productos': 'resumen_productos',
        'estado_cuenta': 'tipo_estado_cuenta',
        'tasa_40': 'tipo_tasa_40',
        'fecha_gestion': 'fecha_gestion',
    }

    if base_snake in mapeo_explicito:
        return mapeo_explicito[base_snake]

    if base_snake.startswith(('fecha_', 'hora_', 'ts_', 'monto_', 'dur_', 'cnt_', 'pct_', 'es_', 'id_', 'tipo_', 'txt_', 'tel_')):
        return base_snake

    if any(token in base_snake for token in ('telefono', 'celular', 'movil')):
        return f"tel_{base_snake}"

    if any(token in base_snake for token in ('fecha_hora', 'timestamp', 'datetime')):
        return f"ts_{base_snake}"

    if any(token in base_snake for token in ('fecha', 'dia', 'mes', 'anio')):
        return f"fecha_{base_snake}"

    if any(token in base_snake for token in ('hora',)):
        return f"hora_{base_snake}"

    if any(token in base_snake for token in ('duracion', 'aht', 'segundo', 'minuto')):
        return f"dur_{base_snake}"

    if any(token in base_snake for token in ('monto', 'saldo', 'interes', 'importe')):
        return f"monto_{base_snake}_ars"

    if any(token in base_snake for token in ('tasa', 'porcentaje', 'ratio')):
        return f"pct_{base_snake}"

    if any(token in base_snake for token in ('cantidad', 'conteo', 'total', 'dias', 'numero')):
        return f"cnt_{base_snake}"

    if any(token in base_snake for token in ('tipo', 'estado', 'categoria', 'clase')):
        return f"tipo_{base_snake}"

    if any(token in base_snake for token in ('id', 'codigo', 'cuenta', 'documento', 'operacion', 'nro', 'cliente')):
        return f"id_{base_snake}"

    if any(token in base_snake for token in ('activo', 'habilitado', 'valido', 'es_')):
        return f"es_{base_snake}"

    return f"txt_{base_snake}"


def normalizar_columnas_semanticas_sin_filtros(df):
    """Normaliza columnas de sin-filtros a snake_case + prefijos semanticos."""
    df = normalizar_columnas_snake_case(df)

    renombres = {}
    usados = set()

    for columna in df.columns:
        base = convertir_a_snake_case(columna)
        candidato = _nombre_columna_semantico(base)

        nombre_final = candidato
        sufijo = 2
        while nombre_final in usados:
            nombre_final = f"{candidato}_{sufijo}"
            sufijo += 1

        renombres[columna] = nombre_final
        usados.add(nombre_final)

    return df.rename(columns=renombres)


def _parsear_decimal(valor):
    """Parsea valores numéricos tolerando formatos europeos y con símbolos."""
    if pd.isna(valor):
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
) -> tuple[str, float | None]:
    """
    Calcula si un cliente es elegible para la quita de intereses y el monto final.

    Implementa la spec funcional 3.1/3.2: aplica 'si' solo si TODAS se cumplen:
      (a) Tipo_Mercado == TIPO_MERCADO_ELEGIBLE
      (b) dias_mora_max cae en algun rango de RANGOS_QUITA (61..365)
      (c) la quita calculada es > 0 (descuento real)
      (d) 0 < monto_quita_ars < monto_adeudado (sanity)
      (e) si EXCLUIR_SI_TIENE_OFERTA, el cliente no tiene oferta pre-calculada

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


def _normalizar_booleano_texto(valor):
    """Normaliza variantes de booleanos a true/false (texto)."""
    if isinstance(valor, bool):
        return 'true' if valor else 'false'

    if pd.isna(valor):
        return ''

    texto = str(valor).strip().lower()
    if texto in {'', 'nan', 'none', 'nat'}:
        return ''
    if texto in {'true', '1', 'si', 'sí', 'yes', 'y', 'verdadero', 't'}:
        return 'true'
    if texto in {'false', '0', 'no', 'n', 'falso', 'f'}:
        return 'false'
    return valor


def _normalizar_aht_mm_ss(valor):
    """Normaliza duración AHT a formato mm:ss."""
    if pd.isna(valor):
        return ''

    texto = str(valor).strip()
    if texto in {'', 'nan', 'NaN', 'None', 'NaT'}:
        return ''

    if ':' in texto:
        partes = [p for p in texto.split(':') if p != '']
        if len(partes) == 2 and all(p.isdigit() for p in partes):
            minutos = int(partes[0])
            segundos = int(partes[1])
            if segundos >= 60:
                minutos += segundos // 60
                segundos = segundos % 60
            return f"{minutos:02d}:{segundos:02d}"
        if len(partes) == 3 and all(p.isdigit() for p in partes):
            horas = int(partes[0])
            minutos = int(partes[1])
            segundos = int(partes[2])
            minutos_totales = (horas * 60) + minutos + (segundos // 60)
            segundos_finales = segundos % 60
            return f"{minutos_totales:02d}:{segundos_finales:02d}"

    numero = _parsear_decimal(texto)
    if numero is None:
        return ''

    segundos_totales = max(int(round(numero)), 0)
    minutos = segundos_totales // 60
    segundos = segundos_totales % 60
    return f"{minutos:02d}:{segundos:02d}"


def normalizar_valores_sin_filtros(df):
    """Aplica normalización de formato para la salida sin-filtros."""
    df = df.copy()

    columnas_monto = [
        'MontoAdeudado',
        'OFERTA_Importe',
        COL_MONTO_VENCIDO,
        'SaldoCapital',
        'InteresAdeudado',
        'IVAInteresAdeudado',
    ]

    for columna in columnas_monto:
        if columna in df.columns:
            df[columna] = df[columna].apply(
                lambda x: _formatear_monto_sin_filtros(x)
            )

    if 'Fecha_Gestion' in df.columns:
        fechas = pd.to_datetime(df['Fecha_Gestion'], dayfirst=True, errors='coerce')
        df['Fecha_Gestion'] = fechas.dt.strftime('%Y-%m-%d').fillna('')

    for columna in ['NumeroTelefono', 'NumeroTrabajo', 'NumeroCelular']:
        if columna in df.columns:
            if columna == 'NumeroCelular':
                df[columna] = df[columna].apply(limpiar_numero_telefono).apply(
                    lambda x: aplicar_prefijo_telefono(x, '549')
                )
            else:
                df[columna] = df[columna].apply(limpiar_numero_telefono).apply(
                    lambda x: aplicar_prefijo_telefono(x, '54')
                )

    if 'Tasa_40' in df.columns:
        def _normalizar_porcentaje(valor):
            if pd.isna(valor):
                return ''
            texto = str(valor).strip()
            if texto in {'', 'nan', 'NaN', 'None', 'NaT'}:
                return ''
            tiene_porcentaje = '%' in texto
            numero = _parsear_decimal(texto.replace('%', ''))
            if numero is None:
                return ''
            if tiene_porcentaje or numero > 1:
                numero = numero / 100
            numero = max(min(numero, 1), 0)
            return ('{:.6f}'.format(numero)).rstrip('0').rstrip('.')

        df['Tasa_40'] = df['Tasa_40'].apply(_normalizar_porcentaje)

    for columna in df.columns:
        if pd.api.types.is_bool_dtype(df[columna]):
            df[columna] = df[columna].apply(lambda x: 'true' if x else 'false')
            continue

        if df[columna].dtype == object:
            valores = df[columna].dropna().astype(str).str.strip().str.lower()
            valores = valores[~valores.isin({'', 'nan', 'none', 'nat'})]
            if not valores.empty and valores.isin({'true', 'false', '1', '0', 'si', 'sí', 'yes', 'no', 'verdadero', 'falso', 'y', 'n', 't', 'f'}).all():
                df[columna] = df[columna].apply(_normalizar_booleano_texto)

    for columna in df.columns:
        if 'aht' in str(columna).lower():
            df[columna] = df[columna].apply(_normalizar_aht_mm_ss)

    return df


def _formatear_monto_sin_filtros(valor):
    """Formatea montos removiendo .00 para enteros y preservando decimales reales."""
    numero = _parsear_decimal(valor)
    if numero is None:
        return ''

    numero_redondeado = round(float(numero), 2)

    if numero_redondeado.is_integer():
        return str(int(numero_redondeado))

    return ('{:.2f}'.format(numero_redondeado)).rstrip('0').rstrip('.')


def _formatear_decimal_fijo_2(valor):
    """Formatea un valor numérico con 2 decimales fijos."""
    numero = _parsear_decimal(valor)
    if numero is None:
        return ''
    return f"{float(numero):.2f}"


def construir_resumen_productos(grupo):
    """Construye el resumen por operacion para un cliente."""
    columnas_orden = [col for col in ['AgrupadorProducto', 'NumeroOperacion'] if col in grupo.columns]
    if columnas_orden:
        grupo_ordenado = grupo.sort_values(columnas_orden, kind='stable')
    else:
        grupo_ordenado = grupo

    items = []
    for _, fila in grupo_ordenado.iterrows():
        producto = corregir_codificacion_texto(fila.get('AgrupadorProducto', ''))
        producto = str(producto).strip()
        if producto in {'', 'nan', 'NaN', 'None', 'NaT'}:
            producto = 'Producto sin especificar'

        deuda = _formatear_decimal_fijo_2(fila.get(COL_MONTO_ADEUDADO))
        if deuda == '':
            deuda = '0.00'

        oferta_valor = _parsear_decimal(fila.get('OFERTA_Importe'))
        oferta_txt = 'NO' if oferta_valor is None or oferta_valor <= 0 else f"{oferta_valor:.2f}"

        items.append(f"{producto} DeudaVencida:{deuda} OfertaImporte:{oferta_txt}")

    return '[' + ' ; '.join(items) + ']'


def validar_contrato_roman(df_salida, df_origen):
    """Valida invariantes clave del contrato ROMAN y emite warning si fallan."""
    errores = []

    if 'id_cuil' in df_salida.columns:
        duplicados = int(df_salida['id_cuil'].astype(str).duplicated().sum())
        if duplicados > 0:
            errores.append(f"id_cuil duplicados detectados: {duplicados}")

    if 'oferta_importe' in df_salida.columns:
        valores = set(df_salida['oferta_importe'].astype(str).str.strip().str.lower().dropna().unique().tolist())
        invalidos = valores - {'si', 'no'}
        if invalidos:
            errores.append(f"oferta_importe contiene valores invalidos: {sorted(invalidos)}")

    if 'monto_adeudado_ars' in df_salida.columns:
        monto_num = pd.Series(pd.to_numeric(df_salida['monto_adeudado_ars'], errors='coerce'))
        invalidos = int(pd.isna(monto_num).sum())
        if invalidos > 0:
            errores.append(f"monto_adeudado_ars no numerico en {invalidos} filas")

    if 'resumen_productos' in df_salida.columns:
        resumen = df_salida['resumen_productos'].astype(str)
        formato_ok = (resumen.str.startswith('[') & resumen.str.endswith(']')).all()
        if not bool(formato_ok):
            errores.append("resumen_productos no respeta delimitadores []")

    if 'id_cuil' in df_salida.columns and 'CUIL' in df_origen.columns and 'NumeroOperacion' in df_origen.columns and 'resumen_productos' in df_salida.columns:
        origen_aux = df_origen.copy()
        origen_aux['CUIL'] = origen_aux['CUIL'].astype(str)
        ops_origen = origen_aux.groupby('CUIL')['NumeroOperacion'].count().to_dict()

        salida_aux = df_salida[['id_cuil', 'resumen_productos']].copy()
        salida_aux['id_cuil'] = salida_aux['id_cuil'].astype(str)

        def _contar_bloques(resumen_txt):
            txt = str(resumen_txt).strip()
            if txt in {'', '[]'}:
                return 0
            cuerpo = txt[1:-1].strip() if txt.startswith('[') and txt.endswith(']') else txt
            if cuerpo == '':
                return 0
            return len([parte for parte in cuerpo.split(' ; ') if parte.strip() != ''])

        salida_aux['bloques'] = salida_aux['resumen_productos'].apply(_contar_bloques)
        mismatches = 0
        for _, fila in salida_aux.iterrows():
            esperado = int(ops_origen.get(fila['id_cuil'], 0))
            if int(fila['bloques']) != esperado:
                mismatches += 1
        if mismatches > 0:
            errores.append(f"resumen_productos desalineado contra NumeroOperacion en {mismatches} filas")

    if 'aplica_quita' in df_salida.columns:
        valores = set(df_salida['aplica_quita'].astype(str).str.strip().str.lower().dropna().unique().tolist())
        invalidos = valores - {'si', 'no'}
        if invalidos:
            errores.append(f"aplica_quita contiene valores invalidos: {sorted(invalidos)}")

        aplica = df_salida['aplica_quita'].astype(str).str.strip().str.lower()
        total_clientes = len(df_salida)
        elegibles = int((aplica == 'si').sum())

        if {'monto_quita_ars', 'monto_adeudado_ars'}.issubset(df_salida.columns):
            mask_si = aplica == 'si'
            monto_quita_num = pd.to_numeric(df_salida.loc[mask_si, 'monto_quita_ars'], errors='coerce')
            monto_adeu_num = pd.to_numeric(df_salida.loc[mask_si, 'monto_adeudado_ars'], errors='coerce')

            no_numerico = int(pd.isna(monto_quita_num).sum())
            if no_numerico > 0:
                errores.append(f"aplica_quita='si' con monto_quita_ars no numerico en {no_numerico} filas")

            fuera_rango = int(((monto_quita_num <= 0) | (monto_quita_num >= monto_adeu_num)).sum())
            if fuera_rango > 0:
                errores.append(f"monto_quita_ars fuera de (0, monto_adeudado_ars) en {fuera_rango} filas")

        if 'fecha_limite_quita' in df_salida.columns:
            mask_si = aplica == 'si'
            fechas_si = df_salida.loc[mask_si, 'fecha_limite_quita'].astype(str).str.strip()
            sin_fecha = int((fechas_si == '').sum())
            if sin_fecha > 0:
                errores.append(f"aplica_quita='si' sin fecha_limite_quita en {sin_fecha} filas")

            mask_no = aplica == 'no'
            quita_no = df_salida.loc[mask_no]
            if 'monto_quita_ars' in quita_no.columns:
                monto_no_vacio = int((quita_no['monto_quita_ars'].astype(str).str.strip() != '').sum())
                if monto_no_vacio > 0:
                    errores.append(f"aplica_quita='no' con monto_quita_ars no vacio en {monto_no_vacio} filas")
            fecha_no_vacio = int((quita_no['fecha_limite_quita'].astype(str).str.strip() != '').sum())
            if fecha_no_vacio > 0:
                errores.append(f"aplica_quita='no' con fecha_limite_quita no vacio en {fecha_no_vacio} filas")

        print(f"\n[VALIDACION ROMAN] Quita: {elegibles}/{total_clientes} clientes elegibles (aplica_quita='si')")

    if errores:
        print("\n[VALIDACION ROMAN] Se detectaron inconsistencias:")
        for error in errores:
            print(f"  - {error}")
    else:
        print("\n[VALIDACION ROMAN] OK: contrato de salida validado")


def limpiar_numero_telefono(valor) -> str:
    """
    Normaliza un número telefónico como texto.

    - Mantiene vacíos como vacíos
    - Elimina guiones y espacios
    - Elimina sufijo decimal tipo ".0"
    """
    if pd.isna(valor):
        return ''

    telefono = str(valor).strip()
    if telefono in {'', 'nan', 'NaN', 'None', 'NaT'}:
        return ''

    telefono = telefono.replace('-', '').replace(' ', '')

    if re.fullmatch(r'\d+\.0+', telefono):
        telefono = telefono.split('.')[0]

    return telefono


def _remover_prefijo_15(num: str) -> str:
    """Elimina el '0' de larga distancia inicial y el '15' embebido en móviles.

    Sólo se remueve el '15' si al quitarlo la parte nacional queda en 10
    dígitos (código de área 2–4 + número local 7–8).
    """
    if not num:
        return ''

    if num.startswith('0'):
        num = num[1:]

    if len(num) != 12:
        return num

    for pos in (2, 3, 4):
        if num[pos:pos + 2] == '15':
            return num[:pos] + num[pos + 2:]

    return num


def aplicar_prefijo_telefono(numero: str, prefijo: str) -> str:
    """
    Agrega prefijo telefónico aplicando normalización previa.

    - Elimina '0' de larga distancia inicial
    - Elimina '15' móvil embebido cuando el número calza como celular
    - Evita duplicar el prefijo internacional
    - Para prefijo 549: si el número ya empieza con 54 pero no con 549,
      se corrige a 549 conservando el resto.
    """
    if not numero:
        return ''

    if numero.startswith(prefijo):
        return numero

    if prefijo == '549' and numero.startswith('54'):
        return f"549{_remover_prefijo_15(numero[2:])}"

    if prefijo == '54' and numero.startswith('54'):
        return numero

    parte_nacional = _remover_prefijo_15(numero)

    if prefijo == '549' and parte_nacional.startswith('9'):
        return f"54{parte_nacional}"

    return f"{prefijo}{parte_nacional}"

def deduplicar_por_telefonos(df):
    """
    Deduplica clientes que comparten números de teléfono.
    Mantiene el cliente con mayor MontoAdeudado.
    En caso de empate, mantiene el que tiene más NumeroOperacion (productos).

    Args:
        df: DataFrame consolidado con una fila por cliente

    Returns:
        Tuple (df_unicos, df_descartados): DataFrames con clientes únicos y descartados
    """
    # Crear copia para no modificar el original
    df = df.copy()

    # Crear columna auxiliar para contar productos
    df['_num_productos'] = df['NumeroOperacion'].apply(
        lambda x: len(str(x).split(',')) if pd.notna(x) and str(x).strip() != '' else 0
    )

    # Convertir MontoAdeudado a numérico para comparación (manejar formato europeo con coma)
    df['_monto_numerico'] = df['MontoAdeudado'].apply(
        lambda x: float(str(x).replace(',', '.')) if pd.notna(x) and str(x).strip() != '' else 0
    )

    # Listas para almacenar resultados
    clientes_unicos = []
    clientes_descartados = []
    procesados = set()

    # Limpiar y normalizar teléfonos para comparación
    for col in ['NumeroTelefono', 'NumeroTrabajo', 'NumeroCelular']:
        if col in df.columns:
            df[f'_{col}_clean'] = df[col].astype(str).str.strip()
            df[f'_{col}_clean'] = df[f'_{col}_clean'].replace(['nan', 'NaN', 'None', 'NaT', ''], '')

    for idx, fila in df.iterrows():
        cliente_bt = fila['Cliente_BT']

        if cliente_bt in procesados:
            continue

        # Extraer teléfonos de esta fila
        tel = fila.get('_NumeroTelefono_clean', '')
        trab = fila.get('_NumeroTrabajo_clean', '')
        cel = fila.get('_NumeroCelular_clean', '')

        # Si no tiene ningún teléfono, mantener sin deduplicar
        if tel == '' and trab == '' and cel == '':
            clientes_unicos.append(fila)
            procesados.add(cliente_bt)
            continue

        # Buscar otros clientes con los mismos teléfonos
        masks = []
        if tel != '':
            masks.append(df['_NumeroTelefono_clean'] == tel)
        if trab != '':
            masks.append(df['_NumeroTrabajo_clean'] == trab)
        if cel != '':
            masks.append(df['_NumeroCelular_clean'] == cel)

        # Combinar máscaras (cualquier teléfono que coincida)
        if masks:
            mask_final = masks[0]
            for m in masks[1:]:
                mask_final = mask_final | m
        else:
            clientes_unicos.append(fila)
            procesados.add(cliente_bt)
            continue

        # Obtener grupo de clientes con teléfonos compartidos
        grupo = df[mask_final].copy()

        if len(grupo) == 1:
            # No hay duplicados
            clientes_unicos.append(fila)
            procesados.add(cliente_bt)
        else:
            # Hay duplicados - ordenar por MontoAdeudado (desc) y _num_productos (desc)
            grupo_ordenado = grupo.sort_values(
                by=['_monto_numerico', '_num_productos'],
                ascending=[False, False]
            )

            # Mantener el primero (mayor deuda, más productos)
            mejor_cliente = grupo_ordenado.iloc[0]
            clientes_unicos.append(mejor_cliente)

            # Descartar los demás
            for _, cliente_descartado in grupo_ordenado.iloc[1:].iterrows():
                if cliente_descartado['Cliente_BT'] not in procesados:
                    clientes_descartados.append(cliente_descartado)

            # Marcar todos como procesados
            for cliente_bt_proc in grupo['Cliente_BT']:
                procesados.add(cliente_bt_proc)

    # Convertir listas a DataFrames
    df_unicos = pd.DataFrame(clientes_unicos)
    df_descartados = pd.DataFrame(clientes_descartados) if clientes_descartados else pd.DataFrame()

    # Preservar el orden relativo original de los sobrevivientes cuando está disponible
    if '_orden_original' in df_unicos.columns:
        df_unicos = df_unicos.sort_values(by='_orden_original', kind='stable').reset_index(drop=True)
    if len(df_descartados) > 0 and '_orden_original' in df_descartados.columns:
        df_descartados = df_descartados.sort_values(by='_orden_original', kind='stable').reset_index(drop=True)

    # Eliminar columnas auxiliares
    columnas_auxiliares = ['_num_productos', '_monto_numerico', '_NumeroTelefono_clean', '_NumeroTrabajo_clean', '_NumeroCelular_clean']
    for col in columnas_auxiliares:
        if col in df_unicos.columns:
            df_unicos = df_unicos.drop(columns=[col])
        if len(df_descartados) > 0 and col in df_descartados.columns:
            df_descartados = df_descartados.drop(columns=[col])

    return df_unicos, df_descartados


def filtrar_acuerdos_vigentes(df):
    """
    Excluye filas (productos) que tienen acuerdos vigentes con el cliente.
    
    Un acuerdo se considera vigente cuando:
    1. Gestion_Estado es '07. Promesa de Pago Pactada' o '08. Gestión de Refinanciación'
    2. Fecha_Gestion tiene 7 días o menos de antigüedad respecto de la fecha actual
    
    Ambas condiciones deben cumplirse para excluir la fila.
    Filas sin Fecha_Gestion o con fecha inválida NO se excluyen.
    
    Args:
        df: DataFrame con columnas Gestion_Estado y Fecha_Gestion
        
    Returns:
        DataFrame sin las filas que tienen acuerdos vigentes
    """
    if 'Gestion_Estado' not in df.columns or 'Fecha_Gestion' not in df.columns:
        print("Advertencia: No se encontraron las columnas Gestion_Estado y/o Fecha_Gestion. "
              "No se aplica filtro de acuerdos vigentes.")
        return df
    
    filas_antes = len(df)
    
    # Estados que representan acuerdos
    estados_acuerdo = [
        '07. Promesa de Pago Pactada',
        '08. Gestión de Refinanciación'
    ]
    
    # Limpiar Gestion_Estado: convertir a string y strip
    df['Gestion_Estado'] = df['Gestion_Estado'].astype(str).str.strip()
    df['Gestion_Estado'] = df['Gestion_Estado'].replace(['nan', 'NaN', 'None', 'NaT'], '')
    
    # Parsear Fecha_Gestion a datetime (formato D/M/YYYY)
    df['_fecha_gestion_parsed'] = pd.to_datetime(
        df['Fecha_Gestion'], 
        dayfirst=True, 
        errors='coerce'
    )
    
    fecha_actual = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Calcular diferencia en días
    df['_dias_desde_gestion'] = (fecha_actual - df['_fecha_gestion_parsed']).dt.days
    
    # Identificar filas con acuerdo vigente:
    # - Gestion_Estado es uno de los estados de acuerdo
    # - Fecha_Gestion tiene 7 días o menos de antigüedad (diferencia <= 7)
    mask_acuerdo_vigente = (
        (df['Gestion_Estado'].isin(estados_acuerdo)) &
        (df['_dias_desde_gestion'].notna()) &
        (df['_dias_desde_gestion'] <= 7)
    )
    
    filas_excluidas = mask_acuerdo_vigente.sum()
    
    # Información de diagnóstico
    print(f"\n--- Filtro de acuerdos vigentes ---")
    print(f"Filas con Gestion_Estado de acuerdo: {df['Gestion_Estado'].isin(estados_acuerdo).sum()}")
    print(f"Filas con acuerdo vigente (<= 7 días): {filas_excluidas}")
    
    if filas_excluidas > 0:
        # Detalle de los excluidos
        df_excluidos = df[mask_acuerdo_vigente]
        for estado in estados_acuerdo:
            count = (df_excluidos['Gestion_Estado'] == estado).sum()
            if count > 0:
                print(f"  - {estado}: {count} filas excluidas")
    
    # Filtrar: mantener las filas que NO tienen acuerdo vigente
    df_filtrado = df[~mask_acuerdo_vigente].copy()
    
    # Eliminar columnas auxiliares de cálculo
    df_filtrado = df_filtrado.drop(columns=['_fecha_gestion_parsed', '_dias_desde_gestion'])
    
    print(f"Filas antes del filtro: {filas_antes}")
    print(f"Filas después del filtro: {len(df_filtrado)}")
    
    return df_filtrado


def leer_csv_con_codificacion(archivo_csv, separador=';'):
    """
    Intenta leer un CSV probando diferentes codificaciones comunes.
    Retorna el DataFrame y la codificación utilizada.
    """
    # Lista de codificaciones a probar (ordenadas por probabilidad)
    codificaciones = ['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'utf-16']
    
    for encoding in codificaciones:
        try:
            df = pd.read_csv(archivo_csv, sep=separador, encoding=encoding, low_memory=False)
            print(f"Archivo leído exitosamente con codificación: {encoding}")
            return df, encoding
        except UnicodeDecodeError:
            continue
        except Exception as e:
            # Si es otro tipo de error, lo relanzamos
            raise
    
    # Si ninguna codificación funcionó, intentar con errors='ignore' o 'replace'
    print("Advertencia: No se pudo leer con codificaciones estándar, intentando con manejo de errores...")
    try:
        df = pd.read_csv(archivo_csv, sep=separador, encoding='latin-1', encoding_errors='replace', low_memory=False)
        print("Archivo leído con codificación latin-1 y manejo de errores 'replace'")
        return df, 'latin-1'
    except Exception as e:
        raise Exception(f"No se pudo leer el archivo con ninguna codificación: {str(e)}")


def listar_archivos_entrada(carpeta_recibida):
    """
    Devuelve los archivos de entrada soportados (CSV y Excel).
    """
    patrones = ("*.csv", "*.xlsx", "*.xls")
    archivos_entrada = []
    for patron in patrones:
        archivos_entrada.extend(carpeta_recibida.glob(patron))
    return sorted(archivos_entrada)


def leer_archivo_entrada(archivo_entrada, separador=';'):
    """
    Lee un archivo de entrada CSV o Excel y retorna DataFrame.
    """
    extension = archivo_entrada.suffix.lower()

    if extension == '.csv':
        return leer_csv_con_codificacion(archivo_entrada, separador=separador)

    if extension in ('.xlsx', '.xls'):
        df = pd.read_excel(archivo_entrada)
        print(f"Archivo Excel leído exitosamente: {archivo_entrada.name}")
        return df, 'excel'

    raise ValueError(f"Formato de archivo no soportado: {archivo_entrada.name}")

def procesar_base():
    """
    Lee el CSV de la carpeta base-recibida, filtra filas con OFERTA_Importe > 0
    y genera un nuevo CSV en base-generada con las columnas especificadas.
    """
    # Definir rutas
    base_dir = Path(__file__).parent.parent
    carpeta_recibida = base_dir / "base-recibida"
    carpeta_generada = base_dir / "base-generada" / "con-filtros"
    carpeta_debug = carpeta_generada / "debug"
    
    # Crear carpetas de salida si no existen
    carpeta_generada.mkdir(exist_ok=True)
    carpeta_debug.mkdir(exist_ok=True)
    
    # Buscar archivos de entrada soportados en la carpeta recibida
    archivos_entrada = listar_archivos_entrada(carpeta_recibida)

    if not archivos_entrada:
        print("No se encontraron archivos CSV o Excel en la carpeta base-recibida")
        return

    # Procesar cada archivo encontrado
    for archivo_entrada in archivos_entrada:
        print(f"Procesando archivo: {archivo_entrada.name}")
        
        try:
            # Leer CSV (con fallback de codificación) o Excel
            df, encoding_usado = leer_archivo_entrada(archivo_entrada, separador=';')
            df = normalizar_encabezados_nuevas_columnas(df)
            
            # Convertir OFERTA_Importe a numérico, manejando formato europeo (coma como decimal)
            # Si no existe la columna, crearla vacía
            if 'OFERTA_Importe' in df.columns:
                # Convertir a string, reemplazar coma por punto, y luego a numérico
                df['OFERTA_Importe'] = df['OFERTA_Importe'].astype(str).str.replace(',', '.', regex=False)
                df['OFERTA_Importe'] = pd.to_numeric(df['OFERTA_Importe'], errors='coerce')
            else:
                print(f"Advertencia: La columna 'OFERTA_Importe' no existe en el archivo. Se creará vacía.")
                df['OFERTA_Importe'] = pd.NA
            
            # Verificar que la columna ModuloCodigo existe
            if 'ModuloCodigo' not in df.columns:
                print(f"Error: La columna 'ModuloCodigo' no existe en el archivo")
                continue
            
            # Convertir ModuloCodigo a string para comparación robusta (puede ser numérico o string)
            df['ModuloCodigo'] = df['ModuloCodigo'].astype(str)
            
            # Filtrar filas donde OFERTA_Importe > 0 y ModuloCodigo == "201"
            df_filtrado = df[
                (df['OFERTA_Importe'].notna()) & 
                (df['OFERTA_Importe'] > 0) & 
                (df['ModuloCodigo'] == '201')
            ].copy()
            
            # Información de depuración
            print(f"Filas originales: {len(df)}")
            print(f"Valores no nulos en OFERTA_Importe: {df['OFERTA_Importe'].notna().sum()}")
            print(f"Valores > 0 en OFERTA_Importe: {(df['OFERTA_Importe'] > 0).sum()}")
            print(f"Filas con ModuloCodigo == '201': {(df['ModuloCodigo'] == '201').sum()}")
            print(f"Filas filtradas (OFERTA_Importe > 0 y ModuloCodigo == '201'): {len(df_filtrado)}")
            
            if len(df_filtrado) == 0:
                print(f"No se encontraron filas con OFERTA_Importe > 0 y ModuloCodigo == 201 en {archivo_entrada.name}")
                continue
            
            # Definir las columnas a mantener
            columnas_seleccionadas = [
                'Cliente_BT',
                'CUIL',
                'NumeroDocumento',
                'ClienteNombre',
                'NumeroTelefono',
                'NumeroTrabajo',
                'NumeroCelular',
                'Mail',
                'Nro Cuenta',
                'Cuenta',
                'Sucursal_Cuenta',
                'AgrupadorProducto',
                COL_CAMPANA_REF,
                COL_TIPO_ASIGNACION,
                COL_GESTION_DESCRIPCION,
                'ModuloCodigo',
                'NumeroOperacion',
                'Dias_Mora',
                'MontoAdeudado',
                COL_MONTO_VENCIDO,
                'SaldoCapital',
                'InteresAdeudado',
                'IVAInteresAdeudado',
                'OFERTA_Importe'
            ]
            
            # Verificar que todas las columnas existan
            columnas_faltantes = [col for col in columnas_seleccionadas if col not in df_filtrado.columns]
            if columnas_faltantes:
                print(f"Advertencia: Las siguientes columnas no se encontraron: {columnas_faltantes}")
                # Solo seleccionar las columnas que existen
                columnas_seleccionadas = [col for col in columnas_seleccionadas if col in df_filtrado.columns]
            
            # Seleccionar solo las columnas especificadas
            df_resultado = df_filtrado[columnas_seleccionadas].copy()
            
            # Convertir NumeroDocumento y Nro Cuenta a enteros (sin decimales)
            # Manejar valores nulos/vacíos apropiadamente
            campos_enteros = ['NumeroDocumento', 'Nro Cuenta']
            for campo in campos_enteros:
                if campo in df_resultado.columns:
                    # Convertir a string primero para manejar todos los casos
                    df_resultado[campo] = df_resultado[campo].astype(str)
                    # Reemplazar valores nulos/NaN por string vacío
                    df_resultado[campo] = df_resultado[campo].replace(['nan', 'NaN', 'None', 'NaT'], '')
                    # Convertir a numérico y luego a entero, eliminando el .0
                    df_resultado[campo] = pd.to_numeric(df_resultado[campo], errors='coerce')
                    # Convertir a string eliminando el .0 de los enteros
                    df_resultado[campo] = df_resultado[campo].apply(
                        lambda x: '' if pd.isna(x) else str(int(x)) if pd.notna(x) else ''
                    )
            
            # Limpiar números de teléfono: eliminar guiones "-"
            campos_telefono = ['NumeroTelefono', 'NumeroTrabajo', 'NumeroCelular']
            numero_hardcodeado = '3519999999'
            
            for campo in campos_telefono:
                if campo in df_resultado.columns:
                    serie_limpia = df_resultado[campo].apply(limpiar_numero_telefono)

                    valores_reemplazados = (serie_limpia == numero_hardcodeado).sum()
                    if valores_reemplazados > 0:
                        print(f"Valores '{numero_hardcodeado}' reemplazados por vacío en {campo}: {valores_reemplazados}")
                    serie_limpia = serie_limpia.replace(numero_hardcodeado, '')

                    if campo == 'NumeroTelefono':
                        serie_limpia = serie_limpia.apply(lambda x: aplicar_prefijo_telefono(x, '54'))
                    elif campo == 'NumeroCelular':
                        serie_limpia = serie_limpia.apply(lambda x: aplicar_prefijo_telefono(x, '549'))

                    df_resultado[campo] = serie_limpia

            # Limpiar campos de texto adicionales
            for campo in [COL_TIPO_ASIGNACION, COL_GESTION_DESCRIPCION]:
                if campo in df_resultado.columns:
                    df_resultado[campo] = df_resultado[campo].astype(str)
                    df_resultado[campo] = df_resultado[campo].replace(['nan', 'NaN', 'None', 'NaT'], '')
                    df_resultado[campo] = df_resultado[campo].apply(corregir_codificacion_texto)

            if COL_CAMPANA_REF in df_resultado.columns:
                df_resultado['tipo_campana_ref'] = df_resultado[COL_CAMPANA_REF].astype(str)
                df_resultado['tipo_campana_ref'] = df_resultado['tipo_campana_ref'].replace(['nan', 'NaN', 'None', 'NaT'], '')
                df_resultado['tipo_campana_ref'] = df_resultado['tipo_campana_ref'].apply(corregir_codificacion_texto)
                df_resultado = df_resultado.drop(columns=[COL_CAMPANA_REF])
            else:
                df_resultado['tipo_campana_ref'] = ''
            
            # Guardar el CSV con una fila por producto en la carpeta debug
            nombre_archivo_debug = f"debug_{archivo_entrada.stem}.csv"
            ruta_debug = carpeta_debug / nombre_archivo_debug
            df_resultado.to_csv(ruta_debug, sep=';', index=False, encoding='utf-8')
            print(f"Archivo debug generado (una fila por producto): {ruta_debug}")
            print(f"Total de filas en el archivo debug: {len(df_resultado)}")
            
            # Consolidar por Cliente_BT (una fila por cliente)
            # Convertir MontoAdeudado a numérico (manejando formato europeo con coma)
            if 'MontoAdeudado' in df_resultado.columns:
                df_resultado['MontoAdeudado'] = df_resultado['MontoAdeudado'].astype(str).str.replace(',', '.', regex=False)
                df_resultado['MontoAdeudado'] = pd.to_numeric(df_resultado['MontoAdeudado'], errors='coerce')

            if COL_MONTO_VENCIDO in df_resultado.columns:
                df_resultado[COL_MONTO_VENCIDO] = df_resultado[COL_MONTO_VENCIDO].astype(str).str.replace(',', '.', regex=False)
                df_resultado[COL_MONTO_VENCIDO] = pd.to_numeric(df_resultado[COL_MONTO_VENCIDO], errors='coerce')
            
            # Convertir Dias_Mora a numérico
            if 'Dias_Mora' in df_resultado.columns:
                df_resultado['Dias_Mora'] = pd.to_numeric(df_resultado['Dias_Mora'], errors='coerce')
            
            # Convertir NumeroOperacion y AgrupadorProducto a string para concatenación
            if 'NumeroOperacion' in df_resultado.columns:
                df_resultado['NumeroOperacion'] = df_resultado['NumeroOperacion'].astype(str)
                df_resultado['NumeroOperacion'] = df_resultado['NumeroOperacion'].replace(['nan', 'NaN', 'None', 'NaT'], '')
            
            if 'AgrupadorProducto' in df_resultado.columns:
                df_resultado['AgrupadorProducto'] = df_resultado['AgrupadorProducto'].astype(str)
                df_resultado['AgrupadorProducto'] = df_resultado['AgrupadorProducto'].replace(['nan', 'NaN', 'None', 'NaT'], '')
                # Corregir problemas de codificación en AgrupadorProducto
                df_resultado['AgrupadorProducto'] = df_resultado['AgrupadorProducto'].apply(corregir_codificacion_texto)
            
            # Agrupar por Cliente_BT y aplicar las reglas de consolidación
            def consolidar_grupo(grupo):
                resultado = grupo.iloc[0].copy()  # Tomar valores de la primera fila
                
                # Sumar MontoAdeudado y OFERTA_Importe
                if 'MontoAdeudado' in grupo.columns:
                    resultado['MontoAdeudado'] = grupo['MontoAdeudado'].sum()

                if COL_MONTO_VENCIDO in grupo.columns:
                    resultado[COL_MONTO_VENCIDO] = grupo[COL_MONTO_VENCIDO].sum()

                if 'OFERTA_Importe' in grupo.columns:
                    resultado['OFERTA_Importe'] = grupo['OFERTA_Importe'].sum()
                
                # Tomar el máximo de Dias_Mora
                if 'Dias_Mora' in grupo.columns:
                    resultado['Dias_Mora'] = grupo['Dias_Mora'].max()
                
                # Concatenar NumeroOperacion separado por comas
                if 'NumeroOperacion' in grupo.columns:
                    operaciones = grupo['NumeroOperacion'].dropna()
                    operaciones = operaciones[operaciones != '']
                    if len(operaciones) > 0:
                        resultado['NumeroOperacion'] = ','.join(operaciones.unique())
                    else:
                        resultado['NumeroOperacion'] = ''
                
                # Concatenar AgrupadorProducto separado por comas
                if 'AgrupadorProducto' in grupo.columns:
                    productos = grupo['AgrupadorProducto'].dropna()
                    productos = productos[productos != '']
                    if len(productos) > 0:
                        # Corregir codificación antes de concatenar (por si acaso)
                        productos_corregidos = [corregir_codificacion_texto(str(p)) for p in productos.unique()]
                        resultado['AgrupadorProducto'] = ','.join(productos_corregidos)
                    else:
                        resultado['AgrupadorProducto'] = ''
                
                return resultado
            
            # Agrupar por Cliente_BT y consolidar
            df_consolidado = df_resultado.groupby('Cliente_BT').apply(consolidar_grupo).reset_index(drop=True)

            # Deduplicar clientes con teléfonos compartidos
            print("\n--- Deduplicación por teléfonos ---")
            print(f"Filas antes de deduplicación: {len(df_consolidado)}")

            df_consolidado, df_descartados = deduplicar_por_telefonos(df_consolidado)

            print(f"Filas después de deduplicación: {len(df_consolidado)}")
            print(f"Clientes descartados: {len(df_descartados)}")

            # Convertir MontoAdeudado y OFERTA_Importe de vuelta a string con formato europeo (coma como decimal)
            if 'MontoAdeudado' in df_consolidado.columns:
                df_consolidado['MontoAdeudado'] = df_consolidado['MontoAdeudado'].apply(
                    lambda x: str(x).replace('.', ',') if pd.notna(x) else ''
                )

            if COL_MONTO_VENCIDO in df_consolidado.columns:
                df_consolidado[COL_MONTO_VENCIDO] = df_consolidado[COL_MONTO_VENCIDO].apply(
                    lambda x: str(x).replace('.', ',') if pd.notna(x) else ''
                )
            
            if 'OFERTA_Importe' in df_consolidado.columns:
                df_consolidado['OFERTA_Importe'] = df_consolidado['OFERTA_Importe'].apply(
                    lambda x: str(x).replace('.', ',') if pd.notna(x) else ''
                )
            
            # Convertir Dias_Mora a string (entero)
            if 'Dias_Mora' in df_consolidado.columns:
                df_consolidado['Dias_Mora'] = df_consolidado['Dias_Mora'].apply(
                    lambda x: str(int(x)) if pd.notna(x) else ''
                )
            
            # Generar nombre del archivo de salida consolidado con formato base_bancor_DDMMAAAA.csv
            fecha_actual = datetime.now()
            nombre_archivo_salida = f"base_bancor_{fecha_actual.strftime('%d%m%Y')}.csv"
            ruta_salida = carpeta_generada / nombre_archivo_salida
            
            # Guardar el CSV consolidado (una fila por cliente)
            # Usar utf-8-sig para asegurar compatibilidad con Excel y evitar problemas de codificación
            df_consolidado.to_csv(ruta_salida, sep=';', index=False, encoding='utf-8-sig')
            
            print(f"Archivo consolidado generado exitosamente (una fila por cliente): {ruta_salida}")
            print(f"Total de filas en el archivo consolidado: {len(df_consolidado)}")
            print(f"Clientes únicos: {df_resultado['Cliente_BT'].nunique()}")

            # Guardar clientes descartados en carpeta backup
            if len(df_descartados) > 0:
                carpeta_backup = carpeta_generada / "backup"
                carpeta_backup.mkdir(exist_ok=True)

                backup_filename = f"descartados_por_telefono_{fecha_actual.strftime('%d%m%Y')}.csv"
                backup_path = carpeta_backup / backup_filename

                # Aplicar formato europeo a los campos numéricos de los descartados
                df_descartados_output = df_descartados.copy()
                if 'MontoAdeudado' in df_descartados_output.columns:
                    df_descartados_output['MontoAdeudado'] = df_descartados_output['MontoAdeudado'].apply(
                        lambda x: str(x).replace('.', ',') if pd.notna(x) and '.' in str(x) else str(x) if pd.notna(x) else ''
                    )
                if COL_MONTO_VENCIDO in df_descartados_output.columns:
                    df_descartados_output[COL_MONTO_VENCIDO] = df_descartados_output[COL_MONTO_VENCIDO].apply(
                        lambda x: str(x).replace('.', ',') if pd.notna(x) and '.' in str(x) else str(x) if pd.notna(x) else ''
                    )
                if 'OFERTA_Importe' in df_descartados_output.columns:
                    df_descartados_output['OFERTA_Importe'] = df_descartados_output['OFERTA_Importe'].apply(
                        lambda x: str(x).replace('.', ',') if pd.notna(x) and '.' in str(x) else str(x) if pd.notna(x) else ''
                    )
                if 'Dias_Mora' in df_descartados_output.columns:
                    df_descartados_output['Dias_Mora'] = df_descartados_output['Dias_Mora'].apply(
                        lambda x: str(int(float(x))) if pd.notna(x) and str(x).strip() != '' else ''
                    )

                df_descartados_output.to_csv(backup_path, sep=';', index=False, encoding='utf-8-sig')
                print(f"\nArchivo de descartados guardado: {backup_path}")
                print(f"Total de clientes descartados: {len(df_descartados_output)}")
            else:
                print("\nNo hay clientes descartados por deduplicación")

        except Exception as e:
            print(f"Error al procesar {archivo_entrada.name}: {str(e)}")
            continue

def procesar_base_completa():
    """
    Procesa la base completa SIN filtros (sin filtro de OFERTA_Importe > 0 ni ModuloCodigo == '201').
    Incluye las mismas 20 columnas que procesar_base() mas dos columnas adicionales:
    - Estado Cuenta
    - Tasa_40
    Genera un archivo consolidado por Cliente_BT con deduplicacion por telefonos.
    """
    # Definir rutas
    base_dir = Path(__file__).parent.parent
    carpeta_recibida = base_dir / "base-recibida"
    carpeta_generada = base_dir / "base-generada" / "sin-filtros"
    carpeta_debug = carpeta_generada / "debug"

    # Crear carpetas de salida si no existen
    carpeta_generada.mkdir(parents=True, exist_ok=True)
    carpeta_debug.mkdir(exist_ok=True)

    # Buscar archivos de entrada soportados en la carpeta recibida
    archivos_entrada = listar_archivos_entrada(carpeta_recibida)

    if not archivos_entrada:
        print("No se encontraron archivos CSV o Excel en la carpeta base-recibida")
        return

    # Procesar cada archivo encontrado
    for archivo_entrada in archivos_entrada:
        print(f"Procesando archivo (base completa): {archivo_entrada.name}")

        try:
            # Leer CSV (con fallback de codificación) o Excel
            df, encoding_usado = leer_archivo_entrada(archivo_entrada, separador=';')
            df = normalizar_encabezados_nuevas_columnas(df)

            # Convertir OFERTA_Importe a numérico para procesamiento posterior
            # Si no existe la columna, crearla vacía
            if 'OFERTA_Importe' in df.columns:
                df['OFERTA_Importe'] = df['OFERTA_Importe'].astype(str).str.replace(',', '.', regex=False)
                df['OFERTA_Importe'] = pd.to_numeric(df['OFERTA_Importe'], errors='coerce')
            else:
                print(f"Advertencia: La columna 'OFERTA_Importe' no existe en el archivo. Se creará vacía.")
                df['OFERTA_Importe'] = pd.NA

            # Filtrar filas con EstadoDescripcion == "Cancelada"
            if 'EstadoDescripcion' in df.columns:
                df['EstadoDescripcion'] = df['EstadoDescripcion'].astype(str).str.strip()
                filas_canceladas = (df['EstadoDescripcion'] == 'Cancelada').sum()
                print(f"Filas con EstadoDescripcion == 'Cancelada': {filas_canceladas}")
                df = df[df['EstadoDescripcion'] != 'Cancelada'].copy()
                print(f"Filas después de excluir canceladas: {len(df)}")

            # Filtrar filas con SaldoCapital == 0
            if 'SaldoCapital' in df.columns:
                df['_SaldoCapital_num'] = df['SaldoCapital'].astype(str).str.replace(',', '.', regex=False)
                df['_SaldoCapital_num'] = pd.to_numeric(df['_SaldoCapital_num'], errors='coerce')
                filas_saldo_cero = ((df['_SaldoCapital_num'].notna()) & (df['_SaldoCapital_num'] == 0)).sum()
                print(f"Filas con SaldoCapital == 0: {filas_saldo_cero}")
                df = df[(df['_SaldoCapital_num'].isna()) | (df['_SaldoCapital_num'] != 0)].copy()
                df = df.drop(columns=['_SaldoCapital_num'])
                print(f"Filas después de excluir SaldoCapital == 0: {len(df)}")

            # Convertir MontoAdeudado a numérico para filtrado
            if 'MontoAdeudado' in df.columns:
                df['MontoAdeudado'] = df['MontoAdeudado'].astype(str).str.replace(',', '.', regex=False)
                df['MontoAdeudado'] = pd.to_numeric(df['MontoAdeudado'], errors='coerce')

            # Filtrar solo por MontoAdeudado > 0 (excluir clientes sin deuda)
            df_filtrado = df[
                (df['MontoAdeudado'].notna()) &
                (df['MontoAdeudado'] > 0)
            ].copy()

            print(f"Filas originales: {len(df)}")
            print(f"Filas con MontoAdeudado > 0: {len(df_filtrado)}")
            print(f"Filas excluidas por MontoAdeudado <= 0 o nulo: {len(df) - len(df_filtrado)}")

            if len(df_filtrado) == 0:
                print(f"El archivo {archivo_entrada.name} está vacío")
                continue

            # Convertir ModuloCodigo a string
            if 'ModuloCodigo' in df_filtrado.columns:
                df_filtrado['ModuloCodigo'] = df_filtrado['ModuloCodigo'].astype(str)

            # Definir las columnas a mantener (20 originales + 2 extra + 2 para filtro de acuerdos)
            columnas_seleccionadas = [
                'Cliente_BT',
                'CUIL',
                'NumeroDocumento',
                'ClienteNombre',
                'NumeroTelefono',
                'NumeroTrabajo',
                'NumeroCelular',
                'Mail',
                'Nro Cuenta',
                'Cuenta',
                'Sucursal_Cuenta',
                'AgrupadorProducto',
                COL_CAMPANA_REF,
                COL_TIPO_ASIGNACION,
                COL_GESTION_DESCRIPCION,
                'ModuloCodigo',
                'NumeroOperacion',
                'Dias_Mora',
                'MontoAdeudado',
                COL_MONTO_VENCIDO,
                'SaldoCapital',
                'InteresAdeudado',
                'IVAInteresAdeudado',
                'OFERTA_Importe',
                'AnticipoMinimo',
                'Estado Cuenta',
                'Tasa_40',
                'Gestion_Estado',
                'Fecha_Gestion',
                COL_TIPO_MERCADO,
                COL_COMPENSATORIO,
                COL_PUNITORIOS
            ]

            # Verificar que todas las columnas existan
            columnas_faltantes = [col for col in columnas_seleccionadas if col not in df_filtrado.columns]
            if columnas_faltantes:
                print(f"Advertencia: Las siguientes columnas no se encontraron: {columnas_faltantes}")
                columnas_seleccionadas = [col for col in columnas_seleccionadas if col in df_filtrado.columns]

            # Seleccionar solo las columnas especificadas
            df_resultado = df_filtrado[columnas_seleccionadas].copy()

            # Convertir NumeroDocumento y Nro Cuenta a enteros (sin decimales)
            campos_enteros = ['NumeroDocumento', 'Nro Cuenta']
            for campo in campos_enteros:
                if campo in df_resultado.columns:
                    df_resultado[campo] = df_resultado[campo].astype(str)
                    df_resultado[campo] = df_resultado[campo].replace(['nan', 'NaN', 'None', 'NaT'], '')
                    df_resultado[campo] = pd.to_numeric(df_resultado[campo], errors='coerce')
                    df_resultado[campo] = df_resultado[campo].apply(
                        lambda x: '' if pd.isna(x) else str(int(x)) if pd.notna(x) else ''
                    )

            # Limpiar números de teléfono: eliminar guiones "-"
            campos_telefono = ['NumeroTelefono', 'NumeroTrabajo', 'NumeroCelular']
            numero_hardcodeado = '3519999999'

            for campo in campos_telefono:
                if campo in df_resultado.columns:
                    serie_limpia = df_resultado[campo].apply(limpiar_numero_telefono)

                    valores_reemplazados = (serie_limpia == numero_hardcodeado).sum()
                    if valores_reemplazados > 0:
                        print(f"Valores '{numero_hardcodeado}' reemplazados por vacío en {campo}: {valores_reemplazados}")
                    serie_limpia = serie_limpia.replace(numero_hardcodeado, '')

                    if campo == 'NumeroTelefono':
                        serie_limpia = serie_limpia.apply(lambda x: aplicar_prefijo_telefono(x, '54'))
                    elif campo == 'NumeroCelular':
                        serie_limpia = serie_limpia.apply(lambda x: aplicar_prefijo_telefono(x, '549'))

                    df_resultado[campo] = serie_limpia

            # Limpiar campos de texto
            for campo in ['Estado Cuenta', 'Tasa_40', COL_TIPO_ASIGNACION, COL_GESTION_DESCRIPCION, COL_CAMPANA_REF]:
                if campo in df_resultado.columns:
                    df_resultado[campo] = df_resultado[campo].astype(str)
                    df_resultado[campo] = df_resultado[campo].replace(['nan', 'NaN', 'None', 'NaT'], '')
                    df_resultado[campo] = df_resultado[campo].apply(corregir_codificacion_texto)

            # Filtrar filas con acuerdos vigentes (antes de consolidar por Cliente_BT)
            df_resultado = filtrar_acuerdos_vigentes(df_resultado)

            # Eliminar solo Gestion_Estado (Fecha_Gestion debe quedar en salida final)
            columnas_gestion = ['Gestion_Estado']
            for col in columnas_gestion:
                if col in df_resultado.columns:
                    df_resultado = df_resultado.drop(columns=[col])

            # Guardar posición original para preservar orden en salida final
            df_resultado['_orden_original'] = range(len(df_resultado))

            if len(df_resultado) == 0:
                print(f"No quedan filas después de aplicar filtro de acuerdos vigentes en {archivo_entrada.name}")
                continue

            # Guardar el CSV con una fila por producto en la carpeta debug
            nombre_archivo_debug = f"debug_completa_{archivo_entrada.stem}.csv"
            ruta_debug = carpeta_debug / nombre_archivo_debug
            df_resultado.to_csv(ruta_debug, sep=';', index=False, encoding='utf-8')
            print(f"Archivo debug generado (una fila por producto): {ruta_debug}")
            print(f"Total de filas en el archivo debug: {len(df_resultado)}")

            # Consolidar por Cliente_BT (una fila por cliente)
            # MontoAdeudado ya fue convertido a numérico antes del filtrado

            if 'Dias_Mora' in df_resultado.columns:
                df_resultado['Dias_Mora'] = pd.to_numeric(df_resultado['Dias_Mora'], errors='coerce')

            if COL_MONTO_VENCIDO in df_resultado.columns:
                df_resultado[COL_MONTO_VENCIDO] = df_resultado[COL_MONTO_VENCIDO].astype(str).str.replace(',', '.', regex=False)
                df_resultado[COL_MONTO_VENCIDO] = pd.to_numeric(df_resultado[COL_MONTO_VENCIDO], errors='coerce')

            # Compensatorio / Punitorios: decimal europeo (T3) para sumar en la quita
            for _col_quita in (COL_COMPENSATORIO, COL_PUNITORIOS):
                if _col_quita in df_resultado.columns:
                    df_resultado[_col_quita] = df_resultado[_col_quita].astype(str).str.replace(',', '.', regex=False)
                    df_resultado[_col_quita] = pd.to_numeric(df_resultado[_col_quita], errors='coerce')

            if 'NumeroOperacion' in df_resultado.columns:
                df_resultado['NumeroOperacion'] = df_resultado['NumeroOperacion'].astype(str)
                df_resultado['NumeroOperacion'] = df_resultado['NumeroOperacion'].replace(['nan', 'NaN', 'None', 'NaT'], '')

            if 'AgrupadorProducto' in df_resultado.columns:
                df_resultado['AgrupadorProducto'] = df_resultado['AgrupadorProducto'].astype(str)
                df_resultado['AgrupadorProducto'] = df_resultado['AgrupadorProducto'].replace(['nan', 'NaN', 'None', 'NaT'], '')
                df_resultado['AgrupadorProducto'] = df_resultado['AgrupadorProducto'].apply(corregir_codificacion_texto)

            # Agrupar por CUIL y aplicar las reglas de consolidación
            def consolidar_grupo(grupo):
                resultado = grupo.iloc[0].copy()  # Tomar valores de la primera fila

                # Deuda total: SUM(MontoAdeudado) por cliente
                if 'MontoAdeudado' in grupo.columns:
                    total_monto_adeudado = grupo['MontoAdeudado'].sum(min_count=1)
                    resultado['MontoAdeudado'] = total_monto_adeudado if pd.notna(total_monto_adeudado) else 0
                elif COL_MONTO_VENCIDO in grupo.columns:
                    total_monto_vencido = grupo[COL_MONTO_VENCIDO].sum(min_count=1)
                    resultado['MontoAdeudado'] = total_monto_vencido if pd.notna(total_monto_vencido) else 0

                # Anticipo minimo es a nivel cliente, no se suma
                if 'AnticipoMinimo' in grupo.columns:
                    anticipo = grupo['AnticipoMinimo'].dropna()
                    resultado['AnticipoMinimo'] = anticipo.iloc[0] if len(anticipo) > 0 else ''

                # Oferta a nivel cliente (si/no)
                if 'OFERTA_Importe' in grupo.columns:
                    oferta_numerica = grupo['OFERTA_Importe'].apply(_parsear_decimal)
                    hay_oferta = any(valor is not None and valor > 0 for valor in oferta_numerica.tolist())
                    resultado['oferta_importe'] = 'si' if hay_oferta else 'no'
                else:
                    resultado['oferta_importe'] = 'no'

                # Maximo de dias de mora
                if 'Dias_Mora' in grupo.columns:
                    resultado['Dias_Mora'] = grupo['Dias_Mora'].max()

                # Resumen por producto/operacion
                resultado['resumen_productos'] = construir_resumen_productos(grupo)

                # Estado Cuenta y Tasa_40: valor de primera fila

                # Quita de intereses (usa el MontoAdeudado ya consolidado y el
                # Dias_Mora max ya calculados arriba; no recalcula nada)
                tipo_mercado = ''
                if COL_TIPO_MERCADO in grupo.columns:
                    tipos = grupo[COL_TIPO_MERCADO].astype(str).str.strip().str.upper()
                    tipos_validos = sorted(set(tipos[~tipos.isin(['', 'NAN', 'NONE', 'NAT'])]))
                    if len(tipos_validos) > 1:
                        print(f"[QUITA] Cliente con Tipo_Mercado mixto {tipos_validos}: no elegible")
                        tipo_mercado = '__MIXTO__'
                    elif tipos_validos:
                        tipo_mercado = tipos_validos[0]

                comp_total = grupo[COL_COMPENSATORIO].sum(min_count=1) if COL_COMPENSATORIO in grupo.columns else None
                punit_total = grupo[COL_PUNITORIOS].sum(min_count=1) if COL_PUNITORIOS in grupo.columns else None
                tiene_oferta = resultado.get('oferta_importe') == 'si'

                aplica, monto_quita = calcular_quita(
                    tipo_mercado=tipo_mercado,
                    dias_mora_max=resultado.get('Dias_Mora'),
                    comp_total=comp_total,
                    punit_total=punit_total,
                    monto_adeudado=resultado.get('MontoAdeudado'),
                    tiene_oferta=tiene_oferta,
                )
                resultado['aplica_quita'] = aplica
                resultado['monto_quita_ars'] = _formatear_decimal_fijo_2(monto_quita) if monto_quita is not None else ''
                resultado['fecha_limite_quita'] = (FECHA_LIMITE_QUITA or '') if aplica == 'si' else ''

                return resultado

            # Agrupar por Cliente_BT y consolidar preservando orden de aparición
            clave_agrupacion = 'CUIL' if 'CUIL' in df_resultado.columns else 'Cliente_BT'
            df_consolidado = df_resultado.groupby(clave_agrupacion, sort=False).apply(consolidar_grupo).reset_index(drop=True)

            # Deduplicar clientes con teléfonos compartidos
            print("\n--- Deduplicación por teléfonos ---")
            print(f"Filas antes de deduplicación: {len(df_consolidado)}")

            df_consolidado, df_descartados = deduplicar_por_telefonos(df_consolidado)

            # Asegurar orden final según aparición original de sobrevivientes
            if '_orden_original' in df_consolidado.columns:
                df_consolidado = df_consolidado.sort_values(by='_orden_original', kind='stable').reset_index(drop=True)
                df_consolidado = df_consolidado.drop(columns=['_orden_original'])

            print(f"Filas después de deduplicación: {len(df_consolidado)}")
            print(f"Clientes descartados: {len(df_descartados)}")

            if 'Dias_Mora' in df_consolidado.columns:
                df_consolidado['Dias_Mora'] = df_consolidado['Dias_Mora'].apply(
                    lambda x: str(int(x)) if pd.notna(x) else ''
                )

            if 'AnticipoMinimo' in df_consolidado.columns:
                df_consolidado['AnticipoMinimo'] = df_consolidado['AnticipoMinimo'].apply(_formatear_monto_sin_filtros)

            if 'oferta_importe' in df_consolidado.columns:
                df_consolidado['oferta_importe'] = df_consolidado['oferta_importe'].astype(str).str.strip().str.lower()
                df_consolidado['oferta_importe'] = df_consolidado['oferta_importe'].replace({'': 'no', 'true': 'si', 'false': 'no'})

            columnas_redundantes = [
                'OFERTA_Importe',
                'AgrupadorProducto',
                'NumeroOperacion',
                'ModuloCodigo',
                'MontoVencido',
                'SaldoCapital',
                'InteresAdeudado',
                'IVAInteresAdeudado',
                'Tasa_40',
                COL_TIPO_MERCADO,
                COL_COMPENSATORIO,
                COL_PUNITORIOS,
            ]
            columnas_presentes = [col for col in columnas_redundantes if col in df_consolidado.columns]
            if columnas_presentes:
                df_consolidado = df_consolidado.drop(columns=columnas_presentes)

            df_consolidado = normalizar_valores_sin_filtros(df_consolidado)
            df_consolidado = normalizar_columnas_semanticas_sin_filtros(df_consolidado)

            columnas_objetivo = [
                'id_cliente_bt',
                'id_cuil',
                'id_nro_documento',
                'customer_name',
                'tel_fijo',
                'tel_laboral',
                'tel_celular',
                'txt_mail',
                'id_nro_cuenta',
                'tipo_cuenta',
                'id_sucursal_cuenta',
                'tipo_campana_ref',
                'tipo_asignacion',
                'txt_gestion_descripcion',
                'tipo_estado_cuenta',
                'fecha_gestion',
                'monto_adeudado_ars',
                'monto_entrega_ars',
                'oferta_importe',
                'resumen_productos',
                'cnt_dias_mora_max',
                'aplica_quita',
                'monto_quita_ars',
                'fecha_limite_quita',
            ]

            renombres_post = {
                'cnt_dias_mora': 'cnt_dias_mora_max',
                'monto_anticipo_minimo_ars': 'monto_entrega_ars',
                'monto_oferta_importe_ars': 'oferta_importe',
            }
            columnas_presentes = [col for col in df_consolidado.columns if col in renombres_post]
            if columnas_presentes:
                df_consolidado = df_consolidado.rename(columns=renombres_post)

            for col in columnas_objetivo:
                if col not in df_consolidado.columns:
                    df_consolidado[col] = ''

            df_consolidado = df_consolidado[columnas_objetivo]

            df_consolidado['oferta_importe'] = (
                df_consolidado['oferta_importe']
                .astype(str)
                .str.strip()
                .str.lower()
                .replace({'true': 'si', 'false': 'no', '1': 'si', '0': 'no', '': 'no'})
            )

            # T2: aplica_quita vuelve a si/no tras la deteccion booleana del normalizador
            if 'aplica_quita' in df_consolidado.columns:
                df_consolidado['aplica_quita'] = (
                    df_consolidado['aplica_quita']
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .replace({'true': 'si', 'false': 'no', '1': 'si', '0': 'no', '': 'no'})
                )

            if 'monto_entrega_ars' in df_consolidado.columns:
                df_consolidado['monto_entrega_ars'] = df_consolidado['monto_entrega_ars'].apply(
                    lambda x: '' if pd.isna(x) else str(x)
                )

            validar_contrato_roman(df_consolidado, df_resultado)

            # Generar nombre del archivo de salida solicitado por negocio
            fecha_actual = datetime.now()
            nombre_archivo_salida = f"BANCOR_ROMAN_{fecha_actual.strftime('%Y%m%d')}.csv"
            ruta_salida = carpeta_generada / nombre_archivo_salida

            df_consolidado.to_csv(ruta_salida, sep=';', index=False, encoding='utf-8')

            print(f"Archivo consolidado generado exitosamente: {ruta_salida}")
            print(f"Total de filas en el archivo consolidado: {len(df_consolidado)}")
            print(f"Clientes únicos: {df_resultado['Cliente_BT'].nunique()}")

            # Guardar clientes descartados en carpeta backup
            if len(df_descartados) > 0:
                carpeta_backup = carpeta_generada / "backup"
                carpeta_backup.mkdir(exist_ok=True)

                backup_filename = f"descartados_completa_{fecha_actual.strftime('%d%m%Y')}.csv"
                backup_path = carpeta_backup / backup_filename

                df_descartados_output = df_descartados.copy()
                if '_orden_original' in df_descartados_output.columns:
                    df_descartados_output = df_descartados_output.drop(columns=['_orden_original'])
                df_descartados_output = normalizar_valores_sin_filtros(df_descartados_output)
                df_descartados_output = normalizar_columnas_semanticas_sin_filtros(df_descartados_output)
                if 'Dias_Mora' in df_descartados_output.columns:
                    df_descartados_output['Dias_Mora'] = df_descartados_output['Dias_Mora'].apply(
                        lambda x: str(int(float(x))) if pd.notna(x) and str(x).strip() != '' else ''
                    )

                df_descartados_output.to_csv(backup_path, sep=';', index=False, encoding='utf-8')
                print(f"\nArchivo de descartados guardado: {backup_path}")
                print(f"Total de clientes descartados: {len(df_descartados_output)}")
            else:
                print("\nNo hay clientes descartados por deduplicación")

        except Exception as e:
            print(f"Error al procesar {archivo_entrada.name}: {str(e)}")
            continue


if __name__ == "__main__":
    procesar_base()

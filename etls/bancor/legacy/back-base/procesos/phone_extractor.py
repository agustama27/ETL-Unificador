import pandas as pd
from pathlib import Path
from datetime import datetime
import re


# Reglas de longitud (Argentina, formato internacional):
# - Número nacional típico: 10 dígitos
# - Fijo internacional: 54 + número nacional -> 12 dígitos (se tolera 11-13 por legados)
# - Celular internacional: 549 + número nacional -> 13 dígitos (se tolera 12-13 por legados)
LONGITUDES_VALIDAS = {
    'fijo': (11, 13),
    'celular': (12, 13),
}

SECUENCIAS_TRIVIALES = {
    '01234567',
    '12345678',
    '23456789',
    '87654321',
    '98765432',
}


def leer_csv_con_codificacion(archivo_csv, separador=';'):
    """
    Intenta leer un CSV probando diferentes codificaciones comunes.
    Retorna el DataFrame y la codificación utilizada.
    """
    # Lista de codificaciones a probar (ordenadas por probabilidad)
    # Priorizar utf-8 y utf-8-sig primero ya que los archivos generados usan utf-8-sig
    codificaciones = ['utf-8-sig', 'utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']

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

    # Si ninguna codificación funcionó, intentar con manejo de errores
    print("Advertencia: No se pudo leer con codificaciones estándar, intentando con manejo de errores...")
    try:
        with open(archivo_csv, 'r', encoding='utf-8-sig', errors='replace') as archivo:
            df = pd.read_csv(archivo, sep=separador, low_memory=False)
        print("Archivo leído con codificación utf-8-sig y manejo de errores 'replace'")
        return df, 'utf-8-sig'
    except Exception as e:
        raise Exception(f"No se pudo leer el archivo con ninguna codificación: {str(e)}")


def _remover_prefijo_15(num):
    """Elimina el '0' de larga distancia y el '15' móvil embebido.

    Sólo remueve '15' cuando la parte nacional sin el '0' tiene longitud 12
    y al quitarlo quedan exactamente 10 dígitos (área + local).
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


def _normalizar_numero(numero, tipo):
    """
    Normaliza números de teléfono según tipo.

    Args:
        numero: Valor original del número.
        tipo: "fijo" o "celular".

    Returns:
        Número normalizado con prefijo internacional o cadena vacía.
    """
    if pd.isna(numero):
        return ''

    numero_limpio = str(numero).strip()
    if numero_limpio in ('', 'nan', 'NaN', 'None', 'NaT'):
        return ''

    numero_limpio = re.sub(r'\.0$', '', numero_limpio)
    numero_limpio = re.sub(r'\D', '', numero_limpio)
    numero_limpio = re.sub(r'^00', '', numero_limpio)

    if not numero_limpio:
        return ''

    if tipo == 'fijo':
        if numero_limpio.startswith('54'):
            return numero_limpio
        return f"54{_remover_prefijo_15(numero_limpio)}"

    if numero_limpio.startswith('549'):
        return numero_limpio
    if numero_limpio.startswith('54'):
        return f"549{_remover_prefijo_15(numero_limpio[2:])}"
    if numero_limpio.startswith('9'):
        return f"54{numero_limpio}"
    return f"549{_remover_prefijo_15(numero_limpio)}"


def _serie_unica_ordenada(serie):
    """Devuelve una serie sin vacíos, sin duplicados y ordenada."""
    serie = serie[serie != '']
    if serie.empty:
        return []
    return sorted(serie.drop_duplicates().tolist())


def _es_numero_trivial(numero, tipo):
    """Detecta patrones triviales/inválidos en la parte local del número."""
    prefijo = '549' if tipo == 'celular' else '54'
    parte_local = numero[len(prefijo):]

    if not parte_local:
        return True

    # Regla adicional útil: rechazar todos ceros o todos iguales.
    if len(set(parte_local)) == 1:
        return True

    ultimos_8 = parte_local[-8:]
    if ultimos_8 in SECUENCIAS_TRIVIALES:
        return True

    return False


def _validar_numero(numero, tipo):
    """
    Valida prefijo, dígitos, longitud y patrones triviales.

    Returns:
        Tuple (es_valido, motivos_invalidacion).
    """
    motivos = []
    prefijo_esperado = '549' if tipo == 'celular' else '54'

    if not numero:
        motivos.append('vacio')
        return False, motivos

    if not numero.isdigit():
        motivos.append('contiene_no_digitos')

    if not numero.startswith(prefijo_esperado):
        motivos.append(f'prefijo_invalido:{prefijo_esperado}')

    min_len, max_len = LONGITUDES_VALIDAS[tipo]
    if not (min_len <= len(numero) <= max_len):
        motivos.append(f'longitud_fuera_rango:{min_len}-{max_len}')

    if _es_numero_trivial(numero, tipo):
        motivos.append('patron_trivial_invalido')

    return len(motivos) == 0, motivos


def _validar_columna(serie, tipo, nombre_columna, max_ejemplos=5):
    """Valida una columna normalizada y devuelve válidos + métricas."""
    serie_con_dato = serie[serie != '']
    numeros_validos = []
    invalidos = []

    for numero in serie_con_dato:
        es_valido, motivos = _validar_numero(numero, tipo)
        if es_valido:
            numeros_validos.append(numero)
        else:
            invalidos.append((numero, ','.join(motivos)))

    metricas = {
        'columna': nombre_columna,
        'total_con_dato': int(len(serie_con_dato)),
        'validos': int(len(numeros_validos)),
        'invalidos': int(len(invalidos)),
        'ejemplos_invalidos': invalidos[:max_ejemplos],
    }

    return numeros_validos, metricas


def _imprimir_metricas_validacion(metricas):
    """Imprime métricas y ejemplos de números inválidos por columna."""
    print(f"\nValidación {metricas['columna']}:")
    print(f"  Con dato: {metricas['total_con_dato']}")
    print(f"  Válidos: {metricas['validos']}")
    print(f"  Inválidos: {metricas['invalidos']}")

    if metricas['ejemplos_invalidos']:
        print("  Ejemplos inválidos:")
        for numero, motivo in metricas['ejemplos_invalidos']:
            print(f"    - {numero}: {motivo}")


def extraer_telefonos(
    carpeta_generada=None,
    nombre_base="base_bancor",
    formato_fecha="%d%m%Y",
    prefijo_salida="telefonos_x_cliente",
    sufijo_salida="",
    columnas_salida_snake_case=False,
):
    """
    Extrae números de teléfono fijo y celular del archivo consolidado.
    Genera un CSV con ambas columnas normalizadas y sin duplicados.

    Args:
        carpeta_generada: Ruta a la carpeta donde buscar el archivo base.
                          Si es None, usa base-generada/con-filtros/
        nombre_base: Prefijo del archivo base (ej: "base_bancor" o "BANCOR_ROMAN")
        formato_fecha: Formato de fecha para buscar/generar archivos.
        prefijo_salida: Prefijo del archivo de salida de teléfonos.
        sufijo_salida: Sufijo opcional del archivo de salida de teléfonos.
        columnas_salida_snake_case: Si True, exporta headers en snake_case.
    """
    print("=" * 70)
    print("EXTRACTOR DE TELÉFONOS (FIJOS Y CELULARES ÚNICOS)")
    print("=" * 70)

    # Definir rutas
    base_dir = Path(__file__).parent.parent
    if carpeta_generada is None:
        carpeta_generada = base_dir / "base-generada" / "con-filtros"
    else:
        carpeta_generada = Path(carpeta_generada)

    # Verificar que la carpeta existe
    if not carpeta_generada.exists():
        raise FileNotFoundError(f"La carpeta '{carpeta_generada}' no existe")

    # Buscar el archivo base del día actual
    fecha_actual = datetime.now()
    nombre_archivo_base = f"{nombre_base}_{fecha_actual.strftime(formato_fecha)}.csv"
    ruta_archivo_base = carpeta_generada / nombre_archivo_base

    if not ruta_archivo_base.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo '{nombre_archivo_base}' en '{carpeta_generada}'. "
            f"Por favor, ejecute primero el procesamiento de la base."
        )

    print(f"\n--- Extracción de Teléfonos ---")
    print(f"Leyendo archivo: {nombre_archivo_base}")

    try:
        # Leer el CSV con separador de punto y coma
        df, encoding_usado = leer_csv_con_codificacion(ruta_archivo_base, separador=';')
        print(f"Total de filas leídas: {len(df)}")

    except Exception as e:
        print(f"ERROR al leer el archivo: {str(e)}")
        return None

    columna_telefono = None
    for candidata in ('NumeroTelefono', 'numero_telefono', 'tel_fijo'):
        if candidata in df.columns:
            columna_telefono = candidata
            break

    columna_celular = None
    for candidata in ('NumeroCelular', 'numero_celular', 'tel_celular'):
        if candidata in df.columns:
            columna_celular = candidata
            break

    if not columna_telefono or not columna_celular:
        print("ERROR: No se encontraron columnas de teléfonos requeridas (NumeroTelefono/numero_telefono/tel_fijo, NumeroCelular/numero_celular/tel_celular)")
        return None

    telefonos_norm = df[columna_telefono].apply(lambda x: _normalizar_numero(x, 'fijo'))
    celulares_norm = df[columna_celular].apply(lambda x: _normalizar_numero(x, 'celular'))

    total_telefonos_antes = int((telefonos_norm != '').sum())
    total_celulares_antes = int((celulares_norm != '').sum())

    telefonos_validos, metricas_tel = _validar_columna(
        telefonos_norm,
        tipo='fijo',
        nombre_columna='NumeroTelefono'
    )
    celulares_validos, metricas_cel = _validar_columna(
        celulares_norm,
        tipo='celular',
        nombre_columna='NumeroCelular'
    )

    _imprimir_metricas_validacion(metricas_tel)
    _imprimir_metricas_validacion(metricas_cel)

    telefonos_unicos = _serie_unica_ordenada(pd.Series(telefonos_validos))
    celulares_unicos = _serie_unica_ordenada(pd.Series(celulares_validos))

    # Excluir repetidos globales entre ambas columnas
    vistos = set()
    telefonos_final = []
    for numero in telefonos_unicos:
        if numero not in vistos:
            telefonos_final.append(numero)
            vistos.add(numero)

    celulares_final = []
    for numero in celulares_unicos:
        if numero not in vistos:
            celulares_final.append(numero)
            vistos.add(numero)

    print(f"Total de teléfonos fijos antes de deduplicar: {total_telefonos_antes}")
    print(f"Total de celulares antes de deduplicar: {total_celulares_antes}")
    print(f"Teléfonos fijos únicos finales: {len(telefonos_final)}")
    print(f"Celulares únicos finales: {len(celulares_final)}")
    print(f"Total números únicos finales: {len(vistos)}")

    max_filas = max(len(telefonos_final), len(celulares_final), 1)
    df_salida = pd.DataFrame({
        'NumeroTelefono': telefonos_final + [''] * (max_filas - len(telefonos_final)),
        'NumeroCelular': celulares_final + [''] * (max_filas - len(celulares_final))
    })

    # Generar nombre de archivo con fecha actual
    nombre_archivo_salida = f"{prefijo_salida}_{fecha_actual.strftime(formato_fecha)}.csv"
    if sufijo_salida:
        nombre_archivo_salida = f"{prefijo_salida}_{fecha_actual.strftime(formato_fecha)}_{sufijo_salida}.csv"
    ruta_archivo_salida = carpeta_generada / nombre_archivo_salida

    # Guardar archivo con encabezado y separador ';'
    if columnas_salida_snake_case:
        df_salida = df_salida.rename(columns={
            'NumeroTelefono': 'tel_fijo',
            'NumeroCelular': 'tel_celular'
        })

    df_salida.to_csv(
        ruta_archivo_salida,
        sep=';',
        decimal=',',
        encoding='utf-8',
        index=False,
        na_rep=''
    )

    print(f"\nArchivo generado exitosamente: {nombre_archivo_salida}")
    print(f"  Total de filas en archivo: {len(df_salida)}")

    # Mostrar primeras 5 filas como ejemplo
    if len(df_salida) > 0:
        print(f"\nPrimeras 5 filas:")
        print(df_salida.head(5).to_string(index=False))

    return ruta_archivo_salida


if __name__ == "__main__":
    try:
        ruta_archivo = extraer_telefonos()
        if ruta_archivo:
            print("\n" + "=" * 70)
            print("PROCESO COMPLETADO EXITOSAMENTE")
            print("=" * 70)
        else:
            print("\n" + "=" * 70)
            print("ADVERTENCIA: No se genero ningun archivo")
            print("=" * 70)
    except Exception as e:
        print("\n" + "=" * 70)
        print("ERROR EN EL PROCESO")
        print("=" * 70)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()

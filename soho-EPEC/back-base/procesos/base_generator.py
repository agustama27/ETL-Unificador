"""
Script para generar un CSV consolidado a partir de múltiples archivos CSV y Excel
en la carpeta base-recibida.
"""
import os
from collections import Counter
import pandas as pd
from pathlib import Path
from datetime import datetime
import unicodedata


TELEFONO_LONGITUD_MIN = 11
TELEFONO_LONGITUD_MAX = 13
TELEFONO_CELULAR_LONGITUD_MIN = 12
TELEFONO_CELULAR_LONGITUD_MAX = 13
MOJIBAKE_MARKERS = ('Ã', 'Â', 'â', 'Ð', '�')
COLUMNAS_REQUERIDAS_BASE = (
    'SUMINISTRO',
    'CONTRATO',
    'RAZON_SOCIAL',
    'BARRIO',
    'DIRECCION',
    'FECHA_EJECUCION',
    'TELEFONO',
    'TELEFONO_CELULAR',
)
COLUMNA_MOTIVO = 'MOTIVO'
COLUMNA_DESCRIPCION_COMPLETA = 'DESCRIPCION_COMPLETA'
COLUMNA_FECHA_EJECUCION = 'FECHA_EJECUCION'
COLUMNA_FECHA_EJECUTADO = 'FECHA_EJECUTADO'
COLUMNA_ORD_FECHA_FIN = 'ORD_FECHA_FIN'
BASE_EPEC_COLUMNAS_SALIDA = (
    'nombre_cliente',
    'telefono',
    'telefono_celular',
    'contrato',
    'dia_visita',
    'motivo',
    'direccion',
    'resultado_solicitud',
    'medidor',
    'dia_gestion',
    'suministro',
    'costo_instalacion',
    'gasto_movilidad',
)


def puntaje_mojibake(texto):
    """Retorna un score simple de patrones tipicos de mojibake."""
    return sum(texto.count(marker) for marker in MOJIBAKE_MARKERS)


def corregir_mojibake_utf8_latin1(valor):
    """
    Corrige mojibake tipico UTF-8 leido como Latin-1/cp1252.

    Es conservadora: solo intenta reparar cuando hay marcadores claros
    y acepta el cambio unicamente si el score de mojibake disminuye.
    """
    if pd.isna(valor):
        return valor

    if not isinstance(valor, str):
        return valor

    texto_original = valor
    if not texto_original:
        return texto_original

    score_original = puntaje_mojibake(texto_original)
    if score_original == 0:
        return texto_original

    texto_actual = texto_original
    score_actual = score_original

    # Dos pasadas maximo para cubrir casos de doble recodificacion.
    for _ in range(2):
        try:
            texto_candidato = texto_actual.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            break

        score_candidato = puntaje_mojibake(texto_candidato)
        if score_candidato >= score_actual:
            break

        texto_actual = texto_candidato
        score_actual = score_candidato

    return texto_actual if score_actual < score_original else texto_original


def normalizar_nombre_columna(columna):
    """Normaliza nombre de columna para comparaciones robustas."""
    texto = unicodedata.normalize('NFKD', str(columna))
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.upper().replace(' ', '_')


def es_columna_descripcion_o_motivo(columna):
    """Identifica columnas textuales donde puede aparecer mojibake."""
    nombre = normalizar_nombre_columna(columna)
    return 'DESCRIPCION' in nombre or 'MOTIVO' in nombre


def sanear_columnas_descripcion(df):
    """Aplica saneamiento de mojibake a columnas de descripcion/motivo."""
    columnas_objetivo = [col for col in df.columns if es_columna_descripcion_o_motivo(col)]

    for columna in columnas_objetivo:
        df[columna] = df[columna].apply(corregir_mojibake_utf8_latin1)

    return df


def quitar_15_local_argentino(cuerpo):
    """
    Quita el prefijo local "15" solo cuando coincide con patron argentino:
    <caracteristica(2-4)> + 15 + <numero(6-8)>.

    Retorna (cuerpo_normalizado, se_modifico).
    """
    if not cuerpo:
        return cuerpo, False

    # Solo evaluar cuerpos nacionales de 12 digitos.
    if len(cuerpo) != 12:
        return cuerpo, False

    for largo_caracteristica in (2, 3, 4):
        fin_caracteristica = largo_caracteristica
        if cuerpo[fin_caracteristica:fin_caracteristica + 2] != '15':
            continue

        largo_numero = len(cuerpo) - (largo_caracteristica + 2)
        if largo_numero < 6 or largo_numero > 8:
            continue

        cuerpo_sin_15 = cuerpo[:fin_caracteristica] + cuerpo[fin_caracteristica + 2:]
        if 8 <= len(cuerpo_sin_15) <= 10:
            return cuerpo_sin_15, True

    return cuerpo, False


def es_patron_trivial_invalido(digitos):
    """Detecta patrones triviales invalidos en una cadena de digitos."""
    if not digitos:
        return True

    if set(digitos) == {'0'}:
        return True

    if len(set(digitos)) == 1:
        return True

    def es_secuencia(paso):
        for i in range(1, len(digitos)):
            actual = int(digitos[i])
            previo = int(digitos[i - 1])
            if actual != (previo + paso) % 10:
                return False
        return True

    if es_secuencia(1) or es_secuencia(-1):
        return True

    for largo_bloque in (1, 2, 3, 4):
        if len(digitos) % largo_bloque != 0:
            continue
        bloque = digitos[:largo_bloque]
        if bloque * (len(digitos) // largo_bloque) == digitos:
            return True

    return False


def normalizar_numero_telefono(valor, tipo):
    """
    Normaliza un numero de telefono argentino segun el tipo de columna.

    Reglas:
    - Conserva solo digitos.
    - Evita duplicados de prefijos 54/549 al inicio.
    - TELEFONO usa prefijo 54.
    - TELEFONO_CELULAR usa prefijo 549.
    """
    if pd.isna(valor):
        return ''

    digitos = ''.join(ch for ch in str(valor) if ch.isdigit())
    if not digitos:
        return ''

    # Remover ceros de salida internacional/local al inicio
    digitos = digitos.lstrip('0')
    if not digitos:
        return ''

    # Si ya trae prefijo argentino (54 o 549), separar cuerpo
    if digitos.startswith('549'):
        cuerpo = digitos[3:]
    elif digitos.startswith('54'):
        cuerpo = digitos[2:]
    else:
        cuerpo = digitos

    # Eliminar prefijos duplicados residuales en el cuerpo
    while cuerpo.startswith('549'):
        cuerpo = cuerpo[3:]
    while cuerpo.startswith('54'):
        cuerpo = cuerpo[2:]

    # Quitar "15" local argentino cuando el patron es claro
    cuerpo, _ = quitar_15_local_argentino(cuerpo)

    if not cuerpo:
        return ''

    prefijo = '54' if tipo == 'fijo' else '549'
    return prefijo + cuerpo


def normalizar_columnas_telefono(df):
    """Aplica normalizacion de telefonos a las columnas conocidas."""
    if 'TELEFONO' in df.columns:
        df['TELEFONO'] = df['TELEFONO'].apply(lambda x: normalizar_numero_telefono(x, 'fijo'))

    if 'TELEFONO_CELULAR' in df.columns:
        df['TELEFONO_CELULAR'] = df['TELEFONO_CELULAR'].apply(lambda x: normalizar_numero_telefono(x, 'celular'))

    return df


def mapear_columnas_descripcion_a_motivo(df):
    """
    Unifica columnas textuales del input en la columna canonica MOTIVO.

    Regla:
    - Si existe DESCRIPCION_COMPLETA, se usa para completar/crear MOTIVO.
    - Si ya existe MOTIVO con contenido, se respeta.
    """
    if COLUMNA_DESCRIPCION_COMPLETA not in df.columns:
        return df

    descripcion = df[COLUMNA_DESCRIPCION_COMPLETA]

    if COLUMNA_MOTIVO not in df.columns:
        df[COLUMNA_MOTIVO] = descripcion
    else:
        motivo_vacio = df[COLUMNA_MOTIVO].isna() | (df[COLUMNA_MOTIVO].astype(str).str.strip() == '')
        df.loc[motivo_vacio, COLUMNA_MOTIVO] = descripcion[motivo_vacio]

    # Evitar duplicar semantica en la salida final.
    df = df.drop(columns=[COLUMNA_DESCRIPCION_COMPLETA])
    return df


def normalizar_columna_fecha_ejecucion(df):
    """Normaliza variantes de fecha al nombre canonico FECHA_EJECUCION."""
    aliases = [COLUMNA_FECHA_EJECUTADO, COLUMNA_ORD_FECHA_FIN]

    if COLUMNA_FECHA_EJECUCION in df.columns:
        aliases_presentes = [alias for alias in aliases if alias in df.columns]
        if aliases_presentes:
            return df.drop(columns=aliases_presentes)
        return df

    for alias in aliases:
        if alias in df.columns:
            return df.rename(columns={alias: COLUMNA_FECHA_EJECUCION})

    return df


def validar_columnas_requeridas(df, nombre_archivo):
    """Valida columnas mínimas esperadas para formatos viejo y nuevo."""
    faltantes_base = [col for col in COLUMNAS_REQUERIDAS_BASE if col not in df.columns]
    if faltantes_base:
        raise ValueError(
            f"Archivo {nombre_archivo} sin columnas requeridas: {faltantes_base}"
        )

    if COLUMNA_MOTIVO not in df.columns and COLUMNA_DESCRIPCION_COMPLETA not in df.columns:
        raise ValueError(
            f"Archivo {nombre_archivo} debe contener '{COLUMNA_MOTIVO}' o '{COLUMNA_DESCRIPCION_COMPLETA}'"
        )


def es_longitud_telefono_valida(valor, prefijo_esperado, longitud_min, longitud_max):
    """Valida digitos, prefijo, longitud y patrones triviales invalidos."""
    if pd.isna(valor):
        return False

    telefono = str(valor).strip()
    if not telefono:
        return False

    if not telefono.isdigit():
        return False

    if not telefono.startswith(prefijo_esperado):
        return False

    cuerpo = telefono[len(prefijo_esperado):]
    if es_patron_trivial_invalido(cuerpo):
        return False

    return longitud_min <= len(telefono) <= longitud_max


def limpiar_telefonos_invalidos(df):
    """Vacía los telefonos invalidos y retorna metricas de inclusion/exclusion."""
    metricas = {}

    if 'TELEFONO' in df.columns:
        telefono = df['TELEFONO'].fillna('').astype(str).str.strip()
        telefono_no_vacio = telefono != ''
        telefono_valido = df['TELEFONO'].apply(
            lambda x: es_longitud_telefono_valida(
                x,
                prefijo_esperado='54',
                longitud_min=TELEFONO_LONGITUD_MIN,
                longitud_max=TELEFONO_LONGITUD_MAX,
            )
        )

        invalidos = int((telefono_no_vacio & ~telefono_valido).sum())
        validos = int(telefono_valido.sum())
        df.loc[telefono_no_vacio & ~telefono_valido, 'TELEFONO'] = ''

        metricas['TELEFONO'] = {
            'validos': validos,
            'invalidos': invalidos,
            'prefijo': '54',
            'longitud': f'{TELEFONO_LONGITUD_MIN}-{TELEFONO_LONGITUD_MAX}',
        }

    if 'TELEFONO_CELULAR' in df.columns:
        celular = df['TELEFONO_CELULAR'].fillna('').astype(str).str.strip()
        celular_no_vacio = celular != ''
        celular_valido = df['TELEFONO_CELULAR'].apply(
            lambda x: es_longitud_telefono_valida(
                x,
                prefijo_esperado='549',
                longitud_min=TELEFONO_CELULAR_LONGITUD_MIN,
                longitud_max=TELEFONO_CELULAR_LONGITUD_MAX,
            )
        )

        invalidos = int((celular_no_vacio & ~celular_valido).sum())
        validos = int(celular_valido.sum())
        df.loc[celular_no_vacio & ~celular_valido, 'TELEFONO_CELULAR'] = ''

        metricas['TELEFONO_CELULAR'] = {
            'validos': validos,
            'invalidos': invalidos,
            'prefijo': '549',
            'longitud': f'{TELEFONO_CELULAR_LONGITUD_MIN}-{TELEFONO_CELULAR_LONGITUD_MAX}',
        }

    return df, metricas


def imprimir_resumen_validaciones(metricas):
    """Imprime resumen de inclusion/exclusion de telefonos."""
    print("\n[PHONE] Validacion de longitud de telefonos")

    if 'TELEFONO' in metricas:
        dato = metricas['TELEFONO']
        print(
            f"  TELEFONO: validos_incluidos={dato['validos']}, invalidos_excluidos={dato['invalidos']} "
            f"(prefijo={dato['prefijo']}, longitud={dato['longitud']})"
        )

    if 'TELEFONO_CELULAR' in metricas:
        dato = metricas['TELEFONO_CELULAR']
        print(
            f"  TELEFONO_CELULAR: validos_incluidos={dato['validos']}, invalidos_excluidos={dato['invalidos']} "
            f"(prefijo={dato['prefijo']}, longitud={dato['longitud']})"
        )


def separar_duplicados_por_pk_telefonos(df, carpeta_base):
    """
    Separa duplicados por PK compuesta TELEFONO;TELEFONO_CELULAR.

    Reglas:
    - Normaliza claves con fillna('') + strip
    - Si una clave aparece mas de una vez, se excluye TODO el grupo
    - Incluye clave vacia (';') bajo la misma regla
    """
    telefono_key = (
        df['TELEFONO'].fillna('').astype(str).str.strip()
        if 'TELEFONO' in df.columns
        else pd.Series('', index=df.index)
    )
    celular_key = (
        df['TELEFONO_CELULAR'].fillna('').astype(str).str.strip()
        if 'TELEFONO_CELULAR' in df.columns
        else pd.Series('', index=df.index)
    )

    claves_df = pd.DataFrame({
        '_pk_telefono': telefono_key,
        '_pk_telefono_celular': celular_key,
    })
    mascara_grupo_duplicado = claves_df.duplicated(
        subset=['_pk_telefono', '_pk_telefono_celular'],
        keep=False,
    )
    total_claves_duplicadas = int(
        claves_df.loc[mascara_grupo_duplicado, ['_pk_telefono', '_pk_telefono_celular']]
        .drop_duplicates()
        .shape[0]
    )

    total_filas = int(len(df))
    total_excluidos = int(mascara_grupo_duplicado.sum())
    df_excluidos = df[mascara_grupo_duplicado].copy()
    df_principal = df[~mascara_grupo_duplicado].copy()

    clave_vacia_mask = (claves_df['_pk_telefono'] == '') & (claves_df['_pk_telefono_celular'] == '')
    clave_vacia_total = int(clave_vacia_mask.sum())
    clave_vacia_excluidos = int((mascara_grupo_duplicado & clave_vacia_mask).sum())

    metricas = {
        'total_entrada': total_filas,
        'total_salida': int(len(df_principal)),
        'filas_excluidas_grupos_duplicados': total_excluidos,
        'claves_afectadas_grupos_duplicados': total_claves_duplicadas,
        'claves_unicas_salida': int(len(df_principal)),
        'clave_vacia_total': clave_vacia_total,
        'clave_vacia_excluidos': clave_vacia_excluidos,
    }

    ruta_debug = None
    if total_excluidos > 0:
        carpeta_debug = Path(carpeta_base) / 'base-generada' / 'debug'
        carpeta_debug.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_debug = f'duplicados_telefono_excluidos_{timestamp}.csv'
        ruta_debug = carpeta_debug / nombre_debug

        df_excluidos.to_csv(ruta_debug, sep=';', index=False, encoding='utf-8', na_rep='')

    print("\n[DEDUP] PK compuesta TELEFONO;TELEFONO_CELULAR")
    print(f"  Total entrada: {metricas['total_entrada']}")
    print(f"  Filas excluidas por grupos duplicados: {metricas['filas_excluidas_grupos_duplicados']}")
    print(f"  Claves afectadas (grupos duplicados): {metricas['claves_afectadas_grupos_duplicados']}")
    print(f"  Total salida: {metricas['total_salida']}")
    print(f"  Claves vacias detectadas (';'): {metricas['clave_vacia_total']}")
    print(f"  Claves vacias excluidas por duplicado: {metricas['clave_vacia_excluidos']}")
    if ruta_debug is not None:
        print(f"  Debug duplicados guardado en: {ruta_debug}")
    else:
        print("  No se genero archivo debug (sin duplicados)")

    return df_principal, df_excluidos, metricas, ruta_debug


def leer_archivo(archivo_path):
    """
    Lee un archivo CSV o Excel y retorna un DataFrame.
    
    Args:
        archivo_path: Ruta al archivo a leer
        
    Returns:
        DataFrame con los datos del archivo
    """
    extension = archivo_path.suffix.lower()
    
    if extension == '.csv':
        # Intentar diferentes encodings y separadores
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        separadores = [';', ',']
        
        df = None
        for encoding in encodings:
            for sep in separadores:
                try:
                    # Leer primero para ver qué columnas tiene
                    df_temp = pd.read_csv(archivo_path, sep=sep, encoding=encoding, nrows=0)
                    # Crear dtype_dict solo con las columnas que existen
                    dtype_dict = {}
                    if 'TELEFONO' in df_temp.columns:
                        dtype_dict['TELEFONO'] = str
                    if 'TELEFONO_CELULAR' in df_temp.columns:
                        dtype_dict['TELEFONO_CELULAR'] = str
                    
                    # Leer el archivo completo con dtype
                    df = pd.read_csv(archivo_path, sep=sep, encoding=encoding, dtype=dtype_dict if dtype_dict else None)
                    # Verificar que se leyó correctamente (más de una columna)
                    if len(df.columns) > 1:
                        break
                except:
                    continue
            else:
                continue
            break
        
        if df is None:
            # Si todos fallan, intentar sin especificar separador
            for encoding in encodings:
                try:
                    df_temp = pd.read_csv(archivo_path, encoding=encoding, nrows=0)
                    dtype_dict = {}
                    if 'TELEFONO' in df_temp.columns:
                        dtype_dict['TELEFONO'] = str
                    if 'TELEFONO_CELULAR' in df_temp.columns:
                        dtype_dict['TELEFONO_CELULAR'] = str
                    df = pd.read_csv(archivo_path, encoding=encoding, dtype=dtype_dict if dtype_dict else None)
                    break
                except:
                    continue
            else:
                raise ValueError(f"No se pudo leer el archivo CSV {archivo_path.name} con ningún encoding")
                
    elif extension in ['.xlsx', '.xls']:
        # Leer Excel, intentar diferentes engines
        # Primero leer solo los headers para ver qué columnas tiene
        try:
            df_temp = pd.read_excel(archivo_path, sheet_name=0, engine='openpyxl', nrows=0)
        except ImportError:
            try:
                df_temp = pd.read_excel(archivo_path, sheet_name=0, engine='xlrd', nrows=0)
            except ImportError:
                raise ImportError(
                    f"Para leer archivos Excel se necesita instalar 'openpyxl' o 'xlrd'. "
                    f"Ejecuta: pip install openpyxl"
                )
        except Exception:
            # Si falla, intentar leer normalmente
            df_temp = None
        
        # Crear dtype_dict solo con las columnas que existen
        dtype_dict = {}
        if df_temp is not None:
            if 'TELEFONO' in df_temp.columns:
                dtype_dict['TELEFONO'] = str
            if 'TELEFONO_CELULAR' in df_temp.columns:
                dtype_dict['TELEFONO_CELULAR'] = str
        
        # Leer Excel completo
        try:
            # Intentar con openpyxl primero (para .xlsx)
            df = pd.read_excel(archivo_path, sheet_name=0, engine='openpyxl', dtype=dtype_dict if dtype_dict else None)
        except ImportError:
            # Si no está instalado openpyxl, intentar con xlrd (para .xls antiguos)
            try:
                df = pd.read_excel(archivo_path, sheet_name=0, engine='xlrd', dtype=dtype_dict if dtype_dict else None)
            except ImportError:
                raise ImportError(
                    f"Para leer archivos Excel se necesita instalar 'openpyxl' o 'xlrd'. "
                    f"Ejecuta: pip install openpyxl"
                )
        except Exception as e:
            # Si openpyxl está instalado pero hay otro error
            try:
                # Intentar sin especificar engine
                df = pd.read_excel(archivo_path, sheet_name=0, dtype=dtype_dict if dtype_dict else None)
            except Exception as e2:
                raise ValueError(f"Error al leer archivo Excel {archivo_path.name}: {e2}")
    else:
        raise ValueError(f"Formato de archivo no soportado: {extension}")
    
    # Eliminar filas completamente vacías
    df = df.dropna(how='all')

    # Unificacion de variante de fecha hacia columna canonica
    df = normalizar_columna_fecha_ejecucion(df)

    validar_columnas_requeridas(df, archivo_path.name)

    # Saneamiento conservador de texto para descripcion/motivo
    df = sanear_columnas_descripcion(df)

    # Unificacion de formato nuevo -> columna canonica MOTIVO
    df = mapear_columnas_descripcion_a_motivo(df)
    
    # Normalizar columnas de teléfono
    df = normalizar_columnas_telefono(df)
    
    return df


def obtener_todos_los_archivos(carpeta_base):
    """
    Obtiene todos los archivos CSV y Excel de la carpeta base-recibida.
    
    Args:
        carpeta_base: Ruta base del proyecto
        
    Returns:
        Lista de rutas a los archivos
    """
    carpeta_recibida = Path(carpeta_base) / 'base-recibida'
    archivos = []
    
    # Buscar archivos CSV
    archivos.extend(carpeta_recibida.glob('*.csv'))
    
    # Buscar archivos Excel
    archivos.extend(carpeta_recibida.glob('*.xlsx'))
    archivos.extend(carpeta_recibida.glob('*.xls'))
    
    return archivos


def combinar_archivos(carpeta_base):
    """
    Combina todos los archivos de base-recibida en un solo DataFrame.
    
    Args:
        carpeta_base: Ruta base del proyecto
        
    Returns:
        DataFrame consolidado con todas las columnas
    """
    archivos = obtener_todos_los_archivos(carpeta_base)
    
    if not archivos:
        raise ValueError("No se encontraron archivos CSV o Excel en la carpeta base-recibida")
    
    dataframes = []
    todas_las_columnas = set()
    
    # Leer todos los archivos y recopilar todas las columnas
    print(f"Leyendo {len(archivos)} archivo(s)...")
    for archivo in archivos:
        print(f"  - Procesando: {archivo.name}")
        try:
            df = leer_archivo(archivo)
            print(f"    Filas leídas: {len(df)}")
            print(f"    Columnas: {list(df.columns)}")
            if len(df) > 0:
                dataframes.append(df)
                todas_las_columnas.update(df.columns.tolist())
            else:
                print(f"    Advertencia: {archivo.name} está vacío o no tiene datos")
        except Exception as e:
            print(f"    Error al leer {archivo.name}: {e}")
            # Si es un error de importación, dar instrucciones claras
            if "openpyxl" in str(e) or "xlrd" in str(e):
                print(f"    Instala la dependencia necesaria ejecutando: pip install openpyxl")
            import traceback
            traceback.print_exc()
            continue
    
    if not dataframes:
        raise ValueError("No se pudieron leer archivos válidos")
    
    # Ordenar las columnas: primero las columnas prioritarias, luego el resto alfabéticamente
    columnas_prioritarias = ['RAZON_SOCIAL', 'TELEFONO', 'TELEFONO_CELULAR']
    todas_las_columnas_lista = list(todas_las_columnas)
    
    # Separar columnas prioritarias del resto
    columnas_resto = [col for col in todas_las_columnas_lista if col not in columnas_prioritarias]
    columnas_resto_ordenadas = sorted(columnas_resto)
    
    # Construir el orden final: primero las prioritarias (solo las que existen), luego el resto
    columnas_prioritarias_existentes = [col for col in columnas_prioritarias if col in todas_las_columnas_lista]
    todas_las_columnas = columnas_prioritarias_existentes + columnas_resto_ordenadas
    
    # Asegurar que todos los DataFrames tengan las mismas columnas
    dataframes_normalizados = []
    for i, df in enumerate(dataframes):
        df_normalizado = df.copy()
        # Agregar columnas faltantes con valores vacíos (string vacío)
        for col in todas_las_columnas:
            if col not in df_normalizado.columns:
                df_normalizado[col] = ''
        # Reordenar columnas
        df_normalizado = df_normalizado[todas_las_columnas]
        # Convertir valores NaN a string vacío para mantener consistencia
        df_normalizado = df_normalizado.fillna('')
        
        # Normalizar números de teléfono
        df_normalizado = normalizar_columnas_telefono(df_normalizado)
        
        dataframes_normalizados.append(df_normalizado)
        print(f"  Archivo {i+1} normalizado: {len(df_normalizado)} filas")
    
    # Combinar todos los DataFrames preservando todas las filas
    df_consolidado = pd.concat(dataframes_normalizados, ignore_index=True, sort=False)
    
    # Normalizar números de teléfono una vez más después de combinar (idempotente)
    df_consolidado = normalizar_columnas_telefono(df_consolidado)

    # Excluir telefonos invalidos vaciando la celda (sin eliminar filas)
    df_consolidado, metricas_telefonos = limpiar_telefonos_invalidos(df_consolidado)
    imprimir_resumen_validaciones(metricas_telefonos)

    # Deduplicar por PK compuesta TELEFONO;TELEFONO_CELULAR
    df_consolidado, _, _, _ = separar_duplicados_por_pk_telefonos(df_consolidado, carpeta_base)
    
    # Agregar columna CONNECTION_RESULT según la lógica especificada
    def asignar_connection_result(row):
        """
        Asigna el valor de CONNECTION_RESULT según:
        - Si MEDIDOR tiene valor → "CX"
        - Si MOTIVO tiene valor → "CXI"
        - Si ni MEDIDOR ni MOTIVO tienen valor → "CXWEB"
        - Si no cumple ninguna condición → "NO IDENTIFICADO"
        """
        tiene_medidor = False
        tiene_motivo = False
        
        # Verificar si MEDIDOR tiene valor
        if 'MEDIDOR' in row.index:
            medidor = row['MEDIDOR']
            if pd.notna(medidor) and str(medidor).strip() != '':
                tiene_medidor = True
        
        # Verificar si MOTIVO tiene valor
        if 'MOTIVO' in row.index:
            motivo = row['MOTIVO']
            if pd.notna(motivo) and str(motivo).strip() != '':
                tiene_motivo = True
        
        # Aplicar la lógica
        if tiene_medidor:
            return 'CX'
        elif tiene_motivo:
            return 'CXI'
        elif not tiene_medidor and not tiene_motivo:
            return 'CXWEB'
        else:
            return 'NO IDENTIFICADO'
    
    # Aplicar la función a cada fila
    df_consolidado['CONNECTION_RESULT'] = df_consolidado.apply(asignar_connection_result, axis=1)
    
    print(f"\nArchivos combinados exitosamente.")
    print(f"Total de filas: {len(df_consolidado)}")
    print(f"Total de columnas: {len(df_consolidado.columns)}")
    
    return df_consolidado


def generar_csv_telefonos(df, carpeta_base):
    """
    Genera un CSV de salida telefonos_epec con columnas NumeroTelefono y NumeroCelular.

    Reglas aplicadas:
    - Prefijado por tipo (54 fijo, 549 celular) sin doble prefijo.
    - Solo digitos y longitudes validas.
    - Rechazo de patrones triviales invalidos.
    - Exclusion de numeros duplicados en toda la salida.
    
    Args:
        df: DataFrame consolidado con todos los datos
        carpeta_base: Ruta base del proyecto
        
    Returns:
        Ruta del archivo generado
    """
    carpeta_generada = Path(carpeta_base) / 'base-generada'
    carpeta_generada.mkdir(exist_ok=True)
    
    # Verificar que existan las columnas de teléfono
    if 'TELEFONO' not in df.columns and 'TELEFONO_CELULAR' not in df.columns:
        raise ValueError("No se encontraron columnas de teléfono en los datos")
    
    numero_telefono = df['TELEFONO'] if 'TELEFONO' in df.columns else pd.Series('', index=df.index)
    numero_celular = (
        df['TELEFONO_CELULAR'] if 'TELEFONO_CELULAR' in df.columns else pd.Series('', index=df.index)
    )
    df_telefonos = pd.DataFrame({
        'NumeroTelefono': numero_telefono,
        'NumeroCelular': numero_celular,
    }).fillna('')

    def normalizar_y_validar(valor, tipo):
        numero = normalizar_numero_telefono(valor, tipo)
        if not numero:
            return ''

        if tipo == 'fijo':
            es_valido = es_longitud_telefono_valida(
                numero,
                prefijo_esperado='54',
                longitud_min=TELEFONO_LONGITUD_MIN,
                longitud_max=TELEFONO_LONGITUD_MAX,
            )
        else:
            es_valido = es_longitud_telefono_valida(
                numero,
                prefijo_esperado='549',
                longitud_min=TELEFONO_CELULAR_LONGITUD_MIN,
                longitud_max=TELEFONO_CELULAR_LONGITUD_MAX,
            )

        return numero if es_valido else ''

    df_telefonos['NumeroTelefono'] = df_telefonos['NumeroTelefono'].apply(
        lambda x: normalizar_y_validar(x, 'fijo')
    )
    df_telefonos['NumeroCelular'] = df_telefonos['NumeroCelular'].apply(
        lambda x: normalizar_y_validar(x, 'celular')
    )

    todos_los_numeros = [
        n
        for n in pd.concat([df_telefonos['NumeroTelefono'], df_telefonos['NumeroCelular']], ignore_index=True)
        if n
    ]
    conteo_numeros = Counter(todos_los_numeros)
    duplicados = {numero for numero, total in conteo_numeros.items() if total > 1}

    if duplicados:
        duplicados_lista = list(duplicados)
        df_telefonos.loc[df_telefonos['NumeroTelefono'].isin(duplicados_lista), 'NumeroTelefono'] = ''
        df_telefonos.loc[df_telefonos['NumeroCelular'].isin(duplicados_lista), 'NumeroCelular'] = ''

    df_telefonos = df_telefonos[
        (df_telefonos['NumeroTelefono'] != '') | (df_telefonos['NumeroCelular'] != '')
    ].copy()


    # Generar nombre del archivo con fecha
    fecha_actual = datetime.now()
    fecha_formato = fecha_actual.strftime('%y%m%d')
    nombre_archivo = f'EPEC_E1KIA_{fecha_formato}.csv'
    
    # Ruta completa del archivo de salida
    archivo_salida = carpeta_generada / nombre_archivo
    
    df_telefonos.to_csv(archivo_salida, sep=';', index=False, encoding='utf-8')
    
    print(f"Archivo de teléfonos guardado en: {archivo_salida}")
    print(f"Total de filas: {len(df_telefonos)}")
    print(f"Numeros duplicados excluidos: {len(duplicados)}")
    
    return archivo_salida


def guardar_csv_consolidado(df, carpeta_base, nombre_archivo=None):
    """
    Guarda el DataFrame consolidado como CSV en la carpeta base-generada.
    
    Args:
        df: DataFrame a guardar
        carpeta_base: Ruta base del proyecto
        nombre_archivo: Nombre del archivo de salida (si es None, se genera con fecha)
    """
    carpeta_generada = Path(carpeta_base) / 'base-generada'
    
    # Crear la carpeta si no existe
    carpeta_generada.mkdir(exist_ok=True)
    
    # Generar nombre del archivo con fecha si no se proporciona
    if nombre_archivo is None:
        fecha_actual = datetime.now()
        fecha_formato = fecha_actual.strftime('%y%m%d')
        nombre_archivo = f'EPEC_ROMAN_{fecha_formato}.csv'
    
    # Ruta completa del archivo de salida
    archivo_salida = carpeta_generada / nombre_archivo
    
    def columna_o_vacia(df_fuente, nombre_columna):
        if nombre_columna in df_fuente.columns:
            return df_fuente[nombre_columna].fillna('')
        return pd.Series('', index=df_fuente.index)

    telefono = columna_o_vacia(df, 'TELEFONO').astype(str).str.strip()
    telefono_celular = columna_o_vacia(df, 'TELEFONO_CELULAR').astype(str).str.strip()

    df_salida = pd.DataFrame({
        'nombre_cliente': columna_o_vacia(df, 'RAZON_SOCIAL'),
        'telefono': telefono,
        'telefono_celular': telefono_celular,
        'contrato': columna_o_vacia(df, 'CONTRATO'),
        'dia_visita': columna_o_vacia(df, 'DIA_VISITA'),
        'motivo': columna_o_vacia(df, 'MOTIVO'),
        'direccion': columna_o_vacia(df, 'DIRECCION'),
        'resultado_solicitud': columna_o_vacia(df, 'CONNECTION_RESULT'),
        'medidor': columna_o_vacia(df, 'MEDIDOR'),
        'dia_gestion': columna_o_vacia(df, 'FECHA_EJECUCION'),
        'suministro': columna_o_vacia(df, 'SUMINISTRO'),
        'costo_instalacion': columna_o_vacia(df, 'COSTO_INSTALACION'),
        'gasto_movilidad': columna_o_vacia(df, 'GASTO_MOVILIDAD'),
    })
    df_salida = df_salida[list(BASE_EPEC_COLUMNAS_SALIDA)]

    # Guardar como CSV con separador punto y coma (como los archivos originales)
    # Usar na_rep='' para que los valores NaN se guarden como vacíos
    df_salida.to_csv(archivo_salida, sep=';', index=False, encoding='utf-8', na_rep='')
    
    print(f"\nArchivo guardado en: {archivo_salida}")
    return archivo_salida


def main():
    """
    Función principal que ejecuta el proceso completo.
    """
    # Obtener la ruta base del proyecto (directorio padre de procesos)
    carpeta_base = Path(__file__).parent.parent
    
    try:
        # Combinar todos los archivos
        df_consolidado = combinar_archivos(carpeta_base)
        
        # Guardar el CSV consolidado completo
        archivo_salida = guardar_csv_consolidado(df_consolidado, carpeta_base)
        
        # Generar CSV de teléfonos
        archivo_telefonos = generar_csv_telefonos(df_consolidado, carpeta_base)
        
        print("\n[OK] Proceso completado exitosamente")
        return archivo_salida, archivo_telefonos
        
    except Exception as e:
        print(f"\n[ERROR] Error durante el proceso: {e}")
        raise


if __name__ == "__main__":
    main()

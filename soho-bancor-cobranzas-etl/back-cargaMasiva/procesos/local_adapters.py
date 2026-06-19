"""
Adaptadores locales para reutilizar módulos de back-resultados
con las rutas de back-cargaMasiva.

Este módulo reimplementa las funciones de obtención de datos
para que busquen los archivos en las carpetas locales.
"""
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Cargar variables de entorno desde back-resultados/.env
from dotenv import load_dotenv
back_resultados_env = Path(__file__).parent.parent.parent / "back-resultados" / ".env"
load_dotenv(back_resultados_env, override=True)

# Agregar directorio de back-resultados al path
back_resultados_dir = Path(__file__).parent.parent.parent / "back-resultados" / "procesos"
sys.path.insert(0, str(back_resultados_dir))

# Importar funciones originales y utilidades
from retell_manager import (
    leer_csv_con_codificacion,
    obtener_call_ids_desde_csv,
    procesar_llamada_individual,
    MAX_WORKERS,
)
from roman_manager import (
    normalizar_datos_roman,
    validar_estructura_roman,
)
from data_merger import merge_datos_inteligente, generar_reporte_merge

from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


def _obtener_retell_api_key() -> str:
    """Obtiene la API key de Retell solo cuando se usa Retell."""
    retell_api_key = os.getenv('RETELL_API_KEY')
    if not retell_api_key:
        raise ValueError("RETELL_API_KEY no configurada. Verificar archivo .env")
    return retell_api_key


def obtener_datos_llamadas_retell_local() -> Dict[str, Dict[str, Any]]:
    """
    Obtiene datos de llamadas desde Retell.ai usando los archivos CSV
    de la carpeta local calls/ de back-cargaMasiva.

    Returns:
        Diccionario con call_id como clave y datos de la llamada como valor
    """
    retell_api_key = _obtener_retell_api_key()

    # Usar carpeta local de back-cargaMasiva
    base_dir = Path(__file__).parent.parent
    carpeta_calls = base_dir / "calls"

    print(f"  Buscando archivos en: {carpeta_calls}")

    if not carpeta_calls.exists():
        raise FileNotFoundError(f"La carpeta {carpeta_calls} no existe")

    archivos_csv = list(carpeta_calls.glob("*.csv"))

    if not archivos_csv:
        raise FileNotFoundError(f"No se encontraron archivos CSV en {carpeta_calls}")

    print(f"  Archivos encontrados: {len(archivos_csv)}")

    # Obtener todos los call IDs de todos los archivos CSV
    todos_call_ids = []
    for archivo in archivos_csv:
        print(f"    - Procesando: {archivo.name}")
        call_ids = obtener_call_ids_desde_csv(archivo)
        todos_call_ids.extend(call_ids)
        print(f"      Call IDs encontrados: {len(call_ids)}")

    # Eliminar duplicados
    call_ids_unicos = list(set(todos_call_ids))
    print(f"\n  Total de Call IDs unicos: {len(call_ids_unicos)}")

    if not call_ids_unicos:
        print("  No se encontraron Call IDs para procesar")
        return {}

    # Obtener datos de cada llamada en paralelo
    print(f"\n  Consultando API de Retell.ai ({MAX_WORKERS} workers)...")
    datos_llamadas = {}
    exitosas = 0
    parciales = 0
    errores = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(procesar_llamada_individual, call_id, retell_api_key): call_id
            for call_id in call_ids_unicos
        }

        with tqdm(total=len(call_ids_unicos), desc="  Progreso", unit="llamadas") as pbar:
            for future in as_completed(futures):
                call_id = futures[future]
                try:
                    call_id_result, resultado, estado = future.result()
                    datos_llamadas[call_id_result] = resultado
                    if estado == 'success':
                        exitosas += 1
                    elif estado == 'partial':
                        parciales += 1
                    else:
                        errores += 1
                except Exception as e:
                    errores += 1
                    datos_llamadas[call_id] = {'variables_dinamicas': {}, 'postcall': {}}
                pbar.update(1)

    print(f"\n  Llamadas procesadas: {len(datos_llamadas)}")
    print(f"  - Exitosas: {exitosas}")
    print(f"  - Parciales: {parciales}")
    if errores > 0:
        print(f"  - Errores: {errores}")

    return datos_llamadas


def obtener_df_roman_raw_local():
    """
    Carga el CSV del ROMAN base de la carpeta local base_roman/ y retorna el DataFrame crudo.

    Utilizado por logcall_manager para cruce por RECNUMBER (posición 1-indexed en la base).
    La carpeta base_roman/ contiene los archivos BANCOR_ROMAN_YYYYMMDD.csv generados por
    back-base, distintos del historial de llamadas Retell que va en roman/.

    Returns:
        DataFrame con las filas del ROMAN base, o None si no hay archivo disponible.
    """
    base_dir = Path(__file__).parent.parent
    carpeta_roman = base_dir / "base_roman"

    if not carpeta_roman.exists():
        return None

    archivos_csv = list(carpeta_roman.glob("*.csv"))
    if not archivos_csv:
        return None

    archivo_roman = max(archivos_csv, key=lambda x: x.stat().st_mtime)

    try:
        df, _ = leer_csv_con_codificacion(archivo_roman, separador=',')
    except Exception:
        try:
            df, _ = leer_csv_con_codificacion(archivo_roman, separador=';')
        except Exception:
            return None

    df.columns = df.columns.str.strip()
    return df


def obtener_datos_roman_local() -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Obtiene y normaliza datos del archivo ROMAN desde la carpeta local
    roman/ de back-cargaMasiva.

    Returns:
        Diccionario con call_id como clave y datos normalizados como valor,
        o None si no hay archivo ROMAN disponible
    """
    # Usar carpeta local de back-cargaMasiva
    base_dir = Path(__file__).parent.parent
    carpeta_roman = base_dir / "roman"

    print(f"  Buscando archivos en: {carpeta_roman}")

    if not carpeta_roman.exists():
        print(f"  La carpeta {carpeta_roman} no existe")
        return None

    archivos_csv = list(carpeta_roman.glob("*.csv"))

    if not archivos_csv:
        print(f"  No se encontraron archivos CSV en {carpeta_roman}")
        return None

    # Usar el archivo más reciente
    archivo_roman = max(archivos_csv, key=lambda x: x.stat().st_mtime)
    print(f"  Archivo ROMAN: {archivo_roman.name}")

    # Leer archivo
    try:
        df, encoding = leer_csv_con_codificacion(archivo_roman, separador=',')
    except:
        try:
            df, encoding = leer_csv_con_codificacion(archivo_roman, separador=';')
        except Exception as e:
            print(f"  Error al leer archivo ROMAN: {str(e)}")
            return None

    # Limpiar nombres de columnas
    df.columns = df.columns.str.strip()

    print(f"  Registros en archivo: {len(df)}")

    # Validar estructura
    if not validar_estructura_roman(df):
        print("  Estructura del archivo ROMAN no es valida")
        return None

    # Normalizar datos
    datos_roman = normalizar_datos_roman(df)

    print(f"  Registros normalizados: {len(datos_roman)}")

    return datos_roman

import pandas as pd
import os
import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from dotenv import load_dotenv
load_dotenv()

# Configuración de procesamiento paralelo
MAX_WORKERS = 100  # Número de workers concurrentes para consultas a la API
API_TIMEOUT = 10  # Timeout en segundos para cada request a la API

# DNS cache para evitar resolución lenta en redes corporativas
_dns_cache = {}
_original_getaddrinfo = socket.getaddrinfo

def _cached_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """
    Wrapper de getaddrinfo que cachea resoluciones DNS.
    Mejora dramáticamente el rendimiento en redes con DNS lento.
    """
    cache_key = (host, port, family, type, proto, flags)
    if cache_key not in _dns_cache:
        _dns_cache[cache_key] = _original_getaddrinfo(host, port, family, type, proto, flags)
    return _dns_cache[cache_key]

def init_dns_cache():
    """
    Inicializa el cache DNS y pre-resuelve api.retellai.com.
    """
    global _dns_cache
    # Monkey-patch getaddrinfo para usar cache
    socket.getaddrinfo = _cached_getaddrinfo
    # Pre-resolver la API de Retell
    print("  Pre-resolviendo DNS para api.retellai.com...")
    try:
        ip = socket.gethostbyname("api.retellai.com")
        print(f"  DNS resuelto: {ip}")
    except Exception as e:
        print(f"  Advertencia DNS: {e}")

# Session global con connection pooling para reutilizar conexiones TCP
_session = None
_dns_initialized = False

def get_session() -> requests.Session:
    """
    Obtiene una session singleton con connection pooling optimizado.
    Reutiliza conexiones TCP y DNS cacheado para mejor performance.
    """
    global _session, _dns_initialized
    if not _dns_initialized:
        init_dns_cache()
        _dns_initialized = True
    if _session is None:
        _session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=Retry(
                total=2,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        _session.mount('https://', adapter)
        _session.mount('http://', adapter)
    return _session

def leer_csv_con_codificacion(archivo_csv, separador=','):
    """
    Intenta leer un CSV probando diferentes codificaciones comunes.
    Retorna el DataFrame y la codificación utilizada.
    """
    # Lista de codificaciones a probar (ordenadas por probabilidad)
    codificaciones = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']
    
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
        df = pd.read_csv(archivo_csv, sep=separador, encoding='utf-8', errors='replace', low_memory=False)
        print("Archivo leído con codificación utf-8 y manejo de errores 'replace'")
        return df, 'utf-8'
    except Exception as e:
        raise Exception(f"No se pudo leer el archivo con ninguna codificación: {str(e)}")


def obtener_call_ids_desde_csv(ruta_csv: Path) -> list:
    """
    Lee un archivo CSV y extrae los valores de la columna 'Call ID' o 'ID de Llamada'.
    
    Args:
        ruta_csv: Ruta al archivo CSV
        
    Returns:
        Lista de call IDs únicos encontrados
    """
    try:
        # Intentar primero con separador de coma (estándar)
        df, encoding = leer_csv_con_codificacion(ruta_csv, separador=',')
    except:
        # Si falla, intentar con punto y coma (formato europeo)
        try:
            df, encoding = leer_csv_con_codificacion(ruta_csv, separador=';')
        except Exception as e:
            raise Exception(f"Error al leer el archivo CSV: {str(e)}")
    
    # Limpiar espacios en los nombres de columnas
    df.columns = df.columns.str.strip()
    
    # Buscar la columna con los call IDs
    call_id_column = None
    posibles_nombres = ['Call ID', 'ID de Llamada', 'call_id', 'CallID', 'callId']
    
    for nombre in posibles_nombres:
        if nombre in df.columns:
            call_id_column = nombre
            break
    
    if call_id_column is None:
        raise ValueError(
            f"No se encontró ninguna columna de Call ID. "
            f"Columnas disponibles: {', '.join(df.columns.tolist())}"
        )
    
    # Extraer los call IDs, eliminar duplicados y valores nulos
    call_ids = df[call_id_column].dropna().unique().tolist()
    call_ids = [str(cid).strip() for cid in call_ids if str(cid).strip()]
    
    print(f"Se encontraron {len(call_ids)} call IDs únicos en la columna '{call_id_column}'")
    
    return call_ids


def obtener_datos_llamada_retell(call_id: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Realiza una consulta GET a la API de Retell.ai para obtener información de una llamada.
    Usa connection pooling y DNS cacheado para mejor performance.

    Args:
        call_id: ID de la llamada en Retell.ai
        api_key: Clave de API de Retell.ai

    Returns:
        Diccionario con los datos de la llamada o None si hay error
    """
    url = f"https://api.retellai.com/v2/get-call/{call_id}"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    try:
        session = get_session()
        response = session.get(url, headers=headers, timeout=API_TIMEOUT)
        response.raise_for_status()
        datos = response.json()

        if not isinstance(datos, dict):
            return datos

        return datos
    except requests.exceptions.RequestException:
        return None


def buscar_campo_recursivo(objeto: Any, nombre_campo: str, visitados: Optional[set] = None) -> Optional[Any]:
    """
    Busca recursivamente un campo en un objeto (dict, list, etc.).
    
    Args:
        objeto: El objeto donde buscar (puede ser dict, list, etc.)
        nombre_campo: Nombre del campo a buscar
        visitados: Conjunto de IDs de objetos ya visitados (para evitar bucles infinitos)
        
    Returns:
        El valor del campo encontrado o None si no se encuentra
    """
    if visitados is None:
        visitados = set()
    
    # Evitar bucles infinitos con referencias circulares
    objeto_id = id(objeto)
    if objeto_id in visitados:
        return None
    visitados.add(objeto_id)
    
    try:
        # Si es un diccionario, buscar el campo
        if isinstance(objeto, dict):
            # Primero verificar si el campo está directamente en este nivel
            if nombre_campo in objeto:
                valor = objeto[nombre_campo]
                if valor is not None:
                    return valor
            
            # Buscar recursivamente en todos los valores del diccionario
            for valor in objeto.values():
                resultado = buscar_campo_recursivo(valor, nombre_campo, visitados)
                if resultado is not None:
                    return resultado
        
        # Si es una lista, buscar en cada elemento
        elif isinstance(objeto, list):
            for item in objeto:
                resultado = buscar_campo_recursivo(item, nombre_campo, visitados)
                if resultado is not None:
                    return resultado
        
        # Si es un objeto con atributos (pero no dict), intentar acceder como atributo
        elif hasattr(objeto, '__dict__'):
            if hasattr(objeto, nombre_campo):
                valor = getattr(objeto, nombre_campo)
                if valor is not None:
                    return valor
            # Buscar en __dict__
            resultado = buscar_campo_recursivo(objeto.__dict__, nombre_campo, visitados)
            if resultado is not None:
                return resultado
    
    except Exception:
        # Si hay algún error durante la búsqueda, continuar
        pass
    
    return None


def extraer_variables_dinamicas_y_postcall(datos_llamada: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae las variables dinámicas y postcall de la respuesta de la API de Retell.
    
    Args:
        datos_llamada: Diccionario con la respuesta completa de la API
        
    Returns:
        Diccionario con variables_dinamicas y postcall
    """
    resultado = {
        'variables_dinamicas': {},
        'postcall': {}
    }
    
    # Buscar variables dinámicas usando búsqueda recursiva
    # Prioridad: retell_llm_dynamic_variables > otros campos posibles
    campos_variables_posibles = [
        'retell_llm_dynamic_variables',
        'collected_dynamic_variables',
        'dynamic_variables',
        'variables'
    ]
    
    for campo in campos_variables_posibles:
        variables = buscar_campo_recursivo(datos_llamada, campo)
        if variables is not None:
            # Validar que sea un diccionario o convertir si es necesario
            if isinstance(variables, dict):
                resultado['variables_dinamicas'] = variables
            elif variables != {} and variables != []:
                # Si no es dict pero tiene contenido, intentar convertir o usar como está
                resultado['variables_dinamicas'] = variables if isinstance(variables, dict) else {}
            break
    
    # Buscar datos postcall usando búsqueda recursiva
    # Prioridad: custom_analysis_data > otros campos posibles
    campos_postcall_posibles = [
        'custom_analysis_data',
        'postcall',
        'post_call',
        'postcall_data',
        'post_call_data'
    ]
    
    for campo in campos_postcall_posibles:
        postcall = buscar_campo_recursivo(datos_llamada, campo)
        if postcall is not None:
            # Validar que sea un diccionario o convertir si es necesario
            if isinstance(postcall, dict):
                resultado['postcall'] = postcall
            elif postcall != {} and postcall != []:
                # Si no es dict pero tiene contenido, intentar convertir o usar como está
                resultado['postcall'] = postcall if isinstance(postcall, dict) else {}
            break
    
    return resultado


def procesar_llamada_individual(call_id: str, api_key: str) -> Tuple[str, Dict[str, Any], str]:
    """
    Procesa una llamada individual consultando la API de Retell.ai.
    Esta función está diseñada para ser ejecutada en paralelo.
    
    Args:
        call_id: ID de la llamada en Retell.ai
        api_key: Clave de API de Retell.ai
        
    Returns:
        Tupla con (call_id, resultado, estado) donde:
        - call_id: El ID de la llamada procesada
        - resultado: Diccionario con variables_dinamicas y postcall
        - estado: 'success', 'partial' o 'error'
    """
    datos_llamada = obtener_datos_llamada_retell(call_id, api_key)
    
    if datos_llamada:
        # Extraer variables dinámicas y postcall usando búsqueda recursiva
        resultado = extraer_variables_dinamicas_y_postcall(datos_llamada)
        
        # Verificar si se encontraron datos
        tiene_variables = bool(resultado['variables_dinamicas'])
        tiene_postcall = bool(resultado['postcall'])
        
        if tiene_variables or tiene_postcall:
            estado = 'success'
        else:
            estado = 'partial'
        
        return (call_id, resultado, estado)
    else:
        # Retornar entrada vacía para mantener consistencia
        return (call_id, {'variables_dinamicas': {}, 'postcall': {}}, 'error')


def obtener_datos_llamadas_retell() -> Dict[str, Dict[str, Any]]:
    """
    Función principal que ejecuta el proceso completo:
    1. Lee el CSV de la carpeta calls
    2. Identifica los Call IDs
    3. Consulta la API de Retell.ai para cada Call ID en paralelo
    4. Almacena la información en un diccionario
    
    Returns:
        Diccionario con la estructura:
        {
            'call_id_1': {
                'variables_dinamicas': {...},
                'postcall': {...}
            },
            'call_id_2': {
                'variables_dinamicas': {...},
                'postcall': {...}
            },
            ...
        }
    """
    # Obtener la ruta de la carpeta calls
    base_dir = Path(__file__).parent.parent
    carpeta_calls = base_dir / "calls"
    
    # Verificar que la carpeta existe
    if not carpeta_calls.exists():
        raise FileNotFoundError(f"La carpeta 'calls' no existe en {base_dir}")
    
    # Buscar archivos CSV en la carpeta calls
    archivos_csv = list(carpeta_calls.glob("*.csv"))
    
    if not archivos_csv:
        raise FileNotFoundError(f"No se encontraron archivos CSV en la carpeta {carpeta_calls}")
    
    # Si hay múltiples archivos, usar el primero (o se puede modificar para procesar todos)
    if len(archivos_csv) > 1:
        print(f"Advertencia: Se encontraron {len(archivos_csv)} archivos CSV. Procesando el primero: {archivos_csv[0].name}")
    archivo_csv = archivos_csv[0]
    
    print(f"Procesando archivo: {archivo_csv.name}")
    
    # Obtener los call IDs del CSV
    call_ids = obtener_call_ids_desde_csv(archivo_csv)
    
    if not call_ids:
        print("No se encontraron call IDs en el archivo CSV")
        return {}
    
    # Obtener la API key de las variables de entorno
    api_key = os.getenv('RETELL_API_KEY')
    if not api_key:
        raise ValueError(
            "No se encontró la variable de entorno RETELL_API_KEY. "
            "Por favor, configúrela antes de ejecutar el script."
        )
    
    # Diccionario para almacenar los resultados
    datos_llamadas = {}
    
    # Contadores para estadísticas
    exitosas = 0
    parciales = 0
    errores = 0
    
    # Consultar la API para cada call ID en paralelo
    total_ids = len(call_ids)
    print(f"\nConsultando API de Retell.ai para {total_ids} llamadas con {MAX_WORKERS} workers paralelos...")
    
    # Usar ThreadPoolExecutor para procesamiento paralelo
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Crear diccionario de futures mapeados a call_ids
        future_to_call_id = {
            executor.submit(procesar_llamada_individual, call_id, api_key): call_id 
            for call_id in call_ids
        }
        
        # Procesar resultados conforme se completan con barra de progreso
        with tqdm(total=total_ids, desc="Procesando llamadas", unit="llamada", 
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
            for future in as_completed(future_to_call_id):
                call_id = future_to_call_id[future]
                try:
                    # Obtener resultado del future
                    call_id_result, resultado, estado = future.result()
                    datos_llamadas[call_id_result] = resultado
                    
                    # Actualizar contadores según el estado
                    if estado == 'success':
                        exitosas += 1
                    elif estado == 'partial':
                        parciales += 1
                    else:
                        errores += 1
                        
                except Exception as e:
                    # En caso de excepción no manejada, registrar el error
                    errores += 1
                    datos_llamadas[call_id] = {
                        'variables_dinamicas': {},
                        'postcall': {}
                    }
                    tqdm.write(f"Error procesando {call_id}: {str(e)}")
                
                # Actualizar barra de progreso
                pbar.update(1)
    
    # Mostrar resumen de procesamiento
    print(f"\nProceso completado. Resumen:")
    print(f"  - Total procesadas: {len(datos_llamadas)}")
    print(f"  - Exitosas (con datos): {exitosas}")
    print(f"  - Parciales (sin variables/postcall): {parciales}")
    print(f"  - Con errores: {errores}")
    
    return datos_llamadas


if __name__ == "__main__":
    try:
        resultado = obtener_datos_llamadas_retell()
        print(f"\nTotal de llamadas procesadas: {len(resultado)}")
        print("\nEjemplo de estructura de datos:")
        if resultado:
            primer_call_id = list(resultado.keys())[0]
            print(f"Call ID: {primer_call_id}")
            print(f"Variables dinámicas: {resultado[primer_call_id]['variables_dinamicas']}")
            print(f"Postcall: {resultado[primer_call_id]['postcall']}")
    except Exception as e:
        print(f"Error: {str(e)}")


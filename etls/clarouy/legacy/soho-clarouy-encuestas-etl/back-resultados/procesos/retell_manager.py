"""
Gestor de llamadas a la API de Retell.ai para encuestas Claro Uruguay.

Maneja lectura de call_ids, llamadas paralelas (100 workers), y extracción
de variables dinámicas y datos postcall.
"""
import socket
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests
from tqdm import tqdm
import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_WORKERS = 100
TIMEOUT_SECONDS = 10

ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']

COLUMNAS_CALL_ID = ['Call ID', 'ID de Llamada', 'call_id', 'CallID', 'callId']

# ── DNS Cache Setup ───────────────────────────────────────────────────────────
_original_getaddrinfo = socket.getaddrinfo

def _cached_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = _cached_getaddrinfo

# ── Session Singleton ─────────────────────────────────────────────────────────
_session = None

def get_session() -> requests.Session:
    """Retorna una sesión singleton con connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=100,
            pool_maxsize=100,
            max_retries=2
        )
        _session.mount('https://', adapter)
        _session.mount('http://', adapter)
    return _session

# ── Functions ─────────────────────────────────────────────────────────────────

def leer_csv_con_codificacion(path: Path, separador: str = None) -> tuple[pd.DataFrame, str]:
    """Lee un CSV probando múltiples codificaciones y separadores."""
    if separador is None:
        for sep in [',', ';']:
            for encoding in ENCODINGS:
                try:
                    df = pd.read_csv(path, sep=sep, encoding=encoding, on_bad_lines='skip')
                    if len(df.columns) > 1:
                        return df, f"{encoding} (sep: {sep})"
                except (UnicodeDecodeError, Exception):
                    continue
        separador = ';'
    
    for encoding in ENCODINGS:
        try:
            df = pd.read_csv(path, sep=separador, encoding=encoding, on_bad_lines='skip')
            return df, encoding
        except (UnicodeDecodeError, Exception):
            continue
    
    df = pd.read_csv(path, sep=separador, encoding='utf-8',
                     on_bad_lines='skip', encoding_errors='replace')
    return df, 'utf-8 (errors replaced)'


def obtener_call_ids_desde_csv(carpeta_calls: Path) -> list[str]:
    """
    Extrae los call_ids desde el archivo CSV en la carpeta.
    
    Args:
        carpeta_calls: Ruta a la carpeta con CSVs
    
    Returns:
        Lista de call_ids
    """
    csvs = list(carpeta_calls.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No se encontró CSV en {carpeta_calls}")
    
    archivo = max(csvs, key=lambda p: p.stat().st_mtime)
    print(f"\n  Archivo de llamadas: {archivo.name}")
    
    df, encoding = leer_csv_con_codificacion(archivo)
    print(f"  Codificación: {encoding}")
    
    for col in COLUMNAS_CALL_ID:
        if col in df.columns:
            call_ids = df[col].dropna().astype(str).str.strip().tolist()
            call_ids = [c for c in call_ids if c]
            print(f"  Call IDs encontrados: {len(call_ids)}")
            return call_ids
    
    raise ValueError(f"No se encontró columna de call_id. Columnas: {list(df.columns)}")


def buscar_campo_recursivo(objeto, nombre_campo: str, visitados=None) -> any:
    """
    Navega dicts/lists/objetos anidados para buscar un campo.
    
    Args:
        objeto: Diccionario u objeto a buscar
        nombre_campo: Nombre del campo a encontrar
        visitados: Conjunto de ids visitados (para evitar ciclos)
    
    Returns:
        Valor del campo o None
    """
    if visitados is None:
        visitados = set()
    
    if id(objeto) in visitados:
        return None
    visitados.add(id(objeto))
    
    if isinstance(objeto, dict):
        if nombre_campo in objeto:
            return objeto[nombre_campo]
        for valor in objeto.values():
            resultado = buscar_campo_recursivo(valor, nombre_campo, visitados)
            if resultado is not None:
                return resultado
    
    elif isinstance(objeto, (list, tuple)):
        for item in objeto:
            resultado = buscar_campo_recursivo(item, nombre_campo, visitados)
            if resultado is not None:
                return resultado
    
    return None


def obtener_datos_llamada_retell(call_id: str, api_key: str) -> dict:
    """
    Obtiene los datos de una llamada desde la API de Retell.
    
    Args:
        call_id: ID de la llamada
        api_key: Clave de API de Retell
    
    Returns:
        Diccionario con los datos de la llamada
    """
    url = f"https://api.retellai.com/v2/get-call/{call_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    session = get_session()
    
    try:
        response = session.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"  Warning: Llamada {call_id} no encontrada (404)")
            return {}
        else:
            print(f"  Warning: Error {response.status_code} para {call_id}")
            return {}
            
    except requests.exceptions.Timeout:
        print(f"  Warning: Timeout para {call_id}")
        return {}
    except Exception as e:
        print(f"  Warning: Error en {call_id}: {e}")
        return {}


def extraer_variables_dinamicas_y_postcall(datos_llamada: dict) -> dict:
    """
    Extrae variables dinámicas y datos postcall de la respuesta de API.
    
    Args:
        datos_llamada: Respuesta completa de la API
    
    Returns:
        Diccionario con variables extraídas
    """
    resultado = {
        'call_id': '',
        'msisdn': '',
        'customer_id': '',
        'nombre_cliente': '',
        'campaign_id': '',
        'canal': '',
        'idioma': '',
        'max_reintentos_principal': '',
        'max_reintentos_domicilio': '',
        'skill_derivacion': '',
    }
    
    call_id = buscar_campo_recursivo(datos_llamada, 'call_id')
    if call_id:
        resultado['call_id'] = str(call_id)
    
    for campo in ['msisdn', 'customer_id', 'nombre_cliente', 'campaign_id',
                  'canal', 'idioma', 'max_reintentos_principal', 
                  'max_reintentos_domicilio', 'skill_derivacion']:
        valor = (
            buscar_campo_recursivo(datos_llamada, f'retell_llm_dynamic_variables.{campo}') or
            buscar_campo_recursivo(datos_llamada, f'collected_dynamic_variables.{campo}') or
            buscar_campo_recursivo(datos_llamada, f'dynamic_variables.{campo}')
        )
        if valor is not None:
            resultado[campo] = str(valor)
    
    postcall = (
        buscar_campo_recursivo(datos_llamada, 'custom_analysis_data') or
        buscar_campo_recursivo(datos_llamada, 'postcall') or
        buscar_campo_recursivo(datos_llamada, 'post_call')
    )
    
    if postcall and isinstance(postcall, dict):
        for key, value in postcall.items():
            resultado[key] = value
    
    return resultado


def procesar_llamada_individual(call_id: str, api_key: str) -> dict:
    """
    Procesa una llamada individual (para ejecución paralela).
    
    Args:
        call_id: ID de la llamada
        api_key: Clave de API
    
    Returns:
        Diccionario con datos de la llamada
    """
    datos = obtener_datos_llamada_retell(call_id, api_key)
    
    if not datos:
        return {'call_id': call_id, 'error': 'no_data'}
    
    return extraer_variables_dinamicas_y_postcall(datos)


def obtener_datos_llamadas_retell(call_ids: list[str], api_key: str) -> dict[str, dict]:
    """
    Obtiene datos de múltiples llamadas en paralelo.
    
    Args:
        call_ids: Lista de IDs de llamadas
        api_key: Clave de API de Retell
    
    Returns:
        Diccionario {call_id: datos}
    """
    resultados = {}
    errores = 0
    
    print(f"\n  Consultando API de Retell ({len(call_ids)} llamadas)...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(procesar_llamada_individual, call_id, api_key): call_id
            for call_id in call_ids
        }
        
        with tqdm(total=len(call_ids), desc="  Procesando", unit="llamadas") as pbar:
            for future in as_completed(futures):
                call_id = futures[future]
                try:
                    resultado = future.result()
                    resultados[call_id] = resultado
                except Exception as e:
                    print(f"  Error en {call_id}: {e}")
                    resultados[call_id] = {'call_id': call_id, 'error': str(e)}
                    errores += 1
                pbar.update(1)
    
    if errores > 0:
        print(f"  Llamadas con error: {errores}")
    
    return resultados


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    BASE_DIR = Path(__file__).parent.parent
    carpeta_calls = BASE_DIR / "calls"
    
    api_key = os.getenv('RETELL_API_KEY')
    if not api_key:
        print("ERROR: RETELL_API_KEY no configurada")
        print("Crear archivo .env con RETELL_API_KEY=...")
    else:
        print("=" * 70)
        print("TEST: Obteniendo datos de Retell")
        print("=" * 70)
        
        try:
            call_ids = obtener_call_ids_desde_csv(carpeta_calls)
            
            if call_ids:
                datos = obtener_datos_llamadas_retell(call_ids[:5], api_key)
                print(f"\n  Datos obtenidos: {len(datos)}")
            else:
                print("\n  No hay call_ids para procesar")
                
        except FileNotFoundError as e:
            print(f"\nERROR: {e}")
            print(f"Colocar archivo CSV en: {carpeta_calls}")

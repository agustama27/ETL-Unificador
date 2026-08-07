"""
Generador del CSV de tipificación de encuestas Claro Uruguay.

Genera el archivo CSV de 26 columnas con los datos de las encuestas.
"""
from pathlib import Path
from datetime import datetime
import pandas as pd

from config_encuesta import COLUMNAS_SALIDA, CAMPOS_PROTEGIDOS
from retell_manager import obtener_call_ids_desde_csv, obtener_datos_llamadas_retell
from roman_manager import obtener_datos_roman
from data_merger import merge_datos_inteligente, generar_reporte_merge

# ── Constants ──────────────────────────────────────────────────────────────────

# Campos excluidos de la respuesta de Retell (metadatos internos)
CAMPOS_EXCLUIDOS = [
    'lk-call-info', 'lk-real-ip', 'lk-transport',
    'retell_llm_dynamic_variables', 'collected_dynamic_variables', 'dynamic_variables'
]

# Prefijos a eliminar de nombres de campos
PREFIJOS_EXCLUIDOS = ['var_', 'postcall_']

# ── Functions ─────────────────────────────────────────────────────────────────

def aplanar_diccionario(datos: dict, prefijo: str = '') -> dict:
    """
    Aplana un diccionario anidado en uno plano con claves compuestas.
    
    Args:
        datos: Diccionario a aplanar
        prefijo: Prefijo para las claves
    
    Returns:
        Diccionario plano
    """
    resultado = {}
    
    for clave, valor in datos.items():
        if not clave or any(clave.startswith(p) for p in PREFIJOS_EXCLUIDOS):
            continue
        
        if any(clave.startswith(e) for e in CAMPOS_EXCLUIDOS):
            continue
        
        nueva_clave = f"{prefijo}{clave}" if prefijo else clave
        
        if isinstance(valor, dict):
            resultado.update(aplanar_diccionario(valor, f"{nueva_clave}."))
        elif isinstance(valor, list):
            resultado[nueva_clave] = ','.join(str(v) for v in valor) if valor else ''
        else:
            resultado[nueva_clave] = valor
    
    return resultado


def generar_dataframe_tipificacion(datos_retell: dict[str, dict]) -> pd.DataFrame:
    """
    Genera el DataFrame de tipificación desde los datos de Retell.
    
    Args:
        datos_retell: Diccionario {call_id: datos}
    
    Returns:
        DataFrame con las columnas de salida
    """
    registros = []
    
    for call_id, datos in datos_retell.items():
        aplanado = aplanar_diccionario(datos)
        aplanado['call_id'] = call_id
        registros.append(aplanado)
    
    if not registros:
        return pd.DataFrame(columns=COLUMNAS_SALIDA)
    
    df = pd.DataFrame(registros)
    
    for col in COLUMNAS_SALIDA:
        if col not in df.columns:
            df[col] = ''
    
    df = df[COLUMNAS_SALIDA]
    
    return df


def generar_csv_encuestas(usar_roman: bool = True) -> Path | None:
    """
    Genera el CSV de encuestas procesando datos de Retell y opcionalmente ROMAN.
    
    Args:
        usar_roman: Si True, merge con datos de ROMAN
    
    Returns:
        Ruta al archivo generado o None
    """
    BASE_DIR = Path(__file__).parent.parent
    
    carpeta_calls = BASE_DIR / "calls"
    carpeta_results = BASE_DIR / "results"
    carpeta_roman = BASE_DIR / "roman"
    
    carpeta_results.mkdir(parents=True, exist_ok=True)
    
    from dotenv import load_dotenv
    import os
    load_dotenv()
    
    api_key = os.getenv('RETELL_API_KEY')
    if not api_key:
        raise ValueError("RETELL_API_KEY no configurada. Verificar archivo .env")
    
    print("\n--- Paso 1: Leer call_ids ---")
    call_ids = obtener_call_ids_desde_csv(carpeta_calls)
    
    if not call_ids:
        print("  No hay call_ids para procesar")
        return None
    
    print("\n--- Paso 2: Consultar API de Retell ---")
    datos_retell = obtener_datos_llamadas_retell(call_ids, api_key)
    
    print("\n--- Paso 3: Generar DataFrame de tipificación ---")
    df_tipificacion = generar_dataframe_tipificacion(datos_retell)
    print(f"  Registros generados: {len(df_tipificacion)}")
    
    df_roman = None
    if usar_roman:
        print("\n--- Paso 4: Merge con datos ROMAN ---")
        df_roman = obtener_datos_roman(carpeta_roman)
        
        if df_roman is not None and not df_roman.empty:
            df_tipificacion, stats = merge_datos_inteligente(df_tipificacion, df_roman)
            print(generar_reporte_merge(stats))
        else:
            print("  No se pudieron obtener datos de ROMAN, usando solo Retell")
    
    print("\n--- Paso 5: Guardar CSV de resultados ---")
    fecha = datetime.today().strftime('%d%m%Y')
    output_path = carpeta_results / f"encuestas_clarouy_{fecha}.csv"
    
    df_tipificacion.to_csv(
        output_path,
        sep=';',
        decimal=',',
        encoding='utf-8',
        index=False,
        na_rep=''
    )
    
    print(f"  Archivo generado: {output_path.name}")
    print(f"  Total registros: {len(df_tipificacion)}")
    print(f"  Columnas: {len(df_tipificacion.columns)}")
    
    return output_path


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("TEST: Generar CSV de encuestas")
    print("=" * 70)
    
    try:
        ruta = generar_csv_encuestas(usar_roman=True)
        
        if ruta:
            print(f"\nOK: CSV generado en {ruta}")
        else:
            print("\nADVERTENCIA: No se generó ningún archivo")
            
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
    except ValueError as e:
        print(f"\nERROR: {e}")

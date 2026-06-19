"""
Módulo de generación de base de clientes Claro Uruguay.

Input: CSV de clientes desde base-recibida/
Output: Base consolidada (un registro por cliente) + teléfonos únicos
"""
from pathlib import Path
from datetime import datetime
import pandas as pd
import re

# ── Constants ──────────────────────────────────────────────────────────────────
ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']

COLUMNAS_SALIDA = [
    'msisdn', 'customer_id', 'nombre_cliente', 'campaign_id',
    'canal', 'idioma', 'max_reintentos_principal',
    'max_reintentos_domicilio', 'skill_derivación'
]

# ── Functions ─────────────────────────────────────────────────────────────────

def leer_csv_con_codificacion(path: Path, separador: str = None) -> tuple[pd.DataFrame, str]:
    """
    Lee un CSV probando múltiples codificaciones y separadores.
    
    Args:
        path: Ruta al archivo CSV
        separador: Separador a usar (None para autodetectar)
    
    Returns:
        Tupla (DataFrame, cadena de codificación usada)
    """
    if separador is None:
        for sep in [',', ';']:
            for encoding in ENCODINGS:
                try:
                    df = pd.read_csv(path, sep=sep, encoding=encoding, dtype=str, on_bad_lines='skip')
                    if len(df.columns) > 1:
                        return df, f"{encoding} (sep: {sep})"
                except (UnicodeDecodeError, Exception):
                    continue
        separador = ';'
    else:
        separador = separador
    
    for encoding in ENCODINGS:
        try:
            df = pd.read_csv(path, sep=separador, encoding=encoding, dtype=str, on_bad_lines='skip')
            return df, encoding
        except (UnicodeDecodeError, Exception):
            continue
    
    df = pd.read_csv(path, sep=separador, encoding='utf-8', 
                     dtype=str, on_bad_lines='skip', encoding_errors='replace')
    return df, 'utf-8 (errors replaced)'


def buscar_csv_en_carpeta(carpeta: Path) -> Path | None:
    """
    Busca el archivo CSV más reciente en una carpeta.
    
    Args:
        carpeta: Ruta a la carpeta de búsqueda
    
    Returns:
        Ruta al archivo CSV encontrado o None
    """
    csvs = list(carpeta.glob("*.csv"))
    if not csvs:
        return None
    return max(csvs, key=lambda p: p.stat().st_mtime)


def limpiar_msisdn(valor) -> str:
    """
    Limpia y formatea un número de teléfono MSISDN.
    Formatos aceptados:
    - Uruguay: 5989XXXXXXXX (12 dígitos, código país 598)
    - Argentina: 549XXXXXXXXXX (13 dígitos, código país 54)

    Args:
        valor: Valor del campo teléfono

    Returns:
        MSISDN limpio o cadena vacía
    """
    if pd.isna(valor) or valor is None:
        return ''

    valor_str = str(valor).strip()
    numeros = re.sub(r'\D', '', valor_str)

    # Uruguay: 9 dígitos locales → agregar 598
    if len(numeros) == 9 and not numeros.startswith('54'):
        return f'598{numeros}'
    # Uruguay: 09XXXXXXXX → agregar 598
    elif len(numeros) == 10 and numeros.startswith('9'):
        return f'598{numeros}'
    # Uruguay: 5989XXXXXXXX completo
    elif len(numeros) == 12 and numeros.startswith('598'):
        return numeros
    # Uruguay: 8 dígitos → agregar 5989
    elif len(numeros) == 8:
        return f'5989{numeros}'
    # Argentina: 549XXXXXXXXXX completo (13 dígitos)
    elif len(numeros) == 13 and numeros.startswith('549'):
        return numeros
    # Argentina: 9XXXXXXXXXX (11 dígitos sin código país) → agregar 54
    elif len(numeros) == 11 and numeros.startswith('9'):
        return f'54{numeros}'
    # Argentina: 10 dígitos sin 9 móvil → agregar 549
    elif len(numeros) == 10 and not numeros.startswith('9'):
        return f'549{numeros}'

    return ''


def generar_customer_id(numero: int) -> str:
    """
    Genera un customer_id en formato CLAROUY-XXXXXXX.
    
    Args:
        numero: Número secuencial
    
    Returns:
        ID de cliente formateado
    """
    return f"CLAROUY-{numero:07d}"


def procesar_base(carpeta_entrada: Path, carpeta_salida: Path) -> pd.DataFrame:
    """
    Procesa la base de clientes: limpia, consolida y deduplica.
    
    Args:
        carpeta_entrada: Carpeta con CSV de entrada
        carpeta_salida: Carpeta para CSV de salida
    
    Returns:
        DataFrame con la base procesada
    """
    archivo_csv = buscar_csv_en_carpeta(carpeta_entrada)
    if not archivo_csv:
        raise FileNotFoundError(f"No se encontró CSV en {carpeta_entrada}")
    
    print(f"\n  Archivo encontrado: {archivo_csv.name}")
    
    df, encoding_usada = leer_csv_con_codificacion(archivo_csv)
    print(f"  Codificación detectada: {encoding_usada}")
    print(f"  Filas originales: {len(df)}")
    print(f"  Columnas: {list(df.columns)[:10]}...")
    
    df = df.rename(columns=str.lower)

    if 'customer_id' not in df.columns:
        print("\n  Generando customer_id secuencial...")
        df['customer_id'] = [generar_customer_id(i + 1) for i in range(len(df))]

    for col in ['msisdn', 'telefono', 'phone', 'numero', 'numero_telefono']:
        if col in df.columns:
            print(f"\n  Limpiando columna de teléfono: {col}")
            df['msisdn'] = df[col].apply(limpiar_msisdn)
            break
    else:
        df['msisdn'] = ''

    for col in ['nombre_cliente', 'nombre', 'cliente', 'name']:
        if col in df.columns:
            df['nombre_cliente'] = df[col].fillna('').astype(str)
            break
    else:
        df['nombre_cliente'] = ''

    for col in ['campaign_id', 'campaña', 'campana']:
        if col in df.columns:
            df['campaign_id'] = df[col].fillna('').astype(str)
            break
    else:
        df['campaign_id'] = ''

    for col in ['canal', 'channel']:
        if col in df.columns:
            df['canal'] = df[col].fillna('').astype(str).str.upper()
            break
    else:
        df['canal'] = 'VOICE'

    for col in ['idioma', 'locale', 'language']:
        if col in df.columns:
            df['idioma'] = df[col].fillna('es-UY').astype(str)
            break
    else:
        df['idioma'] = 'es-UY'

    for col in ['max_reintentos_principal']:
        if col in df.columns:
            df['max_reintentos_principal'] = df[col].fillna('3').astype(str)
            break
    else:
        df['max_reintentos_principal'] = '3'

    for col in ['max_reintentos_domicilio']:
        if col in df.columns:
            df['max_reintentos_domicilio'] = df[col].fillna('2').astype(str)
            break
    else:
        df['max_reintentos_domicilio'] = '2'

    for col in ['skill_derivación', 'skill_derivacion', 'skill']:
        if col in df.columns:
            df['skill_derivación'] = df[col].fillna('').astype(str)
            break
    else:
        df['skill_derivación'] = ''
    
    columnas_disponibles = [c for c in COLUMNAS_SALIDA if c in df.columns]
    df_salida = df[columnas_disponibles].copy()
    
    print(f"\n  Clientes con MSISDN válido: {(df_salida['msisdn'] != '').sum()}")
    
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    
    fecha = datetime.today().strftime('%d%m%Y')
    output_path = carpeta_salida / f"base_clarouy_{fecha}.csv"
    
    df_salida.to_csv(
        output_path,
        sep=';',
        decimal=',',
        encoding='utf-8',
        index=False,
        na_rep=''
    )
    
    print(f"\n  Archivo generado: {output_path.name}")
    print(f"  Total registros: {len(df_salida)}")
    
    return df_salida


def deduplicar_por_telefonos(df: pd.DataFrame, carpeta_backup: Path) -> pd.DataFrame:
    """
    Deduplica clientes que comparten el mismo número de teléfono.
    Mantiene el primero (puede ordenarse por monto antes).
    
    Args:
        df: DataFrame con columna msisdn
        carpeta_backup: Carpeta para guardar descartados
    
    Returns:
        DataFrame deduplicado
    """
    df = df.copy()
    df['msisdn_limpio'] = df['msisdn'].apply(
        lambda x: x if x and len(x) >= 12 else ''
    )
    
    telefonos_validos = df[df['msisdn_limpio'] != '']
    duplicados = telefonos_validos[telefonos_validos.duplicated(subset=['msisdn_limpio'], keep=False)]
    
    if len(duplicados) > 0:
        print(f"  Teléfonos compartidos encontrados: {duplicados['msisdn_limpio'].nunique()}")
        
        carpeta_backup.mkdir(parents=True, exist_ok=True)
        fecha = datetime.today().strftime('%d%m%Y')
        backup_path = carpeta_backup / f"descartados_por_telefono_{fecha}.csv"
        duplicados.to_csv(
            backup_path,
            sep=';',
            decimal=',',
            encoding='utf-8',
            index=False,
            na_rep=''
        )
        print(f"  Descartados guardados en: {backup_path.name}")
    
    df_dedup = df.drop_duplicates(subset=['msisdn_limpio'], keep='first')
    df_dedup = df_dedup.drop(columns=['msisdn_limpio'])
    
    return df_dedup


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    BASE_DIR = Path(__file__).parent.parent
    carpeta_entrada = BASE_DIR / "back-base" / "base-recibida"
    carpeta_salida = BASE_DIR / "back-base" / "base-generada" / "con-filtros"
    carpeta_backup = carpeta_salida / "backup"
    
    print("=" * 70)
    print("PROCESAMIENTO DE BASE DE CLIENTES CLARO URUGUAY")
    print("=" * 70)
    
    try:
        df_resultado = procesar_base(carpeta_entrada, carpeta_salida)
        
        print("\n" + "=" * 70)
        print("PROCESO COMPLETADO")
        print("=" * 70)
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        print("\nAsegúrese de colocar el archivo CSV en:")
        print(f"  {carpeta_entrada}")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

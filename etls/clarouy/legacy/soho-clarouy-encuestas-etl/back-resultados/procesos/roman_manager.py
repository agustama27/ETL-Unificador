"""
Gestor de datos ROMAN para encuestas Claro Uruguay.

Maneja la lectura y normalización de datos de gestión humana desde ROMAN.
"""
from pathlib import Path
import pandas as pd

from config_encuesta import (
    MAPEO_COLUMNAS_ROMAN,
    COLUMNAS_CALL_ID,
    VALORES_VACIOS,
    normalizar_booleano
)

# ── Constants ──────────────────────────────────────────────────────────────────
ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']

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


def obtener_archivo_roman(carpeta_roman: Path) -> Path | None:
    """
    Busca el archivo CSV de ROMAN más reciente.
    
    Args:
        carpeta_roman: Ruta a la carpeta con datos ROMAN
    
    Returns:
        Ruta al archivo o None
    """
    csvs = list(carpeta_roman.glob("*.csv"))
    if not csvs:
        return None
    return max(csvs, key=lambda p: p.stat().st_mtime)


def validar_estructura_roman(df: pd.DataFrame) -> bool:
    """
    Valida que el DataFrame de ROMAN tenga las columnas requeridas.
    
    Args:
        df: DataFrame de ROMAN
    
    Returns:
        True si es válido
    """
    tiene_call_id = any(col in df.columns for col in COLUMNAS_CALL_ID)
    return tiene_call_id


def normalizar_datos_roman(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza los nombres de columnas del DataFrame ROMAN.
    
    Args:
        df: DataFrame de ROMAN
    
    Returns:
        DataFrame con columnas normalizadas
    """
    df = df.copy()
    
    columna_call_id = None
    for col in COLUMNAS_CALL_ID:
        if col in df.columns:
            columna_call_id = col
            break
    
    if columna_call_id and columna_call_id != 'call_id':
        df = df.rename(columns={columna_call_id: 'call_id'})
    
    for col_original, col_nuevo in MAPEO_COLUMNAS_ROMAN.items():
        if col_original in df.columns and col_original != col_nuevo:
            df = df.rename(columns={col_original: col_nuevo})
    
    return df


def filtrar_roman_valido(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra registros de ROMAN que tienen call_id válido.
    
    Args:
        df: DataFrame de ROMAN
    
    Returns:
        DataFrame filtrado
    """
    if 'call_id' not in df.columns:
        return df.head(0)
    
    df = df.copy()
    df['call_id'] = df['call_id'].astype(str).str.strip()
    df = df[df['call_id'].notna()]
    df = df[df['call_id'] != '']
    df = df[df['call_id'] != 'nan']
    
    return df


def obtener_datos_roman(carpeta_roman: Path) -> pd.DataFrame:
    """
    Obtiene y normaliza los datos de ROMAN.
    
    Args:
        carpeta_roman: Ruta a la carpeta con CSVs de ROMAN
    
    Returns:
        DataFrame con datos de ROMAN normalizados
    """
    archivo = obtener_archivo_roman(carpeta_roman)
    
    if not archivo:
        print("  No se encontró archivo de ROMAN")
        return pd.DataFrame()
    
    print(f"  Archivo ROMAN: {archivo.name}")
    
    df, encoding = leer_csv_con_codificacion(archivo)
    print(f"  Codificación: {encoding}")
    print(f"  Registros: {len(df)}")
    
    if not validar_estructura_roman(df):
        print("  ADVERTENCIA: Archivo ROMAN no tiene columna de call_id")
        return pd.DataFrame()
    
    df = normalizar_datos_roman(df)
    df = filtrar_roman_valido(df)
    
    print(f"  Registros válidos: {len(df)}")
    
    return df


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from pathlib import Path
    
    BASE_DIR = Path(__file__).parent.parent
    carpeta_roman = BASE_DIR / "roman"
    
    print("=" * 70)
    print("TEST: Leer datos de ROMAN")
    print("=" * 70)
    
    df = obtener_datos_roman(carpeta_roman)
    
    if not df.empty:
        print(f"\nColumnas: {list(df.columns)}")
    else:
        print("\nNo se encontraron datos de ROMAN")

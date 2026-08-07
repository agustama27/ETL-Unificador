"""
Módulo para manejo de archivos CSV
Lectura y escritura de CSVs con manejo de encoding y errores
"""

import pandas as pd
from pathlib import Path
from typing import Optional
import logging


logger = logging.getLogger(__name__)


def get_latest_file(folder: Path, pattern: str = "*.csv") -> Path:
    """
    Obtener el único archivo que coincida con el patrón en la carpeta

    Args:
        folder: Carpeta donde buscar
        pattern: Patrón de archivo (default: *.csv)

    Returns:
        Path: Path al archivo encontrado

    Raises:
        FileNotFoundError: Si no hay archivos en la carpeta
        ValueError: Si hay múltiples archivos (se espera solo uno)
    """
    files = list(folder.glob(pattern))

    if len(files) == 0:
        raise FileNotFoundError(
            f"No se encontró ningún archivo con patrón '{pattern}' en {folder}"
        )

    if len(files) > 1:
        raise ValueError(
            f"Se encontraron {len(files)} archivos en {folder}. "
            f"Se espera un solo archivo. Archivos encontrados: {[f.name for f in files]}"
        )

    logger.info(f"Archivo encontrado: {files[0].name}")
    return files[0]


def read_retell_csv(file_path: Path) -> pd.DataFrame:
    """
    Leer CSV de Retell con encoding UTF-8

    Args:
        file_path: Path al archivo CSV de Retell

    Returns:
        pd.DataFrame: DataFrame con datos de Retell

    Raises:
        FileNotFoundError: Si el archivo no existe
        ValueError: Si faltan columnas requeridas
    """
    logger.info(f"Leyendo export de Retell: {file_path.name}")

    if not file_path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    # Leer CSV con encoding UTF-8
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        # Fallback a Latin-1 si UTF-8 falla
        logger.warning("UTF-8 falló, intentando con Latin-1")
        df = pd.read_csv(file_path, encoding='latin-1')

    # Validar columnas requeridas
    required_columns = ['Call ID', 'Time']
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Columnas faltantes en CSV de Retell: {missing_columns}. "
            f"Columnas presentes: {list(df.columns)}"
        )

    # Parsear columna Time como datetime (formato: MM/DD/YYYY HH:MM)
    try:
        df['Time'] = pd.to_datetime(df['Time'], format='%m/%d/%Y %H:%M')
    except Exception as e:
        logger.warning(f"No se pudo parsear columna Time como datetime: {e}")

    logger.info(f"Cargados {len(df)} registros de Retell")
    return df


def read_roman_csv(file_path: Path) -> Optional[pd.DataFrame]:
    """
    Leer CSV de Roman (retorna None si no existe)

    Args:
        file_path: Path al archivo CSV de Roman

    Returns:
        Optional[pd.DataFrame]: DataFrame con datos de Roman o None si no existe
    """
    if not file_path.exists():
        logger.info("No se encontró archivo de correcciones Roman")
        return None

    logger.info(f"Leyendo correcciones Roman: {file_path.name}")

    # Leer CSV con encoding UTF-8
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
    except UnicodeDecodeError:
        logger.warning("UTF-8 falló, intentando con Latin-1")
        df = pd.read_csv(file_path, encoding='latin-1')

    # Validar que tenga la columna ID de Llamada
    if 'ID de Llamada' not in df.columns:
        logger.warning(
            f"CSV de Roman no tiene columna 'ID de Llamada'. "
            f"Columnas: {list(df.columns)}"
        )
        return None

    # Parsear columnas de fecha (formato: DD/MM/YYYY)
    date_columns = ['Fecha y Hora']
    for col in date_columns:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], format='%d/%m/%Y, %H:%M')
            except Exception as e:
                logger.warning(f"No se pudo parsear columna {col}: {e}")

    logger.info(f"Cargados {len(df)} registros de Roman")
    return df


def write_enriched_csv(df: pd.DataFrame, output_path: Path) -> None:
    """
    Escribir CSV enriquecido con UTF-8 BOM para Excel

    Args:
        df: DataFrame a escribir
        output_path: Path donde escribir el CSV
    """
    logger.info(f"Escribiendo CSV enriquecido: {output_path.name}")

    # Crear carpeta si no existe
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Escribir con UTF-8 BOM para compatibilidad con Excel
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    logger.info(f"CSV enriquecido escrito: {output_path} ({len(df)} registros)")


def write_tipification_report(df: pd.DataFrame, output_path: Path, columns: list = None) -> None:
    """
    Escribir reporte de tipificación con columnas específicas

    Args:
        df: DataFrame a escribir
        output_path: Path donde escribir el CSV
        columns: Lista de columnas a incluir (opcional, usa todas si None)
    """
    logger.info(f"Escribiendo reporte de tipificación: {output_path.name}")

    # Crear carpeta si no existe
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Filtrar columnas si se especificaron
    if columns:
        # Obtener solo las columnas que existen en el DataFrame
        available_columns = [col for col in columns if col in df.columns]
        missing_columns = [col for col in columns if col not in df.columns]

        if missing_columns:
            logger.warning(f"Columnas faltantes en reporte: {missing_columns}")

        df_to_write = df[available_columns]
    else:
        df_to_write = df

    # Escribir con UTF-8 BOM para compatibilidad con Excel
    df_to_write.to_csv(output_path, index=False, encoding='utf-8-sig')

    logger.info(
        f"Reporte de tipificación escrito: {output_path} "
        f"({len(df_to_write)} registros, {len(df_to_write.columns)} columnas)"
    )


def get_roman_file_if_exists(folder: Path) -> Optional[Path]:
    """
    Obtener archivo de Roman si existe (sin lanzar error si no existe)

    Args:
        folder: Carpeta donde buscar

    Returns:
        Optional[Path]: Path al archivo Roman o None si no existe
    """
    try:
        return get_latest_file(folder, "*.csv")
    except FileNotFoundError:
        logger.info("No hay archivo de correcciones Roman")
        return None
    except ValueError as e:
        logger.warning(f"Error al buscar archivo Roman: {e}")
        return None

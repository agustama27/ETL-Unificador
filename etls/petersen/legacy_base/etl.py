"""
ETL for Petersen banks.

Processes INTEGRACION.csv (client data) and PRODCLI_DEELO.csv (product data).
"""
import argparse
import os
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import sys
import numpy as np

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from adapters.petersen.simple_ingest import load_all_banks
from procesos.simple_merge import merge_integration_and_products
from lib.common.logging_config import setup_logging
from lib.common.validations import (
    validate_sucursal_column,
    validate_numero_operacion,
    extract_all_phones,
    dedupe_phone_columns
)
from procesos.mail_merge import enrich_with_email
import logging

DEFAULT_MAX_CLIENTS = 10000
logger = logging.getLogger('petersen_etl')


def format_time(seconds):
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.2f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.2f}s"


def _phone_to_petersen_txt(phone) -> str:
    """
    Normaliza un teléfono para el archivo `telefonos_petersen.txt`:
    - 1 teléfono por línea
    - siempre con prefijo `+549`
    """
    if phone is None:
        return ""
    phone_str = str(phone).strip()
    if not phone_str:
        return ""

    if not phone_str.startswith('+549'):
        if phone_str.startswith('+54'):
            # Si ya tiene +54 pero no +549, reemplazar
            phone_str = '+549' + phone_str[3:]
        elif phone_str.startswith('549'):
            # Si tiene 549 sin el +, agregar +
            phone_str = '+' + phone_str
        elif phone_str.startswith('54'):
            # Si tiene 54 sin el 9, agregar +9
            phone_str = '+549' + phone_str[2:]
        else:
            # Si no tiene prefijo, agregar +549
            phone_str = '+549' + phone_str
    return phone_str


def write_phones_txt(all_phones_df: pd.DataFrame, out_path: Path, encoding: str = "utf-8-sig") -> None:
    """
    Escribe el listado simple de teléfonos (un teléfono por línea) con encoding controlado.

    Importante: usamos `utf-8-sig` (UTF-8 con BOM) por compatibilidad con Excel/Windows,
    consistente con los CSVs que genera este ETL.
    """
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        if all_phones_df is None or all_phones_df.empty or 'Telefono' not in all_phones_df.columns:
            # Crear el archivo vacío igualmente para que el pipeline sea consistente
            logger.warning(f"No hay teléfonos para escribir en {out_path.name}, creando archivo vacío")
            with open(out_path, 'w', encoding=encoding, newline='\n') as f:
                f.write("")
            return

        phone_count = 0
        with open(out_path, 'w', encoding=encoding, newline='\n') as f:
            for phone in all_phones_df['Telefono']:
                normalized = _phone_to_petersen_txt(phone)
                if normalized:
                    f.write(f"{normalized}\n")
                    phone_count += 1
        
        logger.debug(f"Archivo {out_path.name} escrito exitosamente con {phone_count} teléfonos (encoding: {encoding})")
        
    except Exception as e:
        logger.error(f"Error al escribir {out_path.name}: {e}", exc_info=True)
        raise


def extract_tel1_phones(df: pd.DataFrame) -> list:
    """
    Extrae solo los teléfonos de la columna TEL1 del DataFrame.
    
    Args:
        df: DataFrame con datos consolidados que debe tener columna TEL1
    
    Returns:
        Lista de teléfonos únicos de TEL1 (ya normalizados con prefijo +549)
    """
    if df.empty or 'TEL1' not in df.columns:
        return []
    
    from lib.common.phone_normalize import normalize_phone_string
    
    tel1_phones = []
    seen = set()
    
    for phone in df['TEL1']:
        phone_str = normalize_phone_string(phone)
        if phone_str and phone_str not in seen:
            normalized = _phone_to_petersen_txt(phone_str)
            if normalized:
                tel1_phones.append(normalized)
                seen.add(phone_str)
    
    return tel1_phones


def write_tel1_phones_txt(df: pd.DataFrame, out_path: Path, encoding: str = "utf-8-sig") -> None:
    """
    Escribe un archivo TXT con solo los teléfonos de la columna TEL1.
    
    Args:
        df: DataFrame con datos consolidados
        out_path: Ruta donde escribir el archivo
        encoding: Codificación del archivo (default: utf-8-sig)
    """
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        tel1_phones = extract_tel1_phones(df)
        
        if not tel1_phones:
            logger.warning(f"No hay teléfonos TEL1 para escribir en {out_path.name}, creando archivo vacío")
            with open(out_path, 'w', encoding=encoding, newline='\n') as f:
                f.write("")
            return
        
        phone_count = 0
        with open(out_path, 'w', encoding=encoding, newline='\n') as f:
            for phone in tel1_phones:
                f.write(f"{phone}\n")
                phone_count += 1
        
        logger.debug(f"Archivo {out_path.name} escrito exitosamente con {phone_count} teléfonos TEL1 (encoding: {encoding})")
        
    except Exception as e:
        logger.error(f"Error al escribir {out_path.name}: {e}", exc_info=True)
        raise


def extract_all_phones_per_client(df: pd.DataFrame) -> list:
    """
    Extrae todos los teléfonos (TEL1, TEL2, TEL3, TEL4) por cliente/fila.
    Los teléfonos se mantienen tal cual están en la base (sin normalizar con prefijo).
    
    Args:
        df: DataFrame con datos consolidados que debe tener columnas TEL1, TEL2, TEL3, TEL4
    
    Returns:
        Lista de tuplas (telefonos_string, cantidad_telefonos), ordenada por cantidad descendente
    """
    if df.empty:
        return []
    
    phone_cols = ['TEL1', 'TEL2', 'TEL3', 'TEL4']
    available_cols = [col for col in phone_cols if col in df.columns]
    
    if not available_cols:
        return []
    
    client_phones_list = []
    
    for idx, row in df.iterrows():
        phones = []
        for col in available_cols:
            phone = row[col]
            # Mantener el teléfono tal cual está (sin normalizar)
            if pd.notna(phone) and str(phone).strip() and str(phone).strip().lower() not in ['nan', 'none', 'null', '']:
                phone_str = str(phone).strip()
                phones.append(phone_str)
        
        # Unir los teléfonos con coma, o cadena vacía si no hay teléfonos
        client_phones = ','.join(phones) if phones else ''
        phone_count = len(phones)
        client_phones_list.append((client_phones, phone_count))
    
    # Ordenar por cantidad de teléfonos (descendente) - clientes con más teléfonos primero
    client_phones_list.sort(key=lambda x: x[1], reverse=True)
    
    # Retornar solo los strings de teléfonos (ya ordenados)
    return [phones_str for phones_str, _ in client_phones_list]


def write_all_phones_per_client_csv(df: pd.DataFrame, out_path: Path, encoding: str = "utf-8-sig") -> None:
    """
    Escribe un archivo CSV con todos los teléfonos por cliente (TEL1, TEL2, TEL3, TEL4).
    Cada fila contiene los teléfonos de un cliente separados por coma, tal cual aparecen en la base.
    
    Args:
        df: DataFrame con datos consolidados
        out_path: Ruta donde escribir el archivo
        encoding: Codificación del archivo (default: utf-8-sig)
    """
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        client_phones_list = extract_all_phones_per_client(df)
        
        if not client_phones_list:
            logger.warning(f"No hay teléfonos para escribir en {out_path.name}, creando archivo vacío")
            # Crear CSV vacío sin header
            with open(out_path, 'w', encoding=encoding, newline='\n') as f:
                f.write("")
            return
        
        client_count = 0
        with open(out_path, 'w', encoding=encoding, newline='\n') as f:
            # Escribir datos sin header
            for client_phones in client_phones_list:
                # Si hay teléfonos, escribirlos; si no, línea vacía
                f.write(f"{client_phones}\n")
                client_count += 1
        
        logger.debug(f"Archivo {out_path.name} escrito exitosamente con {client_count} clientes (encoding: {encoding})")
        
    except Exception as e:
        logger.error(f"Error al escribir {out_path.name}: {e}", exc_info=True)
        raise


def find_cartera_column(df: pd.DataFrame):
    """Find CARTERA - SEGMENTO column with different name variations."""
    for col in ['CARTERA - SEGMENTO', 'CARTERA_SEGMENTO', 'CARTERA SEGMENTO', 'CARTERA-SEGMENTO']:
        if col in df.columns:
            return col
    return None


def analyze_cartera_distribution(all_integration_data: dict, max_clients: int):
    """
    Analyze cartera distribution across all banks and suggest filters.
    
    Args:
        all_integration_data: Dict {bank_code: {date: integration_df}}
        max_clients: Maximum clients target
    
    Returns:
        Dict with cartera types, counts, and suggestions
    """
    cartera_counts = {}
    bank_cartera_counts = {}
    
    # Collect all cartera types and their counts
    for bank_code, date_groups in all_integration_data.items():
        bank_cartera_counts[bank_code] = {}
        for date, (integration_df, _, _) in date_groups.items():
            if integration_df is None or integration_df.empty:
                continue
            
            cartera_col = find_cartera_column(integration_df)
            if not cartera_col:
                continue
            
            # Count by cartera type for this bank
            bank_counts = integration_df[cartera_col].value_counts().to_dict()
            bank_cartera_counts[bank_code] = bank_counts
            
            # Aggregate total counts
            for cartera, count in bank_counts.items():
                if cartera not in cartera_counts:
                    cartera_counts[cartera] = 0
                cartera_counts[cartera] += count
    
    # Sort by count descending
    sorted_carteras = sorted(cartera_counts.items(), key=lambda x: x[1], reverse=True)
    
    # Find suggestions (carteras that are close to or under max_clients)
    suggestions = []
    cumulative = 0
    for cartera, count in sorted_carteras:
        if count <= max_clients:
            suggestions.append((cartera, count, "individual"))
        cumulative += count
        if cumulative <= max_clients and len(suggestions) == 0:
            suggestions.append((cartera, cumulative, "acumulado"))
    
    return {
        'cartera_counts': cartera_counts,
        'bank_cartera_counts': bank_cartera_counts,
        'sorted_carteras': sorted_carteras,
        'suggestions': suggestions
    }


# Carteras permitidas para filtrado automático
ALLOWED_CARTERAS = [
    '3_SA_RM_T2',
    '3_SA_RM_T1',
    '3_SA_RB_T2',
    '3_SA_RB_T1',
    '3_NA_RM_T1',
    '3_NA_RB_T1',
    '3_MONOTRIBUTO_RM_T1',
    '3_MONOTRIBUTO_RB_T1'
]


def filter_by_allowed_carteras(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra automáticamente el DataFrame por las carteras permitidas.
    
    Las carteras en la base aparecen como "3 - 3_SA_RM_T2", pero se filtran
    por el sufijo (ej: "3_SA_RM_T2").
    
    Args:
        df: DataFrame con datos de integración
    
    Returns:
        DataFrame filtrado con solo las carteras permitidas
    """
    if df.empty:
        return df
    
    cartera_col = find_cartera_column(df)
    if not cartera_col:
        logger.warning("No se encontró columna CARTERA - SEGMENTO. No se aplicará filtro automático.")
        return df
    
    # Normalize column values for comparison
    cartera_values = df[cartera_col].astype(str).str.strip()
    
    # Crear máscara para todas las carteras permitidas
    mask = pd.Series([False] * len(df), index=df.index)
    
    for allowed_cartera in ALLOWED_CARTERAS:
        # Buscar valores que terminen con la cartera permitida (ej: "3 - 3_SA_RM_T2" termina con "3_SA_RM_T2")
        # También buscar coincidencia exacta
        cartera_match = (
            cartera_values.str.endswith(allowed_cartera) |
            (cartera_values == allowed_cartera) |
            (cartera_values == f"3 - {allowed_cartera}")
        )
        mask = mask | cartera_match
    
    filtered = df[mask].copy()
    
    if len(filtered) < len(df):
        logger.info(f"Filtro automático de carteras: {len(df):,} -> {len(filtered):,} registros")
        # Log distribución de carteras encontradas
        if not filtered.empty:
            cartera_dist = filtered[cartera_col].value_counts()
            logger.debug(f"Carteras encontradas: {dict(cartera_dist)}")
    
    return filtered


def filter_by_cartera_segmento(df: pd.DataFrame, cartera_segmento: str) -> pd.DataFrame:
    """
    Filter DataFrame by CARTERA - SEGMENTO column.
    
    Supports flexible matching:
    - Full format: "3 - 3_MONOTRIBUTO_RM_T1"
    - Partial format: "3_MONOTRIBUTO_RM_T1" (matches "3 - 3_MONOTRIBUTO_RM_T1")
    - Case-insensitive matching
    
    Args:
        df: DataFrame with integration data
        cartera_segmento: Value to filter by (can be full or partial)
    
    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df
    
    cartera_col = find_cartera_column(df)
    if not cartera_col:
        logger.warning("No se encontró columna CARTERA - SEGMENTO. No se aplicará filtro.")
        return df
    
    # Normalize filter value
    filter_value = str(cartera_segmento).strip()
    
    # Normalize column values for comparison
    cartera_values = df[cartera_col].astype(str).str.strip()
    
    # Try exact match first
    exact_match = cartera_values == filter_value
    if exact_match.any():
        filtered = df[exact_match].copy()
        logger.debug(f"Filtro exacto encontrado: '{filter_value}' -> {len(filtered):,} registros")
        return filtered
    
    # Try partial match: if filter doesn't start with "3 - ", try matching the suffix
    if not filter_value.startswith('3 - '):
        # Match values that end with the filter value (e.g., "3 - 3_MONOTRIBUTO_RM_T1" matches "3_MONOTRIBUTO_RM_T1")
        partial_match = cartera_values.str.endswith(filter_value, na=False)
        if partial_match.any():
            filtered = df[partial_match].copy()
            logger.debug(f"Filtro parcial encontrado: '{filter_value}' -> {len(filtered):,} registros")
            return filtered
    
    # Try case-insensitive match
    filter_lower = filter_value.lower()
    case_insensitive = cartera_values.str.lower() == filter_lower
    if case_insensitive.any():
        filtered = df[case_insensitive].copy()
        logger.debug(f"Filtro case-insensitive encontrado: '{filter_value}' -> {len(filtered):,} registros")
        return filtered
    
    # Try case-insensitive partial match
    if not filter_value.startswith('3 - '):
        case_insensitive_partial = cartera_values.str.lower().str.endswith(filter_lower, na=False)
        if case_insensitive_partial.any():
            filtered = df[case_insensitive_partial].copy()
            logger.debug(f"Filtro parcial case-insensitive encontrado: '{filter_value}' -> {len(filtered):,} registros")
            return filtered
    
    # No matches found
    logger.warning(f"No se encontraron registros con CARTERA - SEGMENTO = '{filter_value}'")
    logger.debug(f"Valores disponibles en CARTERA - SEGMENTO: {cartera_values.value_counts().head(10).to_dict()}")
    return pd.DataFrame(columns=df.columns)


def apply_early_limit(integration_df: pd.DataFrame, max_per_bank: int) -> pd.DataFrame:
    """Apply limit early in the pipeline for performance."""
    if len(integration_df) <= max_per_bank:
        return integration_df
    return integration_df.head(max_per_bank).copy()


def limit_by_unique_clients(df: pd.DataFrame, max_clients: int, client_key: str = 'DAT3') -> pd.DataFrame:
    """
    Limita el DataFrame a un número máximo de clientes únicos.
    
    Args:
        df: DataFrame con datos consolidados
        max_clients: Número máximo de clientes únicos a mantener
        client_key: Columna que identifica clientes únicos (default: 'DAT3')
    
    Returns:
        DataFrame limitado con máximo max_clients clientes únicos
    """
    if df.empty or max_clients <= 0:
        return df
    
    if client_key not in df.columns:
        logger.warning(f"Columna '{client_key}' no encontrada. Limitando por filas en lugar de clientes únicos.")
        return df.head(max_clients).copy()
    
    # Obtener clientes únicos
    unique_clients = df[client_key].dropna().unique()
    total_unique_clients = len(unique_clients)
    
    if total_unique_clients <= max_clients:
        logger.debug(f"Clientes únicos: {total_unique_clients:,} (dentro del límite de {max_clients:,})")
        return df.copy()
    
    # Seleccionar los primeros max_clients clientes únicos
    selected_clients = unique_clients[:max_clients]
    
    # Filtrar el DataFrame para incluir solo esos clientes
    filtered_df = df[df[client_key].isin(selected_clients)].copy()
    
    logger.info(f"Limitando por clientes únicos: {total_unique_clients:,} -> {max_clients:,} clientes únicos")
    logger.debug(f"Filas antes: {len(df):,}, Filas después: {len(filtered_df):,}")
    
    return filtered_df


def distribute_clients_equally(all_merged: list, max_clients: int) -> pd.DataFrame:
    """
    Concatena todos los DataFrames y luego limita por número de filas.
    
    El límite se aplica directamente sobre filas, como estaba antes.
    
    Args:
        all_merged: Lista de DataFrames consolidados por banco
        max_clients: Número máximo de filas a mantener en total
    
    Returns:
        DataFrame con máximo max_clients filas
    """
    if not all_merged:
        return pd.DataFrame()
    
    # Concatenar todos los DataFrames
    result = pd.concat(all_merged, ignore_index=True)
    total_rows_before = len(result)
    
    logger.debug(f"Total filas antes de limitar: {total_rows_before:,}")
    
    # Limitar directamente por número de filas
    if total_rows_before > max_clients:
        result = result.head(max_clients).copy()
        logger.info(f"Limitando por filas: {total_rows_before:,} -> {max_clients:,} filas")
    else:
        logger.debug(f"Total filas: {total_rows_before:,} (dentro del límite de {max_clients:,})")
    
    total_rows_after = len(result)
    unique_clients_after = result['DAT3'].nunique() if 'DAT3' in result.columns and not result.empty else 0
    
    logger.basic(f"Limitando a {max_clients:,} filas")
    logger.info(f"Total filas: {total_rows_before:,} -> {total_rows_after:,}")
    logger.info(f"Clientes únicos en resultado: {unique_clients_after:,}")
    
    return result


def generate_unique_filename(output_dir: Path, base_date: str = None) -> str:
    """
    Generate unique filename that doesn't overwrite existing files.
    
    Format: truth_YYYYMMDD_HHMMSS.csv
    If file exists, adds counter: truth_YYYYMMDD_HHMMSS_001.csv
    
    Args:
        output_dir: Output directory
        base_date: Date string (YYYYMMDD) from files, or None to use current date
    
    Returns:
        Unique filename
    """
    if base_date:
        date_part = base_date
    else:
        date_part = datetime.now().strftime('%Y%m%d')
    
    timestamp = datetime.now().strftime('%H%M%S')
    base_name = f"truth_{date_part}_{timestamp}"
    
    # Check if file exists, add counter if needed
    counter = 0
    while True:
        if counter == 0:
            filename = f"{base_name}.csv"
        else:
            filename = f"{base_name}_{counter:03d}.csv"
        
        file_path = output_dir / filename
        if not file_path.exists():
            return filename
        
        counter += 1
        if counter > 999:  # Safety limit
            # Fallback: add microsecond timestamp
            microsecond = datetime.now().microsecond
            filename = f"truth_{date_part}_{timestamp}_{microsecond}.csv"
            return filename


def main():
    start_time_total = time.time()
    
    parser = argparse.ArgumentParser(description='ETL para bancos Petersen')
    parser.add_argument('--input', required=False, 
                       default='inputs/petersen/incoming',
                       help='Carpeta con archivos INTEGRACION.csv y PRODCLI_DEELO.csv')
    parser.add_argument('--output', required=False,
                       default='data/petersen',
                       help='Carpeta de salida')
    parser.add_argument('--cartera', required=False,
                       help='Filtrar por tipo de deuda/cartera')
    parser.add_argument('--max-clients', type=int, default=DEFAULT_MAX_CLIENTS,
                       help=f'Máximo de clientes a procesar (default: {DEFAULT_MAX_CLIENTS:,})')
    parser.add_argument('--early-limit-per-bank', type=int, default=0,
                       help='(Opcional) Límite temprano por banco (por filas) para performance. '
                            '0 = desactivado (default). Si se activa, puede reducir el universo '
                            'antes del merge y afectar el resultado final.')
    parser.add_argument('--log-level', required=False,
                       choices=['BASIC', 'INFO', 'DEBUG', 'WARNING', 'ERROR'],
                       help='Nivel de logging (default: BASIC)')
    parser.add_argument('--config', required=False,
                       help='Ruta al archivo de configuración YAML')
    args = parser.parse_args()

    config_path = args.config or str(project_root / 'config' / 'petersen.yaml')
    logger = setup_logging(config_path=config_path, log_level=args.log_level)
    
    logger.basic("=" * 80)
    logger.basic("ETL - BANCOS PETERSEN")
    logger.basic("=" * 80)
    logger.basic(f"Inicio: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    input_folder = args.input
    if not os.path.isabs(input_folder):
        input_folder = str(project_root / input_folder)
    
    if not os.path.isdir(input_folder):
        raise FileNotFoundError(f"Carpeta de entrada no existe: {input_folder}")

    logger.basic(f"Parámetros:")
    logger.basic(f"  - Carpeta de entrada: {input_folder}")
    logger.basic(f"  - Carpeta de salida: {args.output}")
    logger.basic(f"  - Cantidad objetivo de usuarios: {args.max_clients:,}")
    logger.basic(f"  - Filtro automático de carteras: {', '.join(ALLOWED_CARTERAS)}")
    if args.cartera:
        logger.basic(f"  - Filtro adicional por cartera: {args.cartera}")
    
    start_time_load = time.time()
    all_bank_data = load_all_banks(input_folder)
    load_time = time.time() - start_time_load
    
    if not all_bank_data:
        raise ValueError("No se encontraron archivos INTEGRACION.csv o PRODCLI_DEELO.csv")
    
    logger.basic(f"Archivos cargados en {format_time(load_time)}")
    logger.basic(f"Bancos detectados: {len(all_bank_data)}")
    logger.info(f"Archivos cargados en {format_time(load_time)}")
    logger.info(f"Bancos detectados: {len(all_bank_data)}")
    
    if not args.cartera:
        logger.debug("Analizando distribución por tipo de deuda...")
        analysis = analyze_cartera_distribution(all_bank_data, args.max_clients)
        
        logger.info("Tipos de deuda disponibles:")
        for cartera, count in analysis['sorted_carteras'][:10]:
            logger.info(f"  - {cartera}: {count:,} usuarios")
        
        if analysis['suggestions']:
            logger.info(f"Tipos que permiten alcanzar el volumen objetivo ({args.max_clients:,}):")
            for cartera, count, tipo in analysis['suggestions'][:5]:
                logger.info(f"  - {cartera}: {count:,} usuarios ({tipo})")
    else:
        logger.info(f"Filtro automático activo: {len(ALLOWED_CARTERAS)} carteras permitidas")
        if args.cartera:
            logger.info(f"Filtro adicional activo: CARTERA - SEGMENTO = '{args.cartera}'")
    
    num_banks = len(all_bank_data)
    # IMPORTANTE: El límite final (--max-clients) se aplica SOLO al FINAL del pipeline,
    # después de procesar todas las filas. NO se aplica límite temprano por defecto.
    # El límite temprano solo se activa si se especifica explícitamente --early-limit-per-bank
    max_per_bank_early = None
    if hasattr(args, 'early_limit_per_bank') and args.early_limit_per_bank and args.early_limit_per_bank > 0:
        max_per_bank_early = args.early_limit_per_bank
        logger.info(f"Límite temprano activado: {max_per_bank_early:,} filas por banco (solo para performance)")
    
    all_merged = []
    bank_stats = {}
    all_deelo_dfs = []
    
    for bank_code, date_groups in all_bank_data.items():
        bank_start_time = time.time()
        logger.basic(f"Procesando banco: {bank_code}")
        logger.info(f"Procesando banco: {bank_code}")
        
        for date, (integration_df, deelo_df, mailcli_df) in date_groups.items():
            logger.debug(f"Fecha: {date}")
            
            if integration_df is None or integration_df.empty:
                logger.warning(f"No hay datos de integración para {bank_code}/{date}")
                continue
            
            logger.debug(f"Integración: {len(integration_df):,} filas")

            # Log MAILCLI availability
            if mailcli_df is not None and not mailcli_df.empty:
                logger.debug(f"MAILCLI: {len(mailcli_df):,} filas")
            
            # Aplicar filtro automático por carteras permitidas
            logger.debug("Aplicando filtro automático por carteras permitidas...")
            integration_df = filter_by_allowed_carteras(integration_df)
            logger.debug(f"Integración después del filtro automático: {len(integration_df):,} filas")
            
            if integration_df.empty:
                logger.warning(f"No hay registros que coincidan con las carteras permitidas. Saltando banco.")
                continue
            
            # Si se especifica un filtro adicional por parámetro, aplicarlo también
            if args.cartera:
                logger.debug(f"Aplicando filtro adicional por CARTERA - SEGMENTO: {args.cartera}")
                integration_df = filter_by_cartera_segmento(integration_df, args.cartera)
                logger.debug(f"Integración después del filtro adicional: {len(integration_df):,} filas")
                
                if integration_df.empty:
                    logger.warning(f"No hay registros que coincidan con el filtro adicional. Saltando banco.")
                    continue
            
            if deelo_df is not None and not deelo_df.empty:
                validate_sucursal_column(deelo_df)
                all_deelo_dfs.append(deelo_df)
                logger.debug(f"Productos: {len(deelo_df):,} filas")
            
            # NO aplicar límite temprano aquí por defecto - procesar TODAS las filas disponibles
            # El límite se aplicará SOLO al final después de procesar todo
            if max_per_bank_early is not None:
                integration_df = apply_early_limit(integration_df, max_per_bank_early)
                logger.debug(f"Integración después del límite temprano (opcional): {len(integration_df):,} filas")
            else:
                logger.debug(f"Procesando todas las filas disponibles: {len(integration_df):,} filas (sin límite temprano)")
            
            merge_start_time = time.time()
            merged = merge_integration_and_products(integration_df, deelo_df, bank_code)
            merge_time = time.time() - merge_start_time

            if not merged.empty:
                validate_numero_operacion(merged)
                logger.debug(f"Merge completado en {format_time(merge_time)}")
                logger.debug(f"Resultado merge: {len(merged):,} filas")

                # Enrich with email from MAILCLI
                logger.debug("Enriqueciendo con email_registrado...")
                email_start_time = time.time()
                merged = enrich_with_email(merged, mailcli_df, client_key='DAT3')
                email_time = time.time() - email_start_time

                # Log email enrichment stats
                if 'email_registrado' in merged.columns:
                    total_clients = len(merged)
                    clients_with_email = (merged['email_registrado'] != '').sum()
                    email_pct = (clients_with_email / total_clients * 100) if total_clients > 0 else 0
                    logger.debug(f"Email enriquecido en {format_time(email_time)}")
                    logger.info(f"Clientes con email: {clients_with_email:,} / {total_clients:,} ({email_pct:.1f}%)")

                all_merged.append(merged)
                bank_stats[bank_code] = len(merged)
            else:
                logger.warning(f"Merge resultó en DataFrame vacío")
        
        bank_time = time.time() - bank_start_time
        logger.basic(f"Banco {bank_code} procesado en {format_time(bank_time)}")
        logger.info(f"Banco {bank_code} procesado en {format_time(bank_time)}")
    
    if not all_merged:
        raise ValueError("No se generaron datos después del merge")
    
    limit_start_time = time.time()
    final_truth = distribute_clients_equally(all_merged, args.max_clients)
    limit_time = time.time() - limit_start_time
    
    unique_clients_count = final_truth['DAT3'].nunique() if 'DAT3' in final_truth.columns and not final_truth.empty else 0
    logger.basic(f"Total usuarios procesados: {len(final_truth):,} filas ({unique_clients_count:,} clientes únicos)")
    logger.info(f"Total usuarios procesados: {len(final_truth):,} filas ({unique_clients_count:,} clientes únicos)")
    
    exclude_start_time = time.time()
    columns_before = len(final_truth.columns)
    
    columns_to_exclude = ['DAT8', 'DAT9']
    excluded = []
    for col in columns_to_exclude:
        if col in final_truth.columns:
            final_truth = final_truth.drop(columns=[col])
            excluded.append(col)
    
    if excluded:
        logger.debug(f"Columnas excluidas: {', '.join(excluded)}")
    
    columns_after = len(final_truth.columns)
    exclude_time = time.time() - exclude_start_time

    # Final validation/cleanup: deduplicate phone numbers across clients with TEL priority
    logger.basic("Validación final: deduplicando teléfonos (TEL1..TEL4) por prioridad y primer registro...")
    final_truth, phone_dedupe_stats = dedupe_phone_columns(final_truth, phone_cols=['TEL1', 'TEL2', 'TEL3', 'TEL4'])
    logger.info(
        "Teléfonos deduplicados: %s",
        phone_dedupe_stats
    )

    # Final formatting: limit DEUDA VENCIDA_PROD to 2 decimals (avoid float artifacts like 777601.4299999999)
    debt_prod_col = 'DEUDA VENCIDA_PROD'
    if debt_prod_col in final_truth.columns:
        # Keep empty values as empty strings
        raw = final_truth[debt_prod_col].astype(str)
        raw = raw.replace({'': np.nan, 'nan': np.nan, 'None': np.nan, 'NULL': np.nan, 'null': np.nan})
        # Be tolerant to commas as decimal separators
        numeric = pd.to_numeric(raw.str.replace(',', '.', regex=False), errors='coerce')
        rounded = numeric.round(2)
        final_truth[debt_prod_col] = rounded.map(lambda x: f"{x:.2f}" if pd.notna(x) else '')
    
    # Final validation: normalize DAT6 column to fix encoding issues (e.g., "Banco de Entre R¡os" -> "Banco de Entre Ríos")
    dat6_col = 'DAT6'
    if dat6_col in final_truth.columns:
        logger.debug("Normalizando columna DAT6 para corregir problemas de encoding/tildes...")
        
        dat6_values = final_truth[dat6_col].astype(str)
        
        # Count before fixes
        before_count = (dat6_values.str.contains('R¡os', na=False, regex=False)).sum()
        
        # Fix common encoding issues in bank names
        # Windows-1252 -> UTF-8 encoding issue: í (0xED) gets misinterpreted as ¡ (0xA1)
        # Common pattern: "Banco de Entre R¡os" should be "Banco de Entre Ríos"
        dat6_values = dat6_values.str.replace('R¡os', 'Ríos', regex=False)
        
        final_truth[dat6_col] = dat6_values
        
        # Log if any fixes were applied
        after_count = (final_truth[dat6_col].str.contains('Ríos', na=False, regex=False)).sum()
        if before_count > 0:
            logger.info(f"Columna DAT6 normalizada: {before_count:,} registros corregidos (R¡os -> Ríos)")
    
    save_start_time = time.time()
    
    from lib.common.file_utils import extract_date_from_filename
    detected_date = None
    for bank_code, date_groups in all_bank_data.items():
        for date in date_groups.keys():
            detected_date = date
            break
        if detected_date:
            break
    
    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = str(project_root / output_path)
    
    if os.path.isfile(output_path):
        output_dir = os.path.dirname(output_path)
    elif os.path.isdir(output_path) or output_path.endswith('/') or output_path.endswith('\\'):
        output_dir = output_path
    else:
        output_dir = str(project_root / 'data' / 'petersen')
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    base_filename = f"tabla_integradora_{detected_date}" if detected_date else "tabla_integradora"
    timestamp = datetime.now().strftime('%H%M%S')
    output_filename = f"{base_filename}_{timestamp}.csv"
    output_file_path = output_dir / output_filename
    
    logger.basic(f"Guardando tabla integradora: {output_filename}")
    logger.info(f"Guardando tabla integradora: {output_filename}")
    logger.info(f"Filas: {len(final_truth):,}, Columnas: {columns_after}")
    
    final_truth.to_csv(output_file_path, sep=";", index=False, encoding="utf-8-sig")
    save_time = time.time() - save_start_time
    
    logger.basic("Generando archivo de teléfonos...")
    all_phones_df = extract_all_phones(final_truth)
    phones_filename = f"telefonos_{detected_date}_{timestamp}.csv" if detected_date else f"telefonos_{timestamp}.csv"
    phones_file_path = output_dir / phones_filename
    all_phones_df.to_csv(phones_file_path, sep=";", index=False, encoding="utf-8-sig")
    logger.basic(f"Archivo de teléfonos generado: {phones_filename} ({len(all_phones_df):,} teléfonos únicos)")
    logger.info(f"Archivo de teléfonos generado: {phones_filename} ({len(all_phones_df):,} teléfonos únicos)")
    
    # Generar archivo .txt con listado simple de teléfonos (con prefijo +549)
    # Incluir timestamp en el nombre del archivo para tener un archivo único por ejecución
    phones_txt_filename = f"telefonos_petersen_{detected_date}_{timestamp}.txt" if detected_date else f"telefonos_petersen_{timestamp}.txt"
    phones_txt_file_path = output_dir / phones_txt_filename
    write_phones_txt(all_phones_df, phones_txt_file_path, encoding="utf-8-sig")
    logger.basic(f"Archivo de teléfonos TXT generado: {phones_txt_filename} ({len(all_phones_df):,} teléfonos únicos)")
    logger.info(f"Archivo de teléfonos TXT generado: {phones_txt_filename} ({len(all_phones_df):,} teléfonos únicos)")
    
    # Generar archivo .txt con solo teléfonos TEL1 (con prefijo +549)
    tel1_txt_filename = f"telefonos_tel1_{detected_date}_{timestamp}.txt" if detected_date else f"telefonos_tel1_{timestamp}.txt"
    tel1_txt_file_path = output_dir / tel1_txt_filename
    write_tel1_phones_txt(final_truth, tel1_txt_file_path, encoding="utf-8-sig")
    tel1_count = len(extract_tel1_phones(final_truth))
    logger.basic(f"Archivo de teléfonos TEL1 TXT generado: {tel1_txt_filename} ({tel1_count:,} teléfonos únicos)")
    logger.info(f"Archivo de teléfonos TEL1 TXT generado: {tel1_txt_filename} ({tel1_count:,} teléfonos únicos)")
    
    # Generar archivo CSV con todos los teléfonos por cliente (TEL1, TEL2, TEL3, TEL4) separados por coma
    # Los teléfonos se mantienen tal cual están en la base (sin prefijo +549)
    all_phones_per_client_filename = f"telefonos_petersen_por_cliente_{detected_date}_{timestamp}.csv" if detected_date else f"telefonos_petersen_por_cliente_{timestamp}.csv"
    all_phones_per_client_file_path = output_dir / all_phones_per_client_filename
    write_all_phones_per_client_csv(final_truth, all_phones_per_client_file_path, encoding="utf-8-sig")
    client_count = len(final_truth)
    logger.basic(f"Archivo de teléfonos por cliente CSV generado: {all_phones_per_client_filename} ({client_count:,} clientes)")
    logger.info(f"Archivo de teléfonos por cliente CSV generado: {all_phones_per_client_filename} ({client_count:,} clientes)")
    
    total_time = time.time() - start_time_total
    total_minutes = total_time / 60
    
    logger.basic(f"Archivo guardado: {output_file_path}")
    logger.basic(f"Tiempo transcurrido: {total_minutes:.1f} minutos")
    logger.basic(f"Proceso completado: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.basic("=" * 80)
    logger.info(f"Archivo guardado: {output_file_path}")
    logger.info(f"Tiempo total: {format_time(total_time)}")
    logger.info(f"Proceso completado: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()

"""
Ingestion module for Petersen ETL.

Processes INTEGRACION.csv (client data) and PRODCLI_DEELO.csv (product data).
"""
import logging
import os
import pandas as pd
from typing import Dict, Optional, Tuple
from lib.common.io import read_smart_excel
from lib.common.file_utils import extract_bank_code, extract_date_from_filename
from lib.common.phone_normalize import normalize_phone_columns

logger = logging.getLogger('petersen_etl')


def find_integration_and_deelo_files(input_folder: str) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Find INTEGRACION.csv, PRODCLI_DEELO.csv, and MAILCLI.xls files organized by bank and date.

    Args:
        input_folder: Path to folder containing input files

    Returns:
        Dictionary structure: {bank_code: {date: {'integracion': path, 'deelo': path, 'mailcli': path}}}
        Note: 'mailcli' is optional and may not be present for all banks/dates.
    """
    if not os.path.isdir(input_folder):
        raise FileNotFoundError(f"Input folder no existe: {input_folder}")
    
    files = [os.path.join(input_folder, f) for f in os.listdir(input_folder)
             if f.lower().endswith(('.csv', '.xls', '.xlsx'))]
    
    result: Dict[str, Dict[str, Dict[str, str]]] = {}
    
    for file_path in files:
        filename = os.path.basename(file_path).upper()
        
        # Extract bank code and date
        bank_code = extract_bank_code(filename)
        date = extract_date_from_filename(filename)
        
        if not bank_code or not date:
            continue
        
        # Classify file type
        if 'INTEGRACION' in filename:
            if bank_code not in result:
                result[bank_code] = {}
            if date not in result[bank_code]:
                result[bank_code][date] = {}
            result[bank_code][date]['integracion'] = file_path
        
        elif 'PRODCLI_DEELO' in filename or 'DEELO' in filename:
            if bank_code not in result:
                result[bank_code] = {}
            if date not in result[bank_code]:
                result[bank_code][date] = {}
            result[bank_code][date]['deelo'] = file_path

        elif 'MAILCLI' in filename:
            if bank_code not in result:
                result[bank_code] = {}
            if date not in result[bank_code]:
                result[bank_code][date] = {}
            result[bank_code][date]['mailcli'] = file_path

    return result


def load_bank_data(bank_code: str, date: str, file_paths: Dict[str, str]) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Load integration, DEELO, and MAILCLI files for a specific bank and date.

    Args:
        bank_code: Bank code (BER, BSF, BSJ, BSC)
        date: Date string (YYYYMMDD)
        file_paths: Dictionary with 'integracion', 'deelo', and/or 'mailcli' keys

    Returns:
        Tuple of (integration_df, deelo_df, mailcli_df). Any can be None if file not found.
    """
    integration_df = None
    deelo_df = None
    mailcli_df = None
    
    if 'integracion' in file_paths:
        try:
            integration_df = read_smart_excel(file_paths['integracion'])
            if 'DAT3' not in integration_df.columns:
                logger.warning(f"Archivo INTEGRACION para {bank_code}/{date} no tiene columna DAT3")
                integration_df = None
            else:
                integration_df = normalize_phone_columns(integration_df)
        except Exception as e:
            logger.error(f"Error leyendo INTEGRACION para {bank_code}/{date}: {e}")
            integration_df = None
    
    if 'deelo' in file_paths:
        try:
            deelo_df = read_smart_excel(file_paths['deelo'])
            if 'NUMERO CLIENTE' not in deelo_df.columns:
                logger.warning(f"Archivo PRODCLI_DEELO para {bank_code}/{date} no tiene columna NUMERO CLIENTE")
                deelo_df = None
            else:
                deelo_df = normalize_phone_columns(deelo_df)
        except Exception as e:
            logger.error(f"Error leyendo PRODCLI_DEELO para {bank_code}/{date}: {e}")
            deelo_df = None

    # Load MAILCLI file (optional)
    if 'mailcli' in file_paths:
        try:
            mailcli_df = read_smart_excel(file_paths['mailcli'])
            if 'NUMERO CLIENTE' not in mailcli_df.columns or 'EMAIL' not in mailcli_df.columns:
                print(f"[WARN] Archivo MAILCLI para {bank_code}/{date} no tiene columnas requeridas (NUMERO CLIENTE, EMAIL)")
                mailcli_df = None
        except Exception as e:
            print(f"[ERROR] Error leyendo MAILCLI para {bank_code}/{date}: {e}")
            mailcli_df = None

    return integration_df, deelo_df, mailcli_df


def load_all_banks(input_folder: str) -> Dict[str, Dict[str, Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]]]:
    """
    Load all bank data from input folder.

    Args:
        input_folder: Path to folder containing input files

    Returns:
        Dictionary structure: {bank_code: {date: (integration_df, deelo_df, mailcli_df)}}
    """
    file_structure = find_integration_and_deelo_files(input_folder)
    result = {}

    for bank_code, date_groups in file_structure.items():
        result[bank_code] = {}
        for date, file_paths in date_groups.items():
            integration_df, deelo_df, mailcli_df = load_bank_data(bank_code, date, file_paths)
            result[bank_code][date] = (integration_df, deelo_df, mailcli_df)

    return result


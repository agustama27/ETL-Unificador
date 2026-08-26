"""
Utility functions for file and filename parsing.

Provides functions to extract bank codes, dates, and other metadata from filenames.
"""
import re
from typing import Optional, Tuple
from pathlib import Path


# Bank code mapping: 3-letter codes to full bank names
BANK_CODE_MAP = {
    "BER": "Banco Entre Rios",
    "BSF": "Banco Santa Fe",
    "BSJ": "Banco San Juan",
    "BSC": "Banco Santa Cruz",
}


def extract_bank_code(filename: str) -> Optional[str]:
    """
    Extract bank code from filename.
    
    Looks for 3-letter bank codes (BER, BSF, BSJ, BSC) in the filename.
    Bank codes are typically found after date prefix (e.g., 20250924_AG002_BERC3BUC_...)
    
    Args:
        filename: Name of the file (with or without path)
    
    Returns:
        Bank code (BER, BSF, BSJ, BSC) or None if not found
    """
    # Extract just the filename if path provided
    name = Path(filename).name.upper()
    
    # Look for bank codes in the filename
    for code in BANK_CODE_MAP.keys():
        if code in name:
            return code
    
    return None


def extract_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract date from filename in format YYYYMMDD.
    
    Expected format: YYYYMMDD_... (e.g., 20250924_AG002_BERC3BUC_...)
    
    Args:
        filename: Name of the file (with or without path)
    
    Returns:
        Date string in format YYYYMMDD or None if not found
    """
    # Extract just the filename if path provided
    name = Path(filename).name
    
    # Look for date pattern YYYYMMDD at the beginning
    date_pattern = re.compile(r'^(\d{8})')
    match = date_pattern.match(name)
    
    if match:
        return match.group(1)
    
    return None


def parse_filename_metadata(filename: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse filename to extract bank code, date, and bank name.
    
    Args:
        filename: Name of the file (with or without path)
    
    Returns:
        Tuple of (bank_code, date, bank_name)
        - bank_code: 3-letter code (BER, BSF, BSJ, BSC) or None
        - date: Date string YYYYMMDD or None
        - bank_name: Full bank name or None
    """
    bank_code = extract_bank_code(filename)
    date = extract_date_from_filename(filename)
    bank_name = BANK_CODE_MAP.get(bank_code) if bank_code else None
    
    return bank_code, date, bank_name


def get_bank_name(bank_code: str) -> Optional[str]:
    """
    Get full bank name from bank code.
    
    Args:
        bank_code: 3-letter bank code (BER, BSF, BSJ, BSC)
    
    Returns:
        Full bank name or None if code not recognized
    """
    return BANK_CODE_MAP.get(bank_code.upper())


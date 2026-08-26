"""
Phone number normalization utilities.

Ensures phones are always treated as strings, never as numeric types.
Removes .0 suffixes and normalizes format.
"""
import re
import pandas as pd
from typing import List


def normalize_phone_string(value) -> str:
    """
    Normalize phone number to string format.
    
    Rules:
    - Always returns string
    - Removes .0 suffix if present
    - Removes spaces, dashes, parentheses
    - Keeps only digits (0-9)
    - Preserves leading zeros
    
    Args:
        value: Phone value (can be string, float, int, etc.)
    
    Returns:
        Normalized phone string, or empty string if invalid
    """
    if pd.isna(value) or value == '' or value is None:
        return ''
    
    phone_str = str(value).strip()
    
    if phone_str.lower() in ['nan', 'none', 'null', '']:
        return ''
    
    phone_str = phone_str.replace('.0', '').rstrip('.')
    
    phone_str = re.sub(r'[^\d]', '', phone_str)
    
    return phone_str


def normalize_phone_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize all phone columns in DataFrame to string format.
    
    Identifies phone columns by name patterns (TEL1, TEL2, TEL3, etc.)
    and normalizes them to strings without .0 suffixes.
    
    Args:
        df: DataFrame that may contain phone columns
    
    Returns:
        DataFrame with normalized phone columns
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    phone_cols = []
    for col in df.columns:
        col_upper = col.upper()
        if re.match(r'TEL\d+', col_upper) or any(keyword in col_upper for keyword in ['TELEFONO', 'PHONE', 'NUMERO_COMPLETO', 'NROTELEFONO']):
            phone_cols.append(col)
    
    for col in phone_cols:
        if col in df.columns:
            df[col] = df[col].apply(normalize_phone_string)
            df[col] = df[col].astype(str)
    
    return df


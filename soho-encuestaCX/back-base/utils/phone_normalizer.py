"""
Phone number normalization utilities.

This module implements the exact normalization logic from the n8n workflow
(ENCUESTA-inbound-wh.json, lines 262-274) to ensure compatibility.
"""
from typing import Optional, Union
import pandas as pd


def normalize_phone(phone: Optional[Union[str, int, float]]) -> str:
    """
    Normalize phone number to match n8n workflow logic.

    This function replicates the JavaScript normalization from the n8n workflow:
    - Handles null/None/NaN values → returns empty string
    - Converts to string and trims whitespace
    - Handles decimal format (e.g., "3454400185.0" → "3454400185")
    - Removes all non-digit characters (including '+', spaces, dashes, etc.)

    Args:
        phone: Phone number in any format (string, int, float, or None)

    Returns:
        Normalized phone number containing only digits, or empty string if None

    Examples:
        >>> normalize_phone("+54 9 11 1234-5678")
        '5491112345678'
        >>> normalize_phone("3454400185.0")
        '3454400185'
        >>> normalize_phone("+351 284 3724")
        '3512843724'
        >>> normalize_phone(None)
        ''
        >>> normalize_phone("")
        ''
        >>> normalize_phone(3454400185)
        '3454400185'
    """
    # Handle None first
    if phone is None:
        return ''

    # Handle pandas NaN/NA (must check before == comparison to avoid ambiguous boolean)
    try:
        if pd.isna(phone):
            return ''
    except (TypeError, ValueError):
        pass

    # Handle empty string
    if phone == '':
        return ''

    # Convert to string and trim whitespace
    phone_str = str(phone).strip()

    # Handle empty string after trimming
    if not phone_str:
        return ''

    # Handle decimal format (e.g., "3454400185.0" → "3454400185")
    # This is important for Excel data that may store numbers as floats
    if '.' in phone_str:
        try:
            # Split on decimal point and take integer part
            phone_str = phone_str.split('.')[0]
        except Exception:
            pass  # If splitting fails, continue with original string

    # Remove all non-digit characters (ASCII digits only: 0-9)
    # This handles: +, spaces, dashes, parentheses, unicode digits, etc.
    normalized = ''.join(char for char in phone_str if char in '0123456789')

    return normalized


def normalize_phone_series(phone_series: pd.Series) -> pd.Series:
    """
    Apply phone normalization to a pandas Series.

    Args:
        phone_series: Series of phone numbers

    Returns:
        Series of normalized phone numbers

    Example:
        >>> df['phone_number'] = normalize_phone_series(df['Teléfono'])
    """
    return phone_series.apply(normalize_phone)

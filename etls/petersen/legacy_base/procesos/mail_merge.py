"""
Email merge logic for MAILCLI files.

This module handles the selection of email addresses from MAILCLI data.
When multiple emails exist for a client, it applies deterministic prioritization rules.
"""
import pandas as pd
from typing import Dict, Optional


def build_email_lookup(mailcli_df: pd.DataFrame) -> Dict[str, str]:
    """
    Build a lookup dictionary mapping client ID to selected email.

    Selection priority (deterministic):
    1. ESTADO == "ACTIVO" (if column exists)
    2. PRINCIPAL == "SI" (case-insensitive)
    3. ORIGEN == "CORE" (if column exists, case-insensitive)
    4. If still tied, sort by EMAIL ascending (for stability)

    Args:
        mailcli_df: DataFrame with MAILCLI data. Expected columns:
                   - NUMERO CLIENTE (required)
                   - EMAIL (required)
                   - PRINCIPAL (optional, SI/NO)
                   - ESTADO (optional, ACTIVO/etc)
                   - ORIGEN (optional, CORE/etc)

    Returns:
        Dictionary {client_id: email_registrado} where client_id and email are normalized strings.
        Empty string values are excluded (only clients with valid emails are included).
    """
    if mailcli_df is None or mailcli_df.empty:
        return {}

    # Validate required columns
    if 'NUMERO CLIENTE' not in mailcli_df.columns or 'EMAIL' not in mailcli_df.columns:
        print("[WARN] MAILCLI DataFrame missing required columns (NUMERO CLIENTE, EMAIL)")
        return {}

    # Create working copy
    df = mailcli_df.copy()

    # Normalize NUMERO CLIENTE and EMAIL
    df['NUMERO CLIENTE'] = df['NUMERO CLIENTE'].astype(str).str.strip()
    df['EMAIL'] = df['EMAIL'].astype(str).str.strip().str.lower()

    # Filter out rows with empty email
    df = df[df['EMAIL'] != '']
    df = df[df['EMAIL'] != 'nan']
    df = df[df['EMAIL'].notna()]

    if df.empty:
        return {}

    # Add priority columns for sorting

    # Priority 1: ESTADO == ACTIVO (if column exists)
    if 'ESTADO' in df.columns:
        df['_priority_estado'] = df['ESTADO'].astype(str).str.strip().str.upper() == 'ACTIVO'
    else:
        df['_priority_estado'] = False

    # Priority 2: PRINCIPAL == SI
    if 'PRINCIPAL' in df.columns:
        df['_priority_principal'] = df['PRINCIPAL'].astype(str).str.strip().str.upper() == 'SI'
    else:
        df['_priority_principal'] = False

    # Priority 3: ORIGEN == CORE (if column exists)
    if 'ORIGEN' in df.columns:
        df['_priority_origen'] = df['ORIGEN'].astype(str).str.strip().str.upper() == 'CORE'
    else:
        df['_priority_origen'] = False

    # Sort by priority (descending for booleans = True first, ascending for email)
    df = df.sort_values(
        by=['_priority_estado', '_priority_principal', '_priority_origen', 'EMAIL'],
        ascending=[False, False, False, True]
    )

    # Select first email per client (after sorting by priority)
    email_lookup = df.groupby('NUMERO CLIENTE')['EMAIL'].first().to_dict()

    return email_lookup


def enrich_with_email(consolidated_df: pd.DataFrame,
                      mailcli_df: Optional[pd.DataFrame],
                      client_key: str = 'DAT3') -> pd.DataFrame:
    """
    Enrich consolidated DataFrame with email_registrado column.

    Args:
        consolidated_df: Consolidated client data. Must have client_key column (e.g., DAT3).
        mailcli_df: MAILCLI DataFrame (can be None or empty).
        client_key: Column name for client identifier in consolidated_df (default: 'DAT3').

    Returns:
        DataFrame with new column 'email_registrado' added.
        If mailcli_df is None/empty, email_registrado will be empty string for all rows.
    """
    if consolidated_df.empty:
        return consolidated_df

    # Ensure client_key exists
    if client_key not in consolidated_df.columns:
        print(f"[WARN] Column '{client_key}' not found in consolidated DataFrame. Cannot enrich with email.")
        consolidated_df['email_registrado'] = ''
        return consolidated_df

    # Build email lookup
    email_lookup = build_email_lookup(mailcli_df)

    if not email_lookup:
        # No emails available, add empty column
        consolidated_df['email_registrado'] = ''
        return consolidated_df

    # Normalize client_key for matching
    consolidated_df = consolidated_df.copy()
    client_ids_normalized = consolidated_df[client_key].astype(str).str.strip()

    # Map emails using lookup
    consolidated_df['email_registrado'] = client_ids_normalized.map(email_lookup).fillna('')

    return consolidated_df

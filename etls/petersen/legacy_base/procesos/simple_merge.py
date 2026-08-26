"""
Merge logic for Petersen ETL.

Merges integration data (DAT3) with product data (NUMERO CLIENTE).
Consolidates multiple products per client and sums debt.
"""
import logging
import pandas as pd
from typing import Optional
from lib.common.phone_normalize import normalize_phone_columns

logger = logging.getLogger('petersen_etl')


def normalize_debt(value) -> float:
    """
    Normalize debt value to positive.
    
    Args:
        value: Debt value (can be string with commas or negative number)
    
    Returns:
        Positive float value
    """
    if pd.isna(value) or value == '':
        return 0.0
    
    # Convert to string, remove commas and spaces
    if isinstance(value, str):
        value_str = value.replace(',', '.').replace(' ', '').strip()
        try:
            value_float = float(value_str)
        except (ValueError, AttributeError):
            return 0.0
    else:
        value_float = float(value)
    
    # Return absolute value (always positive)
    return abs(value_float)


def consolidate_products(deelo_df: pd.DataFrame, client_key: str) -> pd.DataFrame:
    """
    Consolidate multiple products per client into comma-separated values.
    
    For each client:
    - Products are concatenated in a single column (comma-separated)
    - Debt is summed across all products
    - All other product columns are consolidated
    
    Args:
        deelo_df: DataFrame with product data (must have NUMERO CLIENTE)
        client_key: Column name for client identifier (should be 'NUMERO CLIENTE')
    
    Returns:
        Consolidated DataFrame with one row per client
    """
    if deelo_df.empty or client_key not in deelo_df.columns:
        return pd.DataFrame()
    
    # Convert client key to string for consistent grouping
    deelo_df = deelo_df.copy()
    deelo_df[client_key] = deelo_df[client_key].astype(str).str.strip()
    
    # Identify product column
    product_col = None
    for col in ['TIPO DE PRODUCTO', 'TIPO_DE_PRODUCTO', 'PRODUCTO', 'DESCRIPCION DEL PRODUCTO']:
        if col in deelo_df.columns:
            product_col = col
            break
    
    # Identify debt column
    debt_col = None
    for col in ['DEUDA VENCIDA', 'DEUDA_VENCIDA', 'DEUDA']:
        if col in deelo_df.columns:
            debt_col = col
            break
    
    # Function to consolidate values into comma-separated string
    def consolidate_series(series):
        """Consolidate non-empty values into comma-separated string."""
        values = series.astype(str).str.strip()
        values = values[(values != '') & (values != 'nan') & (values != 'None') & (values.notna())]
        if len(values) == 0:
            return ''
        # Remove duplicates while preserving order
        seen = set()
        unique_values = []
        for v in values:
            if v and v not in seen:
                seen.add(v)
                unique_values.append(v)
        return ', '.join(unique_values)
    
    # Build aggregation dictionary
    agg_dict = {}
    
    # For product column, consolidate into comma-separated string
    if product_col:
        agg_dict[product_col] = consolidate_series
    
    # For debt column, sum and normalize to positive
    if debt_col:
        def sum_and_normalize(series):
            total = 0.0
            for val in series:
                total += normalize_debt(val)
            return total
        agg_dict[debt_col] = sum_and_normalize
    
    # For all other columns, take first value or consolidate
    for col in deelo_df.columns:
        if col == client_key:
            continue
        if col not in agg_dict:
            # For text columns, consolidate; for numeric, take first
            if deelo_df[col].dtype == 'object':
                agg_dict[col] = consolidate_series
            else:
                agg_dict[col] = 'first'
    
    # Group by client and aggregate
    consolidated = deelo_df.groupby(client_key, as_index=False).agg(agg_dict)
    
    return consolidated


def merge_integration_and_products(integration_df: pd.DataFrame, 
                                  deelo_df: pd.DataFrame,
                                  bank_code: str) -> pd.DataFrame:
    """
    Merge integration data with product data.
    
    Args:
        integration_df: DataFrame with integration data (must have DAT3)
        deelo_df: DataFrame with product data (must have NUMERO CLIENTE)
        bank_code: Bank code (BER, BSF, BSJ, BSC)
    
    Returns:
        Merged DataFrame with all columns from both sources
    """
    if integration_df.empty:
        return pd.DataFrame()
    
    # Prepare integration data
    integration_df = integration_df.copy()
    integration_df['DAT3'] = integration_df['DAT3'].astype(str).str.strip()
    
    if not deelo_df.empty and 'NUMERO CLIENTE' in deelo_df.columns:
        client_ids = set(integration_df['DAT3'].astype(str).str.strip().unique())
        
        deelo_df_original_size = len(deelo_df)
        deelo_df = deelo_df.copy()
        deelo_df['NUMERO CLIENTE'] = deelo_df['NUMERO CLIENTE'].astype(str).str.strip()
        
        deelo_df = deelo_df[deelo_df['NUMERO CLIENTE'].isin(client_ids)].copy()
        deelo_df_filtered_size = len(deelo_df)
        
        if deelo_df_original_size > 0:
            reduction_pct = (1 - deelo_df_filtered_size / deelo_df_original_size) * 100
            logger.debug(f"Productos filtrados por IDs: {deelo_df_original_size:,} -> {deelo_df_filtered_size:,} filas ({reduction_pct:.1f}% reducción)")
        
        essential_cols = ['NUMERO CLIENTE']
        
        for col in ['TIPO DE PRODUCTO', 'TIPO_DE_PRODUCTO', 'PRODUCTO', 'DESCRIPCION DEL PRODUCTO']:
            if col in deelo_df.columns:
                essential_cols.append(col)
                break
        
        for col in ['DEUDA VENCIDA', 'DEUDA_VENCIDA', 'DEUDA']:
            if col in deelo_df.columns:
                essential_cols.append(col)
                break
        
        # Include SUCURSAL column (required for call processing)
        for col in ['SUCURSAL']:
            if col in deelo_df.columns:
                essential_cols.append(col)
                break
        
        # Include NUMERO DE OPERACION column (required for call processing)
        for col in ['NUMERO DE OPERACION', 'NUMERO_DE_OPERACION', 'NUMERO OPERACION', 'NUMERO_OPERACION']:
            if col in deelo_df.columns:
                essential_cols.append(col)
                break
        
        deelo_df = deelo_df[essential_cols].copy()
        
        deelo_consolidated = consolidate_products(deelo_df, 'NUMERO CLIENTE')
        
        merged = pd.merge(
            integration_df,
            deelo_consolidated,
            left_on='DAT3',
            right_on='NUMERO CLIENTE',
            how='left',
            suffixes=('', '_PROD')
        )
    else:
        merged = integration_df.copy()
    
    merged = normalize_phone_columns(merged)
    merged = merged.fillna('')
    
    return merged


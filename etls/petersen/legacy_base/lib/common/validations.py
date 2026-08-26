"""
Validation functions for ETL pipeline.
"""
import logging
import pandas as pd
from typing import Optional, List, Tuple, Dict, Any

logger = logging.getLogger('petersen_etl')


def validate_sucursal_column(deelo_df: pd.DataFrame) -> None:
    """
    Validate that SUCURSAL column exists in PRODCLI_DEELO.
    
    If column doesn't exist, logs warning but continues processing.
    
    Args:
        deelo_df: DataFrame with product data (PRODCLI_DEELO)
    """
    if deelo_df.empty:
        return
    
    if 'SUCURSAL' not in deelo_df.columns:
        logger.warning("Columna SUCURSAL no encontrada en PRODCLI_DEELO. Continuando sin validación de sucursal.")


def validate_numero_operacion(df: pd.DataFrame) -> None:
    """
    Validate that NUMERO DE OPERACION matches product type.
    
    Rules:
    - Préstamo → should have NroPrestamo
    - Tarjeta → should have NroTarjeta
    
    Logs warnings for mismatches but doesn't abort process.
    
    Args:
        df: Merged DataFrame with product data
    """
    if df.empty:
        return
    
    numero_op_col = None
    tipo_producto_col = None
    nro_prestamo_col = None
    nro_tarjeta_col = None
    
    for col in df.columns:
        col_upper = col.upper()
        if 'NUMERO DE OPERACION' in col_upper or 'NUMERO_DE_OPERACION' in col_upper:
            numero_op_col = col
        elif 'TIPO DE PRODUCTO' in col_upper or 'TIPO_DE_PRODUCTO' in col_upper:
            tipo_producto_col = col
        elif 'NROPRESTAMO' in col_upper or 'NRO_PRESTAMO' in col_upper:
            nro_prestamo_col = col
        elif 'NROTARJETA' in col_upper or 'NRO_TARJETA' in col_upper:
            nro_tarjeta_col = col
    
    if not numero_op_col or not tipo_producto_col:
        return
    
    mismatches = []
    
    for idx, row in df.iterrows():
        numero_op = str(row[numero_op_col]).strip() if pd.notna(row[numero_op_col]) else ''
        tipo_producto = str(row[tipo_producto_col]).strip().upper() if pd.notna(row[tipo_producto_col]) else ''
        
        if not numero_op or not tipo_producto:
            continue
        
        is_prestamo = 'PRESTAMO' in tipo_producto or 'PRÉSTAMO' in tipo_producto
        is_tarjeta = 'TARJETA' in tipo_producto or 'CARD' in tipo_producto
        
        if is_prestamo and nro_prestamo_col:
            nro_prestamo = str(row[nro_prestamo_col]).strip() if pd.notna(row[nro_prestamo_col]) else ''
            if numero_op != nro_prestamo:
                mismatches.append(f"Fila {idx}: Préstamo con NUMERO DE OPERACION={numero_op} != NroPrestamo={nro_prestamo}")
        
        elif is_tarjeta and nro_tarjeta_col:
            nro_tarjeta = str(row[nro_tarjeta_col]).strip() if pd.notna(row[nro_tarjeta_col]) else ''
            if numero_op != nro_tarjeta:
                mismatches.append(f"Fila {idx}: Tarjeta con NUMERO DE OPERACION={numero_op} != NroTarjeta={nro_tarjeta}")
    
    if mismatches:
        logger.warning(f"Se detectaron {len(mismatches)} inconsistencias entre NUMERO DE OPERACION y tipo de producto:")
        for mismatch in mismatches[:10]:
            logger.warning(f"  {mismatch}")
        if len(mismatches) > 10:
            logger.warning(f"  ... y {len(mismatches) - 10} más")


def extract_all_phones(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract all phone numbers with TEL1 priority deduplication.
    
    Priority rules:
    - TEL1 has absolute priority
    - If a number appears as TEL1 in any client, it's kept
    - If a number appears only in TEL2/TEL3, it's assigned to first occurrence
    - Numbers are normalized to strings without .0
    
    Args:
        df: DataFrame with phone columns
    
    Returns:
        DataFrame with 'Telefono' column and optional 'DAT3' for matching
    """
    import re
    from lib.common.phone_normalize import normalize_phone_string
    
    df = df.copy()
    
    phone_cols_priority = []
    phone_cols_other = []
    
    for col in df.columns:
        col_upper = col.upper()
        col_lower = col.lower()
        
        tel_match = re.match(r'TEL(\d+)', col_upper)
        if tel_match:
            priority = int(tel_match.group(1))
            phone_cols_priority.append((priority, col))
        elif any(keyword in col_lower for keyword in ['telefono', 'phone', 'numero_completo', 'nrotelefono']):
            phone_cols_other.append(col)
    
    phone_cols_priority.sort(key=lambda x: x[0])
    
    phone_records = []
    client_id_col = 'DAT3' if 'DAT3' in df.columns else None
    
    for priority, col in phone_cols_priority:
        for idx, row in df.iterrows():
            phone = row[col]
            phone_str = normalize_phone_string(phone)
            
            if phone_str:
                record = {
                    'phone': phone_str,
                    'priority': priority,
                    'row_idx': idx
                }
                if client_id_col:
                    record['client_id'] = str(row[client_id_col]) if pd.notna(row[client_id_col]) else ''
                phone_records.append(record)
    
    for col in phone_cols_other:
        for idx, row in df.iterrows():
            phone = row[col]
            phone_str = normalize_phone_string(phone)
            
            if phone_str:
                record = {
                    'phone': phone_str,
                    'priority': 999,
                    'row_idx': idx
                }
                if client_id_col:
                    record['client_id'] = str(row[client_id_col]) if pd.notna(row[client_id_col]) else ''
                phone_records.append(record)
    
    if not phone_records:
        return pd.DataFrame(columns=['Telefono'])
    
    phones_df = pd.DataFrame(phone_records)
    phones_df = phones_df[phones_df['phone'] != '']
    
    if phones_df.empty:
        return pd.DataFrame(columns=['Telefono'])
    
    phones_df = phones_df.sort_values(['phone', 'priority', 'row_idx'])
    
    best_records = {}
    
    for _, record in phones_df.iterrows():
        phone = record['phone']
        priority = record['priority']
        
        if phone not in best_records:
            best_records[phone] = record
        else:
            if priority < best_records[phone]['priority']:
                best_records[phone] = record
    
    result_data = []
    for phone, record in best_records.items():
        result_row = {'Telefono': phone}
        if client_id_col and 'client_id' in record:
            result_row['DAT3'] = record['client_id']
        result_data.append(result_row)
    
    result_df = pd.DataFrame(result_data)
    result_df = result_df.sort_values('Telefono').reset_index(drop=True)
    
    return result_df


def dedupe_phone_columns(df: pd.DataFrame, phone_cols: Optional[List[str]] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Remove duplicated phone numbers across clients and TEL columns, keeping only the best occurrence.

    Rules (as requested):
    - Priority is by TEL column number: TEL1 > TEL2 > TEL3 > TEL4 (lower number wins)
    - If the same phone appears for multiple clients in the same TEL column, keep the first
      occurrence in the DataFrame order (top-to-bottom)
    - All other occurrences are removed (set to empty string '')

    Notes:
    - Comparison uses normalized phone strings (digits only, removes '.0', strips formatting),
      but the kept cell value is left as-is (original formatting preserved).
    - Also handles duplicates within the same client across TEL columns (keeps the best TEL).

    Returns:
        (clean_df, stats_dict)
    """
    import re
    from lib.common.phone_normalize import normalize_phone_string

    if df is None or df.empty:
        return df, {
            'total_occurrences': 0,
            'unique_phones': 0,
            'duplicates': 0,
            'removed_cells': 0,
        }

    clean = df.copy().reset_index(drop=True)

    # Determine TEL columns and their priority (TEL1, TEL2, ...)
    tel_cols_priority: List[Tuple[int, str]] = []
    if phone_cols is None:
        for col in clean.columns:
            m = re.match(r'^TEL(\d+)$', str(col).upper())
            if m:
                tel_cols_priority.append((int(m.group(1)), col))
    else:
        for col in phone_cols:
            if col in clean.columns:
                m = re.match(r'^TEL(\d+)$', str(col).upper())
                pr = int(m.group(1)) if m else 999
                tel_cols_priority.append((pr, col))

    tel_cols_priority.sort(key=lambda x: x[0])
    if not tel_cols_priority:
        return clean, {
            'total_occurrences': 0,
            'unique_phones': 0,
            'duplicates': 0,
            'removed_cells': 0,
        }

    # Collect all occurrences: (phone_norm, priority, row_pos, col)
    occurrences: List[Tuple[str, int, int, str]] = []
    for priority, col in tel_cols_priority:
        series = clean[col] if col in clean.columns else None
        if series is None:
            continue
        for row_pos, val in series.items():
            phone_norm = normalize_phone_string(val)
            if phone_norm:
                occurrences.append((phone_norm, priority, int(row_pos), col))

    if not occurrences:
        return clean, {
            'total_occurrences': 0,
            'unique_phones': 0,
            'duplicates': 0,
            'removed_cells': 0,
        }

    # Pick the best owner per phone: min(priority, row_pos)
    best: Dict[str, Tuple[int, int, str]] = {}
    for phone_norm, priority, row_pos, col in occurrences:
        candidate = (priority, row_pos, col)
        if phone_norm not in best or candidate[:2] < best[phone_norm][:2]:
            best[phone_norm] = candidate

    # Remove all non-best occurrences
    removed_cells = 0
    for phone_norm, priority, row_pos, col in occurrences:
        if best.get(phone_norm) != (priority, row_pos, col):
            current_norm = normalize_phone_string(clean.at[row_pos, col])
            if current_norm:  # only count if something was present
                clean.at[row_pos, col] = ''
                removed_cells += 1

    stats = {
        'total_occurrences': len(occurrences),
        'unique_phones': len(best),
        'duplicates': len(occurrences) - len(best),
        'removed_cells': removed_cells,
        'tel_columns': [c for _, c in tel_cols_priority],
    }
    return clean, stats

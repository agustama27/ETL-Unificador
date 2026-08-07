"""
Módulo para merge de datos de Roman con Retell
Aplica correcciones manuales de Roman sobre datos de Retell
"""

import pandas as pd
import logging
from typing import Optional


logger = logging.getLogger(__name__)


# Campos que Roman sobrescribe
ROMAN_OVERRIDE_FIELDS = [
    'menciona_0800',
    'tipo_contacto',
    'spech_completo',  # Nota: typo intencional, así está en los datos
    'hubo_interaccion',
    'motivo_reintento',
    'tipo_interaccion',
    'contacto_efectivo',
    'motivo_no_entrega',
    'objetivo_cumplido',
    'duracion_total_seg',
    'interrupcion_al_bot',
    'resultado_solicitud',
    'sentimiento_cliente',
    'tiempo_habla_bot_seg',
    'tiempo_habla_cliente_seg',
    'resultado_efectivamente_informado'
]


# Mapeo de columnas Roman → Retell
ROMAN_COLUMN_MAPPING = {
    '[Salida] Contacto Efectivo': 'contacto_efectivo',
    '[Salida] Duracion Total Seg': 'duracion_total_seg',
    '[Salida] Hubo Interaccion': 'hubo_interaccion',
    '[Salida] Interrupcion Al Bot': 'interrupcion_al_bot',
    '[Salida] Menciona 0800': 'menciona_0800',
    '[Salida] Motivo No Entrega': 'motivo_no_entrega',
    '[Salida] Motivo Reintento': 'motivo_reintento',
    '[Salida] Objetivo Cumplido': 'objetivo_cumplido',
    '[Salida] Resultado Efectivamente Informado': 'resultado_efectivamente_informado',
    '[Salida] Resultado Solicitud': 'resultado_solicitud',
    '[Salida] Sentimiento Cliente': 'sentimiento_cliente',
    '[Salida] Spech Completo': 'spech_completo',  # Nota: typo intencional
    '[Salida] Tiempo Habla Bot Seg': 'tiempo_habla_bot_seg',
    '[Salida] Tiempo Habla Cliente Seg': 'tiempo_habla_cliente_seg',
    '[Salida] Tipo Contacto': 'tipo_contacto',
    '[Salida] Tipo Interaccion': 'tipo_interaccion'
}


def normalize_roman_columns(roman_df: pd.DataFrame) -> pd.DataFrame:
    """
    Renombrar columnas Roman a formato Retell

    Args:
        roman_df: DataFrame de Roman con columnas [Salida]

    Returns:
        pd.DataFrame: DataFrame con columnas normalizadas
    """
    logger.info("Normalizando columnas de Roman...")

    # Copiar DataFrame para no modificar el original
    df = roman_df.copy()

    # Renombrar columnas según el mapeo
    columns_to_rename = {}
    for roman_col, retell_col in ROMAN_COLUMN_MAPPING.items():
        if roman_col in df.columns:
            columns_to_rename[roman_col] = retell_col

    if columns_to_rename:
        df.rename(columns=columns_to_rename, inplace=True)
        logger.info(f"Renombradas {len(columns_to_rename)} columnas de Roman")

    # Renombrar ID de Llamada → Call ID para merge
    if 'ID de Llamada' in df.columns:
        df.rename(columns={'ID de Llamada': 'Call ID'}, inplace=True)

    return df


def convert_boolean_values(value):
    """
    Convertir valores "Sí"/"No" a boolean

    Args:
        value: Valor a convertir

    Returns:
        bool, str o valor original
    """
    if pd.isna(value) or value == '' or value == '-':
        return None

    if isinstance(value, str):
        value_lower = value.strip().lower()
        if value_lower in ['sí', 'si', 's', 'yes', 'true']:
            return True
        elif value_lower in ['no', 'n', 'false']:
            return False

    return value


def convert_numeric_values(value):
    """
    Convertir strings numéricos a int/float

    Args:
        value: Valor a convertir

    Returns:
        int, float o valor original
    """
    if pd.isna(value) or value == '' or value == '-':
        return None

    if isinstance(value, str):
        try:
            # Intentar convertir a int
            if '.' not in value:
                return int(value)
            else:
                return float(value)
        except ValueError:
            return value

    return value


def merge_roman_corrections(
    retell_df: pd.DataFrame,
    roman_df: Optional[pd.DataFrame]
) -> pd.DataFrame:
    """
    Merge Roman corrections into Retell data

    Args:
        retell_df: DataFrame de Retell
        roman_df: DataFrame de Roman (opcional)

    Returns:
        pd.DataFrame: DataFrame con correcciones aplicadas
    """
    if roman_df is None or len(roman_df) == 0:
        logger.info("No hay correcciones Roman para aplicar")
        return retell_df

    logger.info(f"Aplicando correcciones Roman para {len(roman_df)} llamadas...")

    # Normalizar columnas de Roman
    roman_normalized = normalize_roman_columns(roman_df)

    # Verificar que ambos DataFrames tengan Call ID
    if 'Call ID' not in retell_df.columns:
        logger.error("DataFrame de Retell no tiene columna 'Call ID'")
        return retell_df

    if 'Call ID' not in roman_normalized.columns:
        logger.error("DataFrame de Roman no tiene columna 'Call ID' después de normalizar")
        return retell_df

    # Copiar DataFrame de Retell para no modificar el original
    df = retell_df.copy()

    # Preparar DataFrame de Roman solo con columnas que vamos a sobrescribir
    roman_cols = ['Call ID'] + [
        col for col in ROMAN_OVERRIDE_FIELDS
        if col in roman_normalized.columns
    ]
    roman_to_merge = roman_normalized[roman_cols].copy()

    # Renombrar columnas de Roman con sufijo para merge
    rename_dict = {
        col: f'{col}_roman'
        for col in roman_to_merge.columns
        if col != 'Call ID'
    }
    roman_to_merge.rename(columns=rename_dict, inplace=True)

    # Left join en Call ID
    df = df.merge(roman_to_merge, on='Call ID', how='left')

    # Aplicar sobrescrituras campo por campo
    updates_count = 0

    for field in ROMAN_OVERRIDE_FIELDS:
        roman_field = f'{field}_roman'

        if roman_field not in df.columns:
            continue

        # Obtener máscaras de valores
        has_roman_value = df[roman_field].notna() & (df[roman_field] != '') & (df[roman_field] != '-')

        if has_roman_value.sum() > 0:
            # Aplicar conversiones según tipo de campo
            if field in ['contacto_efectivo', 'hubo_interaccion', 'interrupcion_al_bot',
                         'objetivo_cumplido', 'resultado_efectivamente_informado', 'menciona_0800']:
                # Campos booleanos
                df.loc[has_roman_value, roman_field] = df.loc[has_roman_value, roman_field].apply(convert_boolean_values)

            elif field in ['duracion_total_seg', 'tiempo_habla_bot_seg', 'tiempo_habla_cliente_seg']:
                # Campos numéricos
                df.loc[has_roman_value, roman_field] = df.loc[has_roman_value, roman_field].apply(convert_numeric_values)

            # Sobrescribir valores de Retell con valores de Roman donde existan
            for idx in df[has_roman_value].index:
                old_value = df.at[idx, field] if field in df.columns else None
                new_value = df.at[idx, roman_field]

                if old_value != new_value:
                    if field in df.columns:
                        df.at[idx, field] = new_value
                    else:
                        # Si la columna no existe en Retell, crearla
                        df.at[idx, field] = new_value

                    updates_count += 1

                    # Log detallado solo para algunos casos (evitar spam)
                    if updates_count <= 10:
                        call_id_short = df.at[idx, 'Call ID'][:15] + '...'
                        logger.debug(
                            f"Sobrescribiendo {field} para {call_id_short}: "
                            f"{old_value} -> {new_value}"
                        )

        # Eliminar columna temporal de Roman
        df.drop(columns=[roman_field], inplace=True)

    logger.info(
        f"Merge Roman completo: {updates_count} valores actualizados "
        f"en {has_roman_value.sum()} llamadas"
    )

    return df


def validate_roman_data(roman_df: pd.DataFrame) -> bool:
    """
    Validar que el DataFrame de Roman tenga las columnas esperadas

    Args:
        roman_df: DataFrame de Roman

    Returns:
        bool: True si es válido, False si no
    """
    if roman_df is None or len(roman_df) == 0:
        return False

    if 'ID de Llamada' not in roman_df.columns:
        logger.warning("CSV de Roman no tiene columna 'ID de Llamada'")
        return False

    # Verificar que tenga al menos una columna [Salida]
    salida_columns = [col for col in roman_df.columns if col.startswith('[Salida]')]

    if len(salida_columns) == 0:
        logger.warning("CSV de Roman no tiene columnas [Salida]")
        return False

    logger.info(f"CSV de Roman válido: {len(salida_columns)} columnas [Salida]")
    return True

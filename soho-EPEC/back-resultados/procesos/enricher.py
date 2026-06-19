"""
Módulo de enriquecimiento de datos
Orquesta el pipeline completo de enriquecimiento con API y Roman merge
"""

import pandas as pd
import logging
from typing import Optional
from .retell_api import RetellAPIClient
from .merger import merge_roman_corrections


logger = logging.getLogger(__name__)


def enrich_retell_export(
    retell_df: pd.DataFrame,
    api_client: RetellAPIClient,
    roman_df: Optional[pd.DataFrame]
) -> pd.DataFrame:
    """
    Pipeline completo de enriquecimiento

    Args:
        retell_df: DataFrame de Retell
        api_client: Cliente de API de Retell
        roman_df: DataFrame de Roman (opcional)

    Returns:
        pd.DataFrame: DataFrame enriquecido
    """
    logger.info(f"Iniciando enriquecimiento para {len(retell_df)} llamadas")

    # Copiar DataFrame para no modificar el original
    df = retell_df.copy()

    # 1. Extraer Call IDs
    if 'Call ID' not in df.columns:
        logger.error("DataFrame no tiene columna 'Call ID'")
        raise ValueError("DataFrame de Retell debe tener columna 'Call ID'")

    call_ids = df['Call ID'].dropna().unique().tolist()
    logger.info(f"Obteniendo datos de API para {len(call_ids)} Call IDs únicos")

    # 2. Fetch en batch desde API
    call_details_map = api_client.batch_fetch_calls(call_ids)

    # 3. Inicializar columnas nuevas
    _initialize_new_columns(df)

    # 4. Procesar cada llamada
    successful_enrichments = 0
    failed_enrichments = 0

    for idx, row in df.iterrows():
        call_id = row['Call ID']

        # Obtener detalles de la llamada
        call_details = call_details_map.get(call_id)

        if call_details:
            # Extraer variables y agregar al DataFrame
            _enrich_row(df, idx, call_id, call_details, api_client)
            df.at[idx, 'api_fetch_status'] = 'success'
            successful_enrichments += 1
        else:
            df.at[idx, 'api_fetch_status'] = 'failed'
            failed_enrichments += 1

        # Log progreso cada 10 registros
        if (idx + 1) % 10 == 0 or (idx + 1) == len(df):
            logger.info(
                f"Enriquecimiento: {idx + 1}/{len(df)} registros procesados "
                f"({successful_enrichments} exitosos, {failed_enrichments} fallidos)"
            )

    logger.info(
        f"Enriquecimiento API completo: {successful_enrichments}/{len(df)} exitosos"
    )

    # 5. Aplicar merge de Roman si existe
    if roman_df is not None:
        df = merge_roman_corrections(df, roman_df)
    else:
        logger.info("No hay correcciones Roman para aplicar")

    logger.info(f"Enriquecimiento completo: {len(df)} registros procesados")

    return df


def _initialize_new_columns(df: pd.DataFrame) -> None:
    """
    Inicializar columnas nuevas en el DataFrame

    Args:
        df: DataFrame a modificar (in-place)
    """
    # Variables dinámicas
    new_columns = [
        'dni_cliente',
        'credito',
        'monto_exacto',
        'customer_name',
        'user_number',
        # Variables de análisis (pueden ya existir en Retell CSV)
        'campaign_id',
        'contact_id',
        'contacto_efectivo',
        'tipo_contacto',
        'speech_completo',
        'motivo_no_entrega',
        'resultado_solicitud',
        'resultado_efectivamente_informado',
        'hubo_interaccion',
        'tipo_interaccion',
        'menciona_0800',
        'objetivo_cumplido',
        'sentimiento_cliente',
        'interrupcion_al_bot',
        'duracion_total_seg',
        'tiempo_habla_cliente_seg',
        'tiempo_habla_bot_seg',
        'motivo_reintento',
        # Metadata
        'script_version',
        'call_datetime',
        # Status
        'api_fetch_status'
    ]

    for col in new_columns:
        if col not in df.columns:
            df[col] = None


def _enrich_row(
    df: pd.DataFrame,
    idx: int,
    call_id: str,
    call_details: dict,
    api_client: RetellAPIClient
) -> None:
    """
    Enriquecer una fila del DataFrame con datos de la API

    Args:
        df: DataFrame a modificar (in-place)
        idx: Índice de la fila
        call_id: ID de la llamada
        call_details: Detalles de la llamada desde API
        api_client: Cliente de API
    """
    # Extraer variables dinámicas
    dynamic_vars = api_client.extract_dynamic_variables(call_details)
    for key, value in dynamic_vars.items():
        if value is not None:
            df.at[idx, key] = value

    # Extraer variables de análisis
    analysis_vars = api_client.extract_analysis_variables(call_details)
    for key, value in analysis_vars.items():
        if value is not None:
            # Solo sobrescribir si la columna no tiene valor o está vacía
            if pd.isna(df.at[idx, key]) or df.at[idx, key] == '':
                df.at[idx, key] = value
            else:
                # Si ya existe un valor en Retell CSV, preservarlo
                logger.debug(
                    f"Preservando valor existente de Retell para {key} "
                    f"en call {call_id[:15]}..."
                )

    # Extraer metadata
    metadata = api_client.extract_metadata(call_details)
    for key, value in metadata.items():
        if value is not None:
            df.at[idx, key] = value


def get_enrichment_summary(df: pd.DataFrame) -> dict:
    """
    Obtener resumen de estadísticas de enriquecimiento

    Args:
        df: DataFrame enriquecido

    Returns:
        dict: Estadísticas de enriquecimiento
    """
    if 'api_fetch_status' not in df.columns:
        return {
            'total': len(df),
            'successful': 0,
            'failed': 0,
            'success_rate': 0.0
        }

    successful = (df['api_fetch_status'] == 'success').sum()
    failed = (df['api_fetch_status'] == 'failed').sum()
    total = len(df)

    return {
        'total': total,
        'successful': successful,
        'failed': failed,
        'success_rate': (successful / total * 100) if total > 0 else 0.0
    }


def validate_enriched_data(df: pd.DataFrame) -> bool:
    """
    Validar que el DataFrame enriquecido tenga las columnas esperadas

    Args:
        df: DataFrame enriquecido

    Returns:
        bool: True si es válido, False si no
    """
    required_columns = [
        'Call ID',
        'api_fetch_status'
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        logger.error(f"Columnas faltantes en DataFrame enriquecido: {missing_columns}")
        return False

    # Verificar que al menos algunas llamadas fueron enriquecidas exitosamente
    if 'api_fetch_status' in df.columns:
        successful = (df['api_fetch_status'] == 'success').sum()
        if successful == 0:
            logger.warning("Ninguna llamada fue enriquecida exitosamente")
            return False

    return True

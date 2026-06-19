"""
Módulo para generación de reportes de tipificación
Genera reportes con columnas específicas y filtrado
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from .retell_api import RetellAPIClient


logger = logging.getLogger(__name__)


# Columnas del reporte de tipificación (18 columnas en 10 categorías)
TIPIFICACION_COLUMNS = [
    # 1. Identificación
    'campaign_id',
    'contact_id',
    'call_datetime',
    'script_version',
    # 2. Contactabilidad
    'contacto_efectivo',
    'tipo_contacto',
    # 3. Entrega del mensaje
    'speech_completo',
    'motivo_no_entrega',
    # 4. Contenido informado
    'resultado_solicitud',
    'resultado_efectivamente_informado',
    # 5. Interacción del cliente
    'hubo_interaccion',
    'tipo_interaccion',
    # 6. Mención del 0800
    'menciona_0800',
    # 7. Objetivo de la llamada
    'objetivo_cumplido',
    # 8. Experiencia
    'sentimiento_cliente',
    'interrupcion_al_bot',
    # 9. Tiempos
    'duracion_total_seg',
    'tiempo_habla_cliente_seg',
    'tiempo_habla_bot_seg',
    # 10. Reintentos
    'motivo_reintento'
]


def generate_tipification_report(enriched_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generar reporte de tipificación desde datos enriquecidos

    Args:
        enriched_df: DataFrame enriquecido con API + Roman

    Returns:
        pd.DataFrame: Reporte de tipificación filtrado
    """
    logger.info("Generando reporte de tipificación...")

    # Verificar columnas requeridas presentes
    missing_columns = [
        col for col in TIPIFICACION_COLUMNS
        if col not in enriched_df.columns
    ]

    if missing_columns:
        logger.warning(
            f"Columnas faltantes en DataFrame enriquecido: {missing_columns}. "
            f"El reporte se generará con las columnas disponibles."
        )

    # Obtener solo las columnas que existen
    available_columns = [
        col for col in TIPIFICACION_COLUMNS
        if col in enriched_df.columns
    ]

    # Filtrar: Solo registros con contacto efectivo
    # (puedes ajustar este criterio según necesites)
    if 'contacto_efectivo' in enriched_df.columns:
        # Filtrar donde contacto_efectivo es True, 'Sí', 'Si', o similar
        mask = (
            (enriched_df['contacto_efectivo'] == True) |
            (enriched_df['contacto_efectivo'] == 'Sí') |
            (enriched_df['contacto_efectivo'] == 'Si') |
            (enriched_df['contacto_efectivo'] == 'true') |
            (enriched_df['contacto_efectivo'] == 'TRUE')
        )
        df_filtered = enriched_df[mask].copy()
        logger.info(
            f"Filtrados {len(df_filtered)} registros con contacto efectivo "
            f"de {len(enriched_df)} totales"
        )
    else:
        logger.warning("No se pudo filtrar por contacto_efectivo (columna faltante)")
        df_filtered = enriched_df.copy()

    # Poblar contact_id con numero telefonico al que se llamo
    if 'contact_id' in available_columns:
        phone_col = None
        if 'user_number' in df_filtered.columns and df_filtered['user_number'].notna().any():
            phone_col = 'user_number'
        elif 'To' in df_filtered.columns and df_filtered['To'].notna().any():
            phone_col = 'To'
        elif 'From' in df_filtered.columns and df_filtered['From'].notna().any():
            phone_col = 'From'

        if phone_col:
            df_filtered['contact_id'] = (
                df_filtered[phone_col]
                .dropna()
                .astype(float)
                .astype(int)
                .astype(str)
            )
            logger.info(f"contact_id poblado con {phone_col}")

    # Seleccionar solo columnas de tipificación
    df_report = df_filtered[available_columns].copy()

    # Ordenar por call_datetime si existe
    if 'call_datetime' in df_report.columns:
        df_report['call_datetime'] = pd.to_datetime(
            df_report['call_datetime'],
            errors='coerce'
        )
        df_report.sort_values('call_datetime', inplace=True)

    # Convertir booleanos True/False a Si/No
    BOOLEAN_COLUMNS = [
        'contacto_efectivo', 'resultado_efectivamente_informado',
        'hubo_interaccion', 'menciona_0800',
        'objetivo_cumplido', 'interrupcion_al_bot'
    ]
    bool_map = {
        True: 'Si', False: 'No',
        'true': 'Si', 'false': 'No',
        'TRUE': 'Si', 'FALSE': 'No',
        'True': 'Si', 'False': 'No'
    }
    for col in BOOLEAN_COLUMNS:
        if col in df_report.columns:
            df_report[col] = df_report[col].map(bool_map).fillna(df_report[col])

    # Limpiar valores null/vacios
    df_report = df_report.fillna('')

    logger.info(
        f"Reporte generado: {len(df_report)} registros, "
        f"{len(df_report.columns)} columnas"
    )

    return df_report


def update_tipification_report(
    new_retell_df: pd.DataFrame,
    existing_report_path: Path,
    api_client: RetellAPIClient
) -> pd.DataFrame:
    """
    Actualizar reporte existente con datos frescos

    Args:
        new_retell_df: Nuevo DataFrame de Retell
        existing_report_path: Path al reporte existente
        api_client: Cliente de API

    Returns:
        pd.DataFrame: Reporte actualizado
    """
    logger.info(f"Actualizando reporte existente: {existing_report_path.name}")

    # Leer reporte existente
    if not existing_report_path.exists():
        raise FileNotFoundError(f"Reporte no encontrado: {existing_report_path}")

    existing_report = pd.read_csv(existing_report_path, encoding='utf-8-sig')
    logger.info(f"Reporte existente: {len(existing_report)} registros")

    # Extraer Call IDs del nuevo export
    if 'Call ID' not in new_retell_df.columns:
        raise ValueError("DataFrame de Retell debe tener columna 'Call ID'")

    call_ids = new_retell_df['Call ID'].dropna().unique().tolist()
    logger.info(f"Actualizando datos para {len(call_ids)} llamadas")

    # Fetch datos frescos de API
    call_details_map = api_client.batch_fetch_calls(call_ids)

    # Crear DataFrame temporal con datos frescos
    updates = []

    for call_id, call_details in call_details_map.items():
        if call_details is None:
            continue

        # Extraer variables de análisis
        analysis_vars = api_client.extract_analysis_variables(call_details)

        # Agregar Call ID para merge
        analysis_vars['Call ID'] = call_id

        updates.append(analysis_vars)

    if not updates:
        logger.warning("No se obtuvieron actualizaciones desde la API")
        return existing_report

    df_updates = pd.DataFrame(updates)
    logger.info(f"Obtenidas actualizaciones para {len(df_updates)} llamadas")

    # Actualizar reporte existente
    # Nota: Esto asume que el reporte existente tiene una columna 'Call ID'
    # Si no la tiene, necesitaríamos otra estrategia de merge

    if 'Call ID' not in existing_report.columns:
        logger.warning(
            "Reporte existente no tiene columna 'Call ID'. "
            "No se puede actualizar."
        )
        return existing_report

    # Merge: actualizar columnas de análisis
    analysis_columns = [
        col for col in df_updates.columns
        if col in TIPIFICACION_COLUMNS and col != 'Call ID'
    ]

    for col in analysis_columns:
        if col in existing_report.columns:
            # Actualizar valores existentes
            existing_report = existing_report.merge(
                df_updates[['Call ID', col]].rename(columns={col: f'{col}_new'}),
                on='Call ID',
                how='left'
            )

            # Sobrescribir con valores nuevos donde existan
            mask = existing_report[f'{col}_new'].notna()
            existing_report.loc[mask, col] = existing_report.loc[mask, f'{col}_new']

            # Eliminar columna temporal
            existing_report.drop(columns=[f'{col}_new'], inplace=True)

    logger.info("Reporte actualizado exitosamente")

    return existing_report


def get_report_filename() -> str:
    """
    Generar nombre de archivo para reporte de tipificacion

    Returns:
        str: Nombre de archivo con formato epec_gestiones_evoltis_YYYYMMDD.csv
    """
    today = datetime.now().strftime('%Y%m%d')
    return f'epec_gestiones_evoltis_{today}.csv'


def get_campaign_id_for_run(execution_date: Optional[datetime] = None) -> str:
    """
    Generar campaign_id para la ejecucion actual

    Args:
        execution_date: Fecha de ejecucion (opcional, usa fecha actual si None)

    Returns:
        str: campaign_id con formato YYYYMMDD
    """
    run_date = execution_date or datetime.now()
    return run_date.strftime('%Y%m%d')


def get_latest_tipification_report(results_folder: Path) -> Optional[Path]:
    """
    Obtener el reporte de tipificación más reciente

    Args:
        results_folder: Carpeta de resultados

    Returns:
        Optional[Path]: Path al reporte más reciente o None
    """
    # Buscar archivos que coincidan con el patrón
    pattern = 'epec_gestiones_evoltis_*.csv'
    reports = list(results_folder.glob(pattern))

    if not reports:
        logger.info("No se encontraron reportes de tipificación existentes")
        return None

    # Ordenar por fecha de modificación (más reciente primero)
    reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    latest_report = reports[0]
    logger.info(f"Reporte más reciente encontrado: {latest_report.name}")

    return latest_report


def validate_report(df: pd.DataFrame) -> bool:
    """
    Validar que el reporte tenga la estructura esperada

    Args:
        df: DataFrame del reporte

    Returns:
        bool: True si es válido, False si no
    """
    if df is None or len(df) == 0:
        logger.warning("Reporte está vacío")
        return False

    # Verificar que tenga al menos algunas columnas clave
    key_columns = ['contacto_efectivo', 'tipo_contacto']
    missing_key_columns = [col for col in key_columns if col not in df.columns]

    if missing_key_columns:
        logger.warning(f"Columnas clave faltantes en reporte: {missing_key_columns}")
        return False

    logger.info(f"Reporte válido: {len(df)} registros, {len(df.columns)} columnas")
    return True

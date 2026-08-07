"""
Sistema de Procesamiento de Call Center
CLI principal para enriquecimiento y generacion de reportes
"""

import sys
import argparse
from pathlib import Path

# Imports de modulos propios
sys.path.insert(0, str(Path(__file__).parent / 'back-resultados'))

from config import load_config, setup_logger, get_log_file_path
from procesos.csv_handler import (
    get_latest_file,
    get_roman_file_if_exists,
    read_retell_csv,
    read_roman_csv,
    write_enriched_csv,
    write_tipification_report
)
from procesos.retell_api import RetellAPIClient
from procesos.enricher import enrich_retell_export, get_enrichment_summary
from procesos.report_generator import (
    generate_tipification_report,
    update_tipification_report,
    get_report_filename,
    get_campaign_id_for_run,
    get_latest_tipification_report,
    TIPIFICACION_COLUMNS
)
from procesos.logcall_consolidator import (
    build_output_filename,
    generate_consolidated_dataframe,
    get_consolidation_summary,
    write_consolidated_excel,
)


def main():
    """Punto de entrada principal del CLI"""
    default_command = 'tipif'
    parser = argparse.ArgumentParser(
        description=(
            "Sistema de Procesamiento de Call Center - Retell AI + Roman "
            f"(por defecto ejecuta '{default_command}')"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandos disponibles:
  retell        Enriquecer export de Retell con API y correcciones Roman
  tipif         Generar reporte de tipificacion
  update-tipif  Actualizar reporte existente con datos frescos
  luz           Consolidar Roman + Logcall y generar Excel

Comportamiento por defecto:
  Sin subcomando se ejecuta: tipif

Ejemplos:
  python main.py
  python main.py retell
  python main.py tipif
  python main.py update-tipif
  python main.py luz
        """
    )

    subparsers = parser.add_subparsers(dest='command', required=False)

    # Comando 1: retell enrichment
    parser_retell = subparsers.add_parser(
        'retell',
        help='Enriquecer export de Retell con API y correcciones Roman'
    )

    # Comando 2: tipification report
    parser_tipif = subparsers.add_parser(
        'tipif',
        help='Generar reporte de tipificacion (comando por defecto)'
    )

    # Comando 3: update tipification
    parser_update = subparsers.add_parser(
        'update-tipif',
        help='Actualizar reporte existente con datos frescos'
    )

    # Comando 4: consolidacion Roman + Logcall a Excel
    subparsers.add_parser(
        'luz',
        help='Consolidar Roman + Logcall y generar Excel output_luz_*.xlsx'
    )

    args = parser.parse_args()
    command = args.command or default_command

    # Ejecutar comando
    try:
        if command == 'retell':
            handle_retell_enrichment()
        elif command == 'tipif':
            handle_tipification_report()
        elif command == 'update-tipif':
            handle_update_tipification()
        elif command == 'luz':
            handle_luz_report()

    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


def handle_retell_enrichment():
    """Comando 1: Enriquecimiento completo de export Retell"""
    print("\n" + "="*60)
    print("COMANDO: Enriquecimiento Completo de Export Retell")
    print("="*60 + "\n")

    # Cargar configuracion
    print("[INFO] Cargando configuracion...")
    config = load_config()

    # Setup logger
    log_file = get_log_file_path()
    logger = setup_logger('main', str(log_file))
    logger.info("="*60)
    logger.info("Iniciando comando: retell")
    logger.info("="*60)

    print(f"[LOG] Log file: {log_file}")

    # Inicializar API client
    print("[API] Inicializando cliente API de Retell...")
    api_client = RetellAPIClient(config.retell_api_key, config.retell_base_url)

    try:
        # 1. Obtener archivo de Retell
        print(f"\n[FOLDER] Buscando archivo en: {config.retell_folder}")
        retell_file = get_latest_file(config.retell_folder, "*.csv")
        print(f"[OK] Archivo encontrado: {retell_file.name}")

        # 2. Leer CSV de Retell
        print("\n[READ] Leyendo CSV de Retell...")
        retell_df = read_retell_csv(retell_file)
        print(f"[OK] Cargados {len(retell_df)} registros")

        # 3. Intentar leer CSV de Roman (opcional)
        print(f"\n[FOLDER] Buscando correcciones Roman en: {config.roman_folder}")
        roman_file = get_roman_file_if_exists(config.roman_folder)

        if roman_file:
            print(f"[OK] Archivo Roman encontrado: {roman_file.name}")
            roman_df = read_roman_csv(roman_file)
            if roman_df is not None:
                print(f"[OK] Cargados {len(roman_df)} registros de Roman")
        else:
            print("[INFO] No se encontro archivo Roman (opcional)")
            roman_df = None

        # 4. Enriquecer datos
        print("\n[START] Iniciando enriquecimiento con API de Retell...")
        print("   (Esto puede tomar varios minutos dependiendo del numero de llamadas)")
        enriched_df = enrich_retell_export(retell_df, api_client, roman_df)

        # Asignar campaign_id por fecha de ejecucion
        campaign_id = get_campaign_id_for_run()
        _set_campaign_id(enriched_df, campaign_id)
        print(f"[INFO] campaign_id asignado automaticamente: {campaign_id}")

        # 5. Mostrar resumen
        summary = get_enrichment_summary(enriched_df)
        print(f"\n[STATS] Resumen de enriquecimiento:")
        print(f"   Total de registros: {summary['total']}")
        print(f"   Exitosos: {summary['successful']}")
        print(f"   Fallidos: {summary['failed']}")
        print(f"   Tasa de exito: {summary['success_rate']:.1f}%")

        # 6. Generar nombre de output
        original_id = retell_file.stem.replace('export_', '')
        output_filename = f"export_{original_id}_enriched.csv"
        output_path = config.results_folder / output_filename

        # 7. Escribir output
        print(f"\n[WRITE] Escribiendo CSV enriquecido...")
        write_enriched_csv(enriched_df, output_path)
        print(f"[OK] Archivo escrito: {output_path}")

        # Resumen final
        print("\n" + "="*60)
        print("[OK] ENRIQUECIMIENTO COMPLETADO EXITOSAMENTE")
        print("="*60)
        print(f"\n[FILE] Output: {output_path}")
        print(f"[LOG] Log: {log_file}")
        print()

    except Exception as e:
        logger.error(f"Error en enriquecimiento: {e}", exc_info=True)
        raise


def handle_tipification_report():
    """Comando 2: Generar reporte de tipificacion"""
    print("\n" + "="*60)
    print("COMANDO: Generar Reporte de Tipificacion")
    print("="*60 + "\n")

    # Cargar configuracion
    print("[INFO] Cargando configuracion...")
    config = load_config()

    # Setup logger
    log_file = get_log_file_path()
    logger = setup_logger('main', str(log_file))
    logger.info("="*60)
    logger.info("Iniciando comando: tipif")
    logger.info("="*60)

    print(f"[LOG] Log file: {log_file}")

    # Inicializar API client
    print("[API] Inicializando cliente API de Retell...")
    api_client = RetellAPIClient(config.retell_api_key, config.retell_base_url)

    try:
        # 1. Obtener archivo de Retell
        print(f"\n[FOLDER] Buscando archivo en: {config.retell_folder}")
        retell_file = get_latest_file(config.retell_folder, "*.csv")
        print(f"[OK] Archivo encontrado: {retell_file.name}")

        # 2. Leer CSV de Retell
        print("\n[READ] Leyendo CSV de Retell...")
        retell_df = read_retell_csv(retell_file)
        print(f"[OK] Cargados {len(retell_df)} registros")

        # 3. Intentar leer CSV de Roman (opcional)
        print(f"\n[FOLDER] Buscando correcciones Roman en: {config.roman_folder}")
        roman_file = get_roman_file_if_exists(config.roman_folder)

        if roman_file:
            print(f"[OK] Archivo Roman encontrado: {roman_file.name}")
            roman_df = read_roman_csv(roman_file)
            if roman_df is not None:
                print(f"[OK] Cargados {len(roman_df)} registros de Roman")
        else:
            print("[INFO] No se encontro archivo Roman (opcional)")
            roman_df = None

        # 4. Enriquecer datos
        print("\n[START] Enriqueciendo datos con API de Retell...")
        enriched_df = enrich_retell_export(retell_df, api_client, roman_df)

        # Asignar campaign_id por fecha de ejecucion
        campaign_id = get_campaign_id_for_run()
        _set_campaign_id(enriched_df, campaign_id)
        print(f"[INFO] campaign_id asignado automaticamente: {campaign_id}")

        # 5. Generar reporte de tipificacion
        print("\n[STATS] Generando reporte de tipificacion...")
        report_df = generate_tipification_report(enriched_df)
        print(f"[OK] Reporte generado: {len(report_df)} registros, {len(report_df.columns)} columnas")

        # 6. Generar nombre de archivo
        report_filename = get_report_filename()
        report_path = config.results_folder / report_filename

        # 7. Escribir reporte
        print(f"\n[WRITE] Escribiendo reporte...")
        write_tipification_report(report_df, report_path, TIPIFICACION_COLUMNS)
        print(f"[OK] Reporte escrito: {report_path}")

        # Resumen final
        print("\n" + "="*60)
        print("[OK] REPORTE DE TIPIFICACION GENERADO EXITOSAMENTE")
        print("="*60)
        print(f"\n[FILE] Output: {report_path}")
        print(f"[LOG] Log: {log_file}")
        print(f"[STATS] Registros en reporte: {len(report_df)}")
        print()

    except Exception as e:
        logger.error(f"Error en generacion de reporte: {e}", exc_info=True)
        raise


def handle_update_tipification():
    """Comando 3: Actualizar reporte de tipificacion existente"""
    print("\n" + "="*60)
    print("COMANDO: Actualizar Reporte de Tipificacion")
    print("="*60 + "\n")

    # Cargar configuracion
    print("[INFO] Cargando configuracion...")
    config = load_config()

    # Setup logger
    log_file = get_log_file_path()
    logger = setup_logger('main', str(log_file))
    logger.info("="*60)
    logger.info("Iniciando comando: update-tipif")
    logger.info("="*60)

    print(f"[LOG] Log file: {log_file}")

    # Inicializar API client
    print("[API] Inicializando cliente API de Retell...")
    api_client = RetellAPIClient(config.retell_api_key, config.retell_base_url)

    try:
        # 1. Obtener nuevo archivo de Retell
        print(f"\n[FOLDER] Buscando nuevo archivo en: {config.retell_folder}")
        retell_file = get_latest_file(config.retell_folder, "*.csv")
        print(f"[OK] Archivo encontrado: {retell_file.name}")

        # 2. Leer CSV de Retell
        print("\n[READ] Leyendo CSV de Retell...")
        retell_df = read_retell_csv(retell_file)
        print(f"[OK] Cargados {len(retell_df)} registros")

        # 3. Buscar reporte mas reciente
        print(f"\n[SEARCH] Buscando reporte mas reciente en: {config.results_folder}")
        existing_report_path = get_latest_tipification_report(config.results_folder)

        if not existing_report_path:
            print("[ERROR] No se encontro ningun reporte existente")
            print("   Ejecute primero: python main.py tipif")
            sys.exit(1)

        print(f"[OK] Reporte encontrado: {existing_report_path.name}")

        # 4. Actualizar reporte
        print("\n[UPDATE] Actualizando reporte con datos frescos de API...")
        updated_report = update_tipification_report(
            retell_df,
            existing_report_path,
            api_client
        )

        # Reasignar campaign_id por fecha de ejecucion
        campaign_id = get_campaign_id_for_run()
        _set_campaign_id(updated_report, campaign_id)
        print(f"[INFO] campaign_id actualizado automaticamente: {campaign_id}")

        # 5. Sobrescribir reporte existente
        print(f"\n[WRITE] Escribiendo reporte actualizado...")
        write_tipification_report(updated_report, existing_report_path, TIPIFICACION_COLUMNS)
        print(f"[OK] Reporte actualizado: {existing_report_path}")

        # Resumen final
        print("\n" + "="*60)
        print("[OK] REPORTE ACTUALIZADO EXITOSAMENTE")
        print("="*60)
        print(f"\n[FILE] Reporte: {existing_report_path}")
        print(f"[LOG] Log: {log_file}")
        print(f"[STATS] Registros actualizados: {len(updated_report)}")
        print()

    except Exception as e:
        logger.error(f"Error en actualizacion de reporte: {e}", exc_info=True)
        raise


def handle_luz_report():
    """Comando 4: Consolidar Roman + Logcall en formato Excel estilo Luz"""
    print("\n" + "="*60)
    print("COMANDO: Consolidar Roman + Logcall a Excel")
    print("="*60 + "\n")

    config = load_config(require_api_key=False)

    log_file = get_log_file_path()
    logger = setup_logger('main', str(log_file))
    logger.info("="*60)
    logger.info("Iniciando comando: luz")
    logger.info("="*60)

    print(f"[LOG] Log file: {log_file}")
    print(f"[FOLDER] Roman: {config.roman_folder}")
    print(f"[FOLDER] Logcall: {config.results_folder.parent / 'logcall'}")

    try:
        logcall_folder = config.results_folder.parent / 'logcall'
        consolidated_df = generate_consolidated_dataframe(config.roman_folder, logcall_folder)
        summary = get_consolidation_summary(config.roman_folder, logcall_folder)

        output_filename = build_output_filename()
        output_path = config.results_folder / output_filename
        write_consolidated_excel(consolidated_df, output_path)

        print("\n[STATS] Resumen consolidado:")
        print(f"   Roman (conectados): {summary['roman_rows']}")
        print(f"   Logcall total: {summary['logcall_rows']}")
        print(f"   Logcall RESULT=10 (conectado): {summary['logcall_connected_result_10']}")
        print(f"   Logcall RESULT!=10 (no conectados): {summary['logcall_non_connected_rows']}")
        print(f"   Total output Excel: {len(consolidated_df)}")

        print("\n" + "="*60)
        print("[OK] REPORTE LUZ GENERADO EXITOSAMENTE")
        print("="*60)
        print(f"\n[FILE] Output: {output_path}")
        print(f"[LOG] Log: {log_file}")
        print()

    except Exception as e:
        logger.error(f"Error en generación de reporte luz: {e}", exc_info=True)
        raise


def _set_campaign_id(df, campaign_id: str) -> None:
    """Asignar campaign_id uniforme en el DataFrame de salida."""
    df['campaign_id'] = campaign_id


if __name__ == '__main__':
    main()

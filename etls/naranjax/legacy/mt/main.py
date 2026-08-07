"""Punto de entrada principal del ETL de cobranzas Naranja."""

import argparse
import sys

from procesos.back_resultados import procesar as procesar_back_resultados
from procesos.base_generator import procesar_base
from procesos.phone_extractor import extraer_telefonos


def main():
    """Ejecuta el flujo principal o modo back-resultados."""
    parser = argparse.ArgumentParser(description="ETL Naranja X MT")
    parser.add_argument("--back", action="store_true", help="Procesa LOGCALL + historial y genera DEELO_NAR_USUOLOS")
    parser.add_argument("--logcall", default=None, help="Ruta explícita LOGCALL para --back")
    parser.add_argument("--historial", default=None, help="Ruta explícita historial para --back")
    parser.add_argument("--m30", default=None, help="Ruta explícita base M30 para --back")
    parser.add_argument("--back-output-dir", default=None, help="Directorio de salida para --back")
    parser.add_argument(
        "--strict-phone-quality",
        action="store_true",
        help="Falla en --back si PHONE irrecuperable supera el umbral configurado",
    )
    parser.add_argument(
        "--max-phone-irrecoverable-ratio",
        type=float,
        default=0.05,
        help="Umbral maximo (0..1) de PHONE irrecuperable para --back en modo estricto",
    )
    args = parser.parse_args()

    try:
        if args.back:
            print("Modo back-resultados: procesando fuentes...")
            archivo_usuolos, archivo_anomalias, total = procesar_back_resultados(
                logcall_path=args.logcall,
                historial_path=args.historial,
                m30olos_path=args.m30,
                output_dir=args.back_output_dir,
                strict_phone_quality=args.strict_phone_quality,
                max_phone_irrecoverable_ratio=args.max_phone_irrecoverable_ratio,
            )
            print(f"  -> USUOLOS: {archivo_usuolos}")
            print(f"  -> Anomalías: {archivo_anomalias}")
            print(f"  -> Filas generadas: {total}")
            print("\nProceso back-resultados completado correctamente.")
            return

        # 1. Generar base: TXT de base_recibida -> CSV en base_procesada
        print("Paso 1: Generando base procesada...")
        archivo_base = procesar_base()
        print(f"  -> {archivo_base}")

        # 2. Extraer teléfonos: base_procesada -> telefonos_naranja_DDMMAAAA.csv
        print("Paso 2: Extrayendo teléfonos...")
        archivo_telefonos = extraer_telefonos(archivo_base)
        print(f"  -> {archivo_telefonos}")

        print("\nProceso completado correctamente.")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

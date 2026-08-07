"""
Script principal para generar el CSV de encuestas Claro Uruguay desde Retell.ai.

Procesa los resultados de llamadas de Retell, opcionalmente integra datos de ROMAN,
y genera un CSV de análisis interno con 26 columnas.
"""
import sys
import os
from pathlib import Path

procesos_dir = Path(__file__).parent / "procesos"
sys.path.insert(0, str(procesos_dir))

from tipif_generator import generar_csv_encuestas


def main():
    try:
        print("\n" + "=" * 70)
        print("SISTEMA DE GENERACIÓN DE CSV DE ENCUESTAS CLARO URUGUAY")
        print("=" * 70)
        
        usar_roman_env = os.getenv('USE_ROMAN', 'true').lower()
        usar_roman = usar_roman_env in ['true', '1', 'yes', 'sí', 'si']
        
        if not usar_roman:
            print("\nADVERTENCIA - ROMAN DESHABILITADO (USE_ROMAN=false)")
            print("Solo se usarán datos de Retell")
        
        ruta_archivo = generar_csv_encuestas(usar_roman=usar_roman)
        
        if ruta_archivo:
            print("\n" + "=" * 70)
            print("OK - PROCESO COMPLETADO EXITOSAMENTE")
            print("=" * 70)
            print(f"\nArchivo generado: {ruta_archivo}")
            return 0
        else:
            print("\n" + "=" * 70)
            print("ADVERTENCIA: No se generó ningún archivo")
            print("=" * 70)
            return 1
            
    except KeyboardInterrupt:
        print("\n\nADVERTENCIA - Proceso interrumpido por el usuario")
        return 130
    except Exception as e:
        print("\n" + "=" * 70)
        print("ERROR EN EL PROCESO")
        print("=" * 70)
        print(f"\nError: {str(e)}")
        import traceback
        print("\nDetalles del error:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

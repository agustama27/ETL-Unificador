"""
Script principal para generar el CSV de gestiones Bancor desde Retell.ai

Este script ejecuta el flujo completo:
1. Lee el CSV de la carpeta calls con los Call IDs
2. Consulta la API de Retell.ai para obtener información de cada llamada
3. Extrae las variables dinámicas y postcall de cada llamada
4. Opcionalmente, mergea con datos actualizados de ROMAN
5. Genera un CSV con todas las gestiones en la carpeta results

Variables de entorno:
- USE_ROMAN: Habilita/deshabilita integración con ROMAN (default: true)
              Valores: 'true', 'false'
"""

import sys
import os
from pathlib import Path

# Agregar el directorio procesos al path para importar los módulos
procesos_dir = Path(__file__).parent / "procesos"
sys.path.insert(0, str(procesos_dir))

# Importar la función de generación de CSV
from tipif_generator import generar_csv_gestiones


def main():
    """
    Función principal que ejecuta el flujo completo de generación de CSV.
    """
    try:
        print("\n" + "=" * 70)
        print("SISTEMA DE GENERACIÓN DE CSV DE GESTIONES BANCOR")
        print("=" * 70)

        # Leer configuración de ROMAN desde variable de entorno
        usar_roman_env = os.getenv('USE_ROMAN', 'true').lower()
        usar_roman = usar_roman_env in ['true', '1', 'yes', 'sí', 'si']

        if not usar_roman:
            print("\nADVERTENCIA - ROMAN DESHABILITADO (USE_ROMAN=false)")
            print("Solo se usaran datos de Retell")

        ruta_archivo = generar_csv_gestiones(usar_roman=usar_roman)
        
        if ruta_archivo:
            print("\n" + "=" * 70)
            print("OK - PROCESO COMPLETADO EXITOSAMENTE")
            print("=" * 70)
            print(f"\nArchivo generado: {ruta_archivo}")
            return 0
        else:
            print("\n" + "=" * 70)
            print("ADVERTENCIA: No se genero ningun archivo")
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


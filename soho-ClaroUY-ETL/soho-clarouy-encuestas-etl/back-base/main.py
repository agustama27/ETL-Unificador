"""
Script principal para procesamiento de base de clientes Claro Uruguay.

Procesa la base de clientes y genera:
- base_clarouy_DDMMAAAA.csv: base consolidada
- telefonos_x_cliente_DDMMAAAA.csv: teléfonos para cargar en Retell
"""
from pathlib import Path
import sys

procesos_dir = Path(__file__).parent / "procesos"
sys.path.insert(0, str(procesos_dir))

from base_generator import procesar_base, deduplicar_por_telefonos
from phone_extractor import extraer_telefonos, buscar_base_generada


def main():
    try:
        print("\n" + "=" * 70)
        print("SISTEMA DE PROCESAMIENTO DE BASE CLARO URUGUAY")
        print("=" * 70)
        
        BASE_DIR = Path(__file__).parent
        
        carpeta_entrada = BASE_DIR / "base-recibida"
        carpeta_salida = BASE_DIR / "base-generada" / "con-filtros"
        carpeta_backup = carpeta_salida / "backup"
        
        print("\n--- Paso 1: Procesar base de clientes ---")
        df_base = procesar_base(carpeta_entrada, carpeta_salida)
        
        print("\n--- Paso 2: Deduplicar por teléfonos ---")
        df_dedup = deduplicar_por_telefonos(df_base, carpeta_backup)
        
        fecha = Path(__file__).parent.name
        from datetime import datetime
        fecha_str = datetime.today().strftime('%d%m%Y')
        output_dedup = carpeta_salida / f"base_clarouy_{fecha_str}.csv"
        
        df_dedup.to_csv(
            output_dedup,
            sep=';',
            decimal=',',
            encoding='utf-8',
            index=False,
            na_rep=''
        )
        
        print(f"\n  Base deduplicada guardada: {output_dedup.name}")
        print(f"  Registros: {len(df_dedup)}")
        
        print("\n--- Paso 3: Extraer teléfonos ---")
        base_path = buscar_base_generada(carpeta_salida)
        
        if base_path:
            output_telefonos = carpeta_salida / f"telefonos_x_cliente_{fecha_str}.csv"
            cantidad = extraer_telefonos(base_path, output_telefonos)
            print(f"\n  Teléfonos extraídos: {cantidad}")
        else:
            print("\n  ADVERTENCIA: No se encontró base para extraer teléfonos")
        
        print("\n" + "=" * 70)
        print("OK - PROCESO COMPLETADO EXITOSAMENTE")
        print("=" * 70)
        
        return 0
        
    except FileNotFoundError as e:
        print("\n" + "=" * 70)
        print("ERROR: Archivo no encontrado")
        print("=" * 70)
        print(f"\n{e}")
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

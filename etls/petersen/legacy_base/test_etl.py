"""
Script de prueba para el ETL simplificado.
Ejecuta el ETL y muestra un resumen de los resultados.

Nota: este archivo NO es un test pytest. Se debe ejecutar manualmente:
  python test_etl.py
"""
import sys
from pathlib import Path
import subprocess

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def main() -> int:
    print("=" * 80)
    print("PRUEBA DEL ETL SIMPLIFICADO")
    print("=" * 80)

    # Test 1: Verificar que los módulos se pueden importar
    print("\n[TEST 1] Verificando importación de módulos...")
    try:
        from adapters.petersen.simple_ingest import load_all_banks  # noqa: F401
        from procesos.simple_merge import merge_integration_and_products  # noqa: F401
        print("  ✓ Módulos importados correctamente")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return 1

    # Test 2: Verificar que se encuentran los archivos
    print("\n[TEST 2] Buscando archivos INTEGRACION y PRODCLI_DEELO...")
    input_folder = project_root / 'inputs' / 'petersen' / 'incoming'

    try:
        from adapters.petersen.simple_ingest import find_integration_and_deelo_files
        file_structure = find_integration_and_deelo_files(str(input_folder))

        if not file_structure:
            print("  ✗ No se encontraron archivos")
            return 1

        print(f"  ✓ Encontrados {len(file_structure)} banco(s):")
        total_integracion = 0
        total_deelo = 0
        for bank_code, date_groups in file_structure.items():
            for _, files in date_groups.items():
                if 'integracion' in files:
                    total_integracion += 1
                if 'deelo' in files:
                    total_deelo += 1
            print(f"    - {bank_code}: {len(date_groups)} fecha(s)")

        print(f"\n  Resumen:")
        print(f"    - Archivos INTEGRACION: {total_integracion}")
        print(f"    - Archivos PRODCLI_DEELO: {total_deelo}")

    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Test 3: Ejecutar el ETL
    print("\n[TEST 3] Ejecutando ETL...")
    print("  Comando: python etl.py --input inputs/petersen/incoming --output data/petersen")
    print("  (Esto puede tardar unos segundos...)")

    try:
        result = subprocess.run(
            [sys.executable, 'etl.py', '--input', 'inputs/petersen/incoming', '--output', 'data/petersen'],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300  # 5 minutos máximo
        )

        if result.returncode == 0:
            print("  ✓ ETL ejecutado exitosamente")
            print("\n  Salida del ETL:")
            print("  " + "\n  ".join(result.stdout.split('\n')[-20:]))  # Últimas 20 líneas
        else:
            print(f"  ✗ ETL falló con código {result.returncode}")
            print("\n  Error:")
            print("  " + "\n  ".join(result.stderr.split('\n')[-20:]))
            return 1

    except subprocess.TimeoutExpired:
        print("  ✗ ETL tardó demasiado (timeout)")
        return 1
    except Exception as e:
        print(f"  ✗ Error ejecutando ETL: {e}")
        return 1

    # Test 4: Verificar que se generó el archivo
    print("\n[TEST 4] Verificando archivo generado...")
    output_dir = project_root / 'data' / 'petersen'
    integradora_files = list(output_dir.glob('tabla_integradora_*.csv'))

    if integradora_files:
        latest_file = max(integradora_files, key=lambda p: p.stat().st_mtime)
        print(f"  ✓ Archivo generado: {latest_file.name}")

        # Leer y mostrar estadísticas básicas
        try:
            import pandas as pd
            df = pd.read_csv(latest_file, nrows=1000, sep=';')  # Solo leer muestra
            print(f"\n  Estadísticas del archivo:")
            print(f"    - Filas (muestra): {len(df):,}")
            print(f"    - Columnas: {len(df.columns)}")
            print(f"    - Columnas principales: {list(df.columns)[:10]}")

            if 'DAT3' in df.columns:
                print(f"    - Clientes únicos (muestra): {df['DAT3'].nunique():,}")

        except Exception as e:
            print(f"    (No se pudo leer estadísticas: {e})")
    else:
        print("  ✗ No se encontró archivo tabla_integradora_*.csv")
        return 1

    print("\n" + "=" * 80)
    print("✓ TODAS LAS PRUEBAS COMPLETADAS")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


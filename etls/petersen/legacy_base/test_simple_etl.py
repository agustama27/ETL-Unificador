"""
Script de prueba simple para verificar el nuevo ETL simplificado.

Nota: este archivo NO es un test pytest. Se debe ejecutar manualmente:
  python test_simple_etl.py
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def main() -> int:
    print("[TEST] Probando carga de modulos...")
    try:
        from adapters.petersen.simple_ingest import find_integration_and_deelo_files
        print("  [OK] simple_ingest importado correctamente")
    except Exception as e:
        print(f"  [ERROR] Error importando simple_ingest: {e}")
        return 1

    try:
        from procesos.simple_merge import merge_integration_and_products  # noqa: F401
        print("  [OK] simple_merge importado correctamente")
    except Exception as e:
        print(f"  [ERROR] Error importando simple_merge: {e}")
        return 1

    print("\n[TEST] Buscando archivos INTEGRACION y PRODCLI_DEELO...")
    input_folder = project_root / 'inputs' / 'petersen' / 'incoming'

    try:
        file_structure = find_integration_and_deelo_files(str(input_folder))
        print(f"  [OK] Encontrados {len(file_structure)} banco(s)")
        for bank_code, date_groups in file_structure.items():
            print(f"    - {bank_code}: {len(date_groups)} fecha(s)")
            for date, files in date_groups.items():
                integracion = '[OK]' if 'integracion' in files else '[FALTA]'
                deelo = '[OK]' if 'deelo' in files else '[FALTA]'
                print(f"      {date}: INTEGRACION {integracion}, DEELO {deelo}")
    except Exception as e:
        print(f"  [ERROR] Error buscando archivos: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n[TEST] [OK] Todas las pruebas basicas pasaron")
    print("[INFO] Puedes ejecutar: python etl.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

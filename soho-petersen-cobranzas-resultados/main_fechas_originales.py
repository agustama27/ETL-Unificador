"""
Versión del main.py que preserva las fechas originales del archivo CSV
en lugar de usar la fecha actual.

La fecha se extrae del nombre del archivo CSV de entrada y se usa para
el campo FECHA_ALTA en los archivos generados.

Usage (PowerShell):
  python .\\main_fechas_originales.py

Diferencias con main.py:
  - FECHA_ALTA: usa la fecha del archivo CSV (no la fecha actual)
  - Nombres de carpetas: siguen usando fecha actual (para distinguir ejecuciones)
  - include_all_efectos=True: incluye todos los efectos (incluso RELLAMAR)

Fuentes de datos:
  - roman/:          CSVs exportados de ROMAN (obligatorio)
  - approach/:       Reporte de approach (opcional)
  - base/:           Base de clientes (opcional, para approach)
  - datos-excluidos/: Clientes excluidos (opcional)
"""

from __future__ import annotations

from procesos.paths import get_project_root
from procesos.promesa_validator import (
    export_valid_promesas,
    validate_results,
    export_all_gestiones_fecha_original,
)
from procesos.tipif_generator import generate_tipif_files


def main() -> None:
    base_dir = get_project_root()
    roman_dir = base_dir / "roman"

    result_paths = generate_tipif_files(
        roman_dir=roman_dir,
        include_all_efectos=True,
    )

    print("\nOK - Archivos generados (con fechas originales del CSV):")
    for bank, path in result_paths.items():
        print(f" - {bank}: {path}")

    if result_paths:
        results_dir = list(result_paths.values())[0].parent
        validate_results(results_dir, print_report=True)

        promesas_dir = base_dir / "gestiones-validas"
        archivos_promesas = export_valid_promesas(results_dir, promesas_dir)
        if archivos_promesas:
            print("\nArchivos de promesas válidas generados:")
            for banco, path in archivos_promesas.items():
                print(f" - {banco}: {path}")

        print("\n=== Exportando gestiones completas con fechas originales ===")
        gestiones_fecha_original_dir = base_dir / "gestiones-validas-fecha-original"
        archivos_fecha_original = export_all_gestiones_fecha_original(
            results_dir,
            gestiones_fecha_original_dir
        )
        if archivos_fecha_original:
            print("\n[OK] Archivos con TODAS las gestiones (fechas originales) generados:")
            for banco, path in archivos_fecha_original.items():
                print(f"  - {banco}: {path}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from procesos.approach_merge import run_approach_merge_and_tipify, run_tipify_excluded
from procesos.paths import get_project_root
from procesos.promesa_validator import export_valid_promesas, validate_results
from procesos.tipif_generator import generate_tipif_files

AG002_FILES = [
    "AG002_45.csv",
    "AG002_46.csv",
    "AG002_47.csv",
    "AG002_48.csv",
]


def _build_output_zip(gestiones_dir: Path, output_zip_path: Path) -> None:
    """
    Crea el ZIP final con los 4 archivos AG002 desde archivos_codificacion.
    """
    codificacion_dir = gestiones_dir / "archivos_codificacion"
    if not codificacion_dir.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de codificación esperada: {codificacion_dir}"
        )

    missing_files = [name for name in AG002_FILES if not (codificacion_dir / name).exists()]
    if missing_files:
        raise FileNotFoundError(
            "No se pudieron generar todos los archivos AG002 esperados. "
            f"Faltan: {', '.join(missing_files)}"
        )

    if output_zip_path.exists():
        output_zip_path.unlink()

    with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for file_name in AG002_FILES:
            source_path = codificacion_dir / file_name
            zip_file.write(source_path, arcname=file_name)


def main() -> None:
    r"""
    Usage (PowerShell):
      python .\main.py

    Fuentes de datos:
      - roman/:          CSVs exportados de ROMAN (obligatorio)
      - approach/:       Reporte de approach (opcional)
      - base/:           Base de clientes (opcional, para approach)
      - datos-excluidos/: Clientes excluidos (opcional)
    """
    base_dir = get_project_root()
    roman_dir = base_dir / "roman"
    zip_name = f"Gestiones_Petersen_{datetime.now().strftime('%Y%m%d')}.zip"
    output_zip_path = base_dir / zip_name

    with tempfile.TemporaryDirectory(prefix="petersen_gestiones_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        temp_debug_dir = temp_dir / "debug"
        temp_results_dir = temp_debug_dir / f"gestiones_totales_{datetime.now().strftime('%Y%m%d')}"
        temp_gestiones_validas_dir = temp_dir / "gestiones-validas"

        result_paths = generate_tipif_files(
            roman_dir=roman_dir,
            results_dir=temp_results_dir,
        )
        print("OK - Archivos intermedios generados")
        for bank, path in result_paths.items():
            print(f" - {bank}: {path.name}")

        if not result_paths:
            raise RuntimeError("No se generaron archivos de tipificación intermedios.")

        results_dir = list(result_paths.values())[0].parent
        validate_results(results_dir, print_report=True)

        archivos_promesas = export_valid_promesas(results_dir, temp_gestiones_validas_dir)
        if not archivos_promesas:
            raise RuntimeError("No se generaron archivos de promesas válidas.")

        gestiones_dir = list(archivos_promesas.values())[0].parent.parent

        try:
            _, stats = run_approach_merge_and_tipify(
                gestiones_dir=gestiones_dir,
                debug_folder=temp_debug_dir,
            )
            print("\nApproach merge + tipificación:")
            print(f" - Total matcheados: {stats['total_matcheados']}")
            print(f" - Ya tipificados (omitidos): {stats['ya_tipificados']}")
            print(f" - Banco desconocido (omitidos): {stats['banco_desconocido']}")
            print(f" - Tipificaciones agregadas: {stats['tipificaciones_agregadas']}")
        except FileNotFoundError as e:
            print(f"\n[INFO] Approach merge omitido: {e}")

        try:
            excluded_stats = run_tipify_excluded(gestiones_dir=gestiones_dir)
            print("\nTipificación datos excluidos:")
            print(f" - Total excluidos únicos: {excluded_stats['total_excluidos']}")
            print(f" - Ya tipificados (omitidos): {excluded_stats['excluidos_ya_tipificados']}")
            print(
                " - Banco desconocido (omitidos): "
                f"{excluded_stats['excluidos_banco_desconocido']}"
            )
            print(
                " - Tipificaciones agregadas: "
                f"{excluded_stats['tipificaciones_excluidos_agregadas']}"
            )
        except FileNotFoundError as e:
            print(f"\n[INFO] Tipificación de datos excluidos omitida: {e}")
        except ValueError as e:
            print(f"\n[WARN] Tipificación de datos excluidos falló: {e}")

        _build_output_zip(gestiones_dir=gestiones_dir, output_zip_path=output_zip_path)

    print(f"\n[OK] Salida final generada: {output_zip_path.name}")
    print("Contiene: AG002_45.csv, AG002_46.csv, AG002_47.csv, AG002_48.csv")


if __name__ == "__main__":
    try:
        main()
    finally:
        input("\nPresione Enter para salir...")

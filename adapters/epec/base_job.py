"""Unifier-owned CLI for the EPEC base ETL (back-base).

The legacy ``main()`` anchors its root to the module file, but every helper
takes ``carpeta_base`` as a parameter — this wrapper runs the exact legacy
chain against a sandbox-rooted layout and publishes ``base-generada`` CSVs
into the run ``output/`` directory.
"""

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="EPEC base (unified)")
    parser.add_argument("--input", required=True, help="Raw EPEC CSV")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd() / "back-base"))
    from procesos.base_generator import (combinar_archivos, generar_csv_telefonos,
                                         guardar_csv_consolidado)

    output_dir = Path(arguments.output_dir)
    work = output_dir.parent / "legacy"
    (work / "base-recibida").mkdir(parents=True, exist_ok=True)
    (work / "base-generada" / "debug").mkdir(parents=True, exist_ok=True)
    shutil.copy2(arguments.input, work / "base-recibida" / "base.csv")

    try:
        consolidado = combinar_archivos(work)
        guardar_csv_consolidado(consolidado, work)
        generar_csv_telefonos(consolidado, work)
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1

    for item in (work / "base-generada").glob("*.csv"):
        shutil.copy2(item, output_dir / item.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

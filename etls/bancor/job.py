"""Unifier-owned CLI for the Bancor base ETL (back-base).

The legacy ``main.py`` takes no arguments, anchors every path to the module
file, and swallows step failures. This wrapper anchors the pipeline to the
run sandbox (via the module ``__file__`` seam the functions derive their
``base_dir`` from), runs the exact four-step chain fail-fast, and publishes
``base-generada/**`` into the sandbox ``output/`` directory.
"""

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Bancor base (unified)")
    parser.add_argument("--input", required=True, help="Raw Bancor CSV")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd() / "back-base"))
    from procesos import base_generator
    from procesos.phone_extractor import extraer_telefonos

    output_dir = Path(arguments.output_dir)
    work = output_dir.parent / "legacy"
    (work / "base-recibida").mkdir(parents=True, exist_ok=True)
    (work / "base-generada" / "con-filtros").mkdir(parents=True, exist_ok=True)
    (work / "base-generada" / "sin-filtros").mkdir(parents=True, exist_ok=True)
    shutil.copy2(arguments.input, work / "base-recibida" / "base.csv")
    base_generator.__file__ = str(work / "procesos" / "base_generator.py")

    try:
        base_generator.procesar_base()
        base_generator.procesar_base_completa()
        extraer_telefonos(
            carpeta_generada=work / "base-generada" / "con-filtros",
            nombre_base="base_bancor",
        )
        extraer_telefonos(
            carpeta_generada=work / "base-generada" / "sin-filtros",
            nombre_base="BANCOR_ROMAN",
            formato_fecha="%Y%m%d",
            prefijo_salida="BANCOR_E1KIA",
            sufijo_salida="sinestrategia",
            columnas_salida_snake_case=True,
        )
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1

    for subdir in ("con-filtros", "sin-filtros"):
        source = work / "base-generada" / subdir
        target = output_dir / subdir
        target.mkdir(parents=True, exist_ok=True)
        for item in source.glob("*"):
            if item.is_file():
                shutil.copy2(item, target / item.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

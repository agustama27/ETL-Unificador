"""Unifier-owned CLI for the ClaroUY base ETL (back-base).

Mirrors the exact legacy ``main()`` chain — ``procesar_base`` →
``deduplicar_por_telefonos`` → dated dedup CSV → ``extraer_telefonos`` —
against sandbox-rooted folders, fail-fast, publishing the two contract
artifacts into the run ``output/`` directory.
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="ClaroUY base (unified)")
    parser.add_argument("--input", required=True, help="Raw ClaroUY clients CSV")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    root = Path.cwd() / "soho-clarouy-encuestas-etl" / "back-base"
    sys.path.insert(0, str(root / "procesos"))
    from base_generator import deduplicar_por_telefonos, procesar_base
    from phone_extractor import buscar_base_generada, extraer_telefonos

    output_dir = Path(arguments.output_dir)
    work = output_dir.parent / "legacy"
    entrada = work / "base-recibida"
    salida = work / "salida"
    entrada.mkdir(parents=True, exist_ok=True)
    salida.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arguments.input, entrada / "base.csv")

    try:
        base = procesar_base(entrada, salida)
        dedup = deduplicar_por_telefonos(base, salida / "backup")
        fecha = datetime.today().strftime("%d%m%Y")
        base_csv = salida / f"base_clarouy_{fecha}.csv"
        dedup.to_csv(base_csv, sep=";", decimal=",", encoding="utf-8",
                     index=False, na_rep="")
        encontrado = buscar_base_generada(salida)
        if encontrado is None:
            raise FileNotFoundError("no se encontro la base generada para extraer telefonos")
        extraer_telefonos(encontrado, salida / f"telefonos_x_cliente_{fecha}.csv")
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1

    for pattern in (f"base_clarouy_{fecha}.csv", f"telefonos_x_cliente_{fecha}.csv"):
        shutil.copy2(salida / pattern, output_dir / pattern)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Unifier-owned CLI for the legacy MT Voice daily chain.

Spawned as a subprocess with the legacy MT repo as cwd. Mirrors the exact
``main.py`` chain — ``procesar_base`` then ``extraer_telefonos`` — but with
explicit input and output paths so no legacy autodetection is reachable and
every artifact lands in the run sandbox.
"""

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Naranja X MT Voice daily (unified)")
    parser.add_argument("--input", required=True, help="33-column pipe-delimited TXT")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd()))
    from procesos.base_generator import procesar_base
    from procesos.phone_extractor import extraer_telefonos

    try:
        roman = procesar_base(Path(arguments.input), Path(arguments.output_dir))
        print(f"  -> {roman}")
        e1kia = extraer_telefonos(roman, Path(arguments.output_dir))
        print(f"  -> {e1kia}")
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

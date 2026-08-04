"""Unifier-owned CLI for the Fravega base ETL (back-base).

``clean_base`` already takes explicit directories — this wrapper stages the
input into a sandbox-local folder, runs the exact legacy function fail-fast,
and writes the fixed-name output straight into the run ``output/`` directory.
"""

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fravega base (unified)")
    parser.add_argument("--input", required=True, help="Raw Fravega CSV")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd() / "back-base"))
    from procesos.clean_base import clean_base

    output_dir = Path(arguments.output_dir)
    work = output_dir.parent / "legacy" / "base_recibida"
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy2(arguments.input, work / "base.csv")

    try:
        clean_base(input_dir=str(work), output_dir=str(output_dir),
                   output_filename="fravega_base.csv")
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

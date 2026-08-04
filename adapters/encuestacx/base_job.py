"""Unifier-owned CLI for the Encuesta CX base ETL.

Spawned as a subprocess with the legacy repo as cwd. The legacy ``main.py``
takes no arguments and anchors every path to the repo, so this wrapper points
the shared config singleton at the staged input and the run sandbox before
running the exact legacy pipeline.
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Encuesta CX base (unified)")
    parser.add_argument("--input", required=True, help="Survey Excel file")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd() / "back-base"))
    from config import config

    output_dir = Path(arguments.output_dir)
    config.INPUT_FILE = Path(arguments.input)
    config.OUTPUT_DIR = output_dir
    config.OUTPUT_FILE = output_dir / "base_encuesta.csv"
    config.OUTPUT_FILE_E164 = output_dir / "base_encuesta_e164.csv"
    config.LOG_DIR = output_dir.parent / "logs"

    import main as legacy

    return legacy.main()


if __name__ == "__main__":
    raise SystemExit(main())

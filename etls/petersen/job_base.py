"""Unifier-owned CLI for the Petersen tabla integradora ETL (legacy_base).

The legacy ``etl.py`` already takes explicit ``--input``/``--output`` folders
and anchors nothing else, so this wrapper only translates the platform
contract (``--output_dir``) to the legacy argv and fails fast with a clean
message instead of a raw traceback.
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Petersen tabla integradora (unified)")
    parser.add_argument("--input", required=True, help="Carpeta con los archivos del dia")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd()))
    import etl as legacy

    sys.argv = ["etl.py", "--input", arguments.input, "--output", arguments.output_dir]
    try:
        legacy.main()
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Unifier-owned CLI for the CartaSur base ETL.

The legacy CLI defaults to the desktop GUI without ``--cli``, spells the
output flag ``--output-dir`` and reads leftover GUI settings from
``%LOCALAPPDATA%``. This wrapper skips all of that: it imports the public
``procesar_paths`` seam (explicit paths, no runtime-path resolution) and runs
the exact legacy pipeline fail-fast into the sandbox ``output/`` directory.
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="CartaSur base (unified)")
    parser.add_argument("--input", required=True, help="Base CartaSur (.xlsx/.xlsm/.csv)")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd() / "src"))
    from cartasur_etl.procesar_dia import procesar_paths

    try:
        result = procesar_paths(
            input_path=Path(arguments.input),
            output_dir=Path(arguments.output_dir),
            log_cb=print,
        )
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1
    if not result.ok:
        for issue in result.errors:
            print(f"Error: {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

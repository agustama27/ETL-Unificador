"""Unifier-owned CLI for the Social Learning base ETLs (Argentina and Chile).

``generate_base`` takes explicit input/output paths — this wrapper selects
the country module, derives the dated legacy filename inside the sandbox
``output/`` directory, and runs the exact legacy function fail-fast.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

PREFIXES = {"argentina": "SOCIAL_ARG_CARTERA", "chile": "SOCIAL_CHI_CARTERA"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Social Learning base (unified)")
    parser.add_argument("--country", required=True, choices=sorted(PREFIXES))
    parser.add_argument("--input", required=True, help="Raw cartera CSV")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    root = Path.cwd() / "soho-social-learning-etl" / f"base_{arguments.country}"
    sys.path.insert(0, str(root))
    from procesos.base_generator import generate_base

    date_str = datetime.now().strftime("%Y%m%d")
    output = Path(arguments.output_dir) / f"{PREFIXES[arguments.country]}_{date_str}.csv"
    try:
        generate_base(input_path=Path(arguments.input), output_path=output)
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

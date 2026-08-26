"""Unifier-owned CLI for the Alvarez Maquinarias cobranzas ETL.

The legacy ``main.py`` anchors ``inputs/<date>/`` and ``outputs/<date>/``
partitions to its own ``__file__`` and cannot write elsewhere. This wrapper
skips that partition layer entirely: it builds the public ``PipelineConfig``
with the four staged input paths and the sandbox ``output/`` directory, and
runs the exact legacy ``run_pipeline`` fail-fast.
"""

import argparse
import sys
from datetime import date
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Alvarez Maquinarias cobranzas (unified)")
    parser.add_argument("--input", required=True, help="Saldos generales (.xls o .csv)")
    parser.add_argument("--maquinarias", required=True, help="Maquinarias vendidas (.xlsx)")
    parser.add_argument("--servicios", required=True, help="Remitos de servicios (.xlsx)")
    parser.add_argument("--repuestos", required=True, help="Remitos de repuestos (.pdf)")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd()))
    from src.etl.config import PipelineConfig
    from src.etl.pipeline import run_pipeline

    today = date.today()
    config = PipelineConfig(
        saldos_generales_path=Path(arguments.input),
        maquinarias_path=Path(arguments.maquinarias),
        remitos_repuestos_path=Path(arguments.repuestos),
        remitos_servicios_path=Path(arguments.servicios),
        output_dir=Path(arguments.output_dir),
        reference_date=today,
        run_date=today,
        overwrite=False,
    )
    try:
        run_pipeline(config)
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

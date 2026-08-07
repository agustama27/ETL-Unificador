#!/usr/bin/env python3
"""ETL script to transform Naranja X Excel assignments into SOHO CSV format."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from back_base_etl.constants import OUTPUT_COLUMNS_ROMAN, OUTPUT_FILENAME_E1KIA, OUTPUT_FILENAME_PREFIX, OUTPUT_FILENAME_ROMAN
from back_base_etl.io import iter_planes_chunks, load_input, load_pagos, save_output
from back_base_etl.planes_pivot import pivot_planes
from back_base_etl.transformers import build_e1kia_output, sort_roman_rows, transform
from back_base_etl.update_estado import update_estado


LOGGER = logging.getLogger("etl_naranjax")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = SCRIPT_DIR / "archivo-recibido" / "NARANJAX_MA_BaseMensual.xlsx"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "base-generada"


def main() -> None:
    """Command-line entrypoint for the ETL process."""
    parser = argparse.ArgumentParser(description="Naranja X to SOHO ETL")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Path to input Excel file",
    )
    parser.add_argument(
        "--output_dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for CSV",
    )
    parser.add_argument(
        "--planes",
        required=False,
        help="Path to daily PLANES file (.xlsx)",
    )
    parser.add_argument(
        "--pagos",
        required=False,
        help="Path to daily PAGOS file (.csv)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    try:
        LOGGER.info("Starting ETL process")
        LOGGER.info("Loading input file: %s", args.input)
        df_base = load_input(args.input)

        df_planes_pivot = None
        if args.planes:
            LOGGER.info("Loading PLANES file: %s", args.planes)
            df_planes_pivot = pivot_planes(iter_planes_chunks(args.planes))
            LOGGER.info(
                "Processed PLANES rows=%s products=%s max_plans=%s",
                df_planes_pivot.attrs.get("input_plan_rows", 0),
                len(df_planes_pivot),
                df_planes_pivot.attrs.get("max_plans", 0),
            )
        else:
            LOGGER.warning("PLANES file not provided, monthly amounts will be used")

        df_pagos = None
        if args.pagos:
            LOGGER.info("Loading PAGOS file: %s", args.pagos)
            df_pagos = load_pagos(args.pagos)
        else:
            LOGGER.info("PAGOS file not provided")

        plan_columns = [] if df_planes_pivot is None else list(df_planes_pivot.attrs.get("plan_columns", []))

        df_estado = update_estado(df_base, df_planes_pivot, df_pagos=df_pagos, logger=LOGGER)

        LOGGER.info("Transforming %s rows", len(df_estado))
        is_roman_output = bool(args.planes)
        output_df = transform(
            df_estado,
            plan_columns=plan_columns,
            output_columns_base=OUTPUT_COLUMNS_ROMAN if is_roman_output else None,
            logger=LOGGER,
        )
        if is_roman_output:
            output_df = sort_roman_rows(output_df)

        LOGGER.info("Saving output CSV in: %s", args.output_dir)
        output_prefix = OUTPUT_FILENAME_ROMAN if is_roman_output else OUTPUT_FILENAME_PREFIX
        output_path = save_output(output_df, args.output_dir, prefix=output_prefix)
        e1kia_path = None
        if is_roman_output:
            e1kia_df = build_e1kia_output(output_df)
            e1kia_path = save_output(
                e1kia_df,
                args.output_dir,
                prefix=OUTPUT_FILENAME_E1KIA,
                date_format="%y%m%d",
                suffix="_sinestrategia.csv",
            )

        LOGGER.info(
            "ETL summary - total_rows=%s, rows_with_warning=%s, output_path=%s, e1kia_path=%s",
            output_df.attrs.get("total_rows", len(output_df)),
            output_df.attrs.get("rows_with_warning", 0),
            output_path,
            e1kia_path,
        )
    except Exception:
        LOGGER.exception("ETL process failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

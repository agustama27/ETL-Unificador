#!/usr/bin/env python3
"""CLI entrypoint for IA voz tipificaciones to PCT contract ETL."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.modelos import ConfigTipificaciones
from core.procesar_tipificaciones import procesar_tipificaciones

LOGGER = logging.getLogger("etl_tipificaciones_ia_voz_pct")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = SCRIPT_DIR / "roman"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "base-generada"


def _resolve_input_path(input_arg: str | None) -> Path:
    if input_arg:
        return Path(input_arg)

    DEFAULT_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates: list[Path] = []
    for extension in ("*.csv", "*.xlsx", "*.xls"):
        candidates.extend(path for path in DEFAULT_INPUT_DIR.glob(extension) if path.is_file())

    if not candidates:
        raise FileNotFoundError(
            "No input file provided and no input files found in default folder "
            f"'{DEFAULT_INPUT_DIR}'. Put a .csv/.xlsx/.xls file there or pass --input."
        )

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    selected = candidates[0]
    LOGGER.info("Using latest input file from roman/: %s", selected)
    return selected


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for ETL execution."""
    parser = argparse.ArgumentParser(description="Tipificaciones IA voz to PCT ETL")
    parser.add_argument(
        "--input",
        required=False,
        help=(
            "Path to source input file. If omitted, the latest .csv/.xlsx/.xls file "
            "from back-resultados/roman/ is used"
        ),
    )
    parser.add_argument(
        "--output_dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for generated PCT csv",
    )
    parser.add_argument(
        "--log_level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser


def main() -> None:
    """Run ETL flow end-to-end with explicit validation."""
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    try:
        input_path = _resolve_input_path(args.input)
        config = ConfigTipificaciones(
            output_dir=Path(args.output_dir),
        )
        resultado = procesar_tipificaciones(input_path, config, log_cb=None)
        if resultado.status != "success":
            raise RuntimeError("; ".join(resultado.errores) or "ETL process failed")

        LOGGER.info(
            "ETL summary - total_input_rows=%s, total_output_rows=%s, "
            "omitted_rows_total=%s, warning_count=%s, omitted_by_reason=%s, output_path=%s",
            resultado.total_input_rows,
            resultado.total_output_rows,
            resultado.omitted_rows_total,
            resultado.warning_count,
            resultado.omitted_by_reason,
            resultado.output_path,
        )
    except Exception:
        LOGGER.exception("ETL process failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

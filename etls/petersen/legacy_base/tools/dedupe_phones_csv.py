"""
Utility to deduplicate phone numbers across TEL columns in an existing output CSV.

Rules:
- Keep phone in the highest-priority TEL column (TEL1 > TEL2 > TEL3 > TEL4)
- If same phone appears in the same TEL column for multiple clients, keep the first row
- Remove all other occurrences (set cell to empty)

Usage (PowerShell):
  python tools\\dedupe_phones_csv.py --input data\\petersen\\tabla_integradora_20251218_003341.csv
  python tools\\dedupe_phones_csv.py --input <file.csv> --output <deduped.csv>
"""

import argparse
from pathlib import Path
import sys

import pandas as pd

# Ensure project root is in path
BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from lib.common.validations import dedupe_phone_columns


def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate phone numbers across TEL columns in a CSV")
    parser.add_argument("--input", required=True, help="Input CSV path (semicolon separated)")
    parser.add_argument("--output", required=False, help="Output CSV path (default: <input>_deduped.csv)")
    parser.add_argument("--sep", required=False, default=";", help="CSV separator (default: ';')")
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {in_path}")

    out_path = Path(args.output) if args.output else in_path.with_name(in_path.stem + "_deduped" + in_path.suffix)

    # Read as strings to avoid numeric coercion (e.g. 345... -> 3.45e+09)
    df = pd.read_csv(in_path, sep=args.sep, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    cleaned, stats = dedupe_phone_columns(df, phone_cols=["TEL1", "TEL2", "TEL3", "TEL4"])

    cleaned.to_csv(out_path, sep=args.sep, index=False, encoding="utf-8-sig")

    print("[OK] Archivo generado:", out_path)
    print("[INFO] Stats:", stats)


if __name__ == "__main__":
    main()



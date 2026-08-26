from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from cartasur_etl.config import ConfigError
from cartasur_etl.ingest import IngestError
from cartasur_etl.models import EtlConfig, InputFiles
from cartasur_etl.procesar_dia import procesar_dia
from cartasur_etl.runtime_paths import RuntimePathInputs, resolve_runtime_paths


def run(input_path: str | Path, output_dir: str | Path, config_path: str | Path | None = None, run_date: date | None = None, strict: bool = False) -> dict:
    out = Path(output_dir)
    result = procesar_dia(
        EtlConfig(out, out / ".logs", Path(config_path) if config_path else None, run_date, strict),
        InputFiles(Path(input_path)),
    )
    if not result.ok:
        raise SystemExit("; ".join(result.errors) or "ETL failed")
    return result.to_legacy_dict()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transform CartaSur Excel/CSV into SOHO dynamic variables CSV.")
    parser.add_argument("--input", default=None, help="Path to CartaSur .xlsx or semicolon-delimited .csv input")
    parser.add_argument("--output-dir", default=None, help="Directory where CSV and reports will be written")
    parser.add_argument("--log-dir", default=None, help="Optional log directory; defaults to ./logs")
    parser.add_argument("--config", default=None, help="Optional YAML config override")
    parser.add_argument("--run-date", default=None, help="Run date in YYYY-MM-DD; defaults to today")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero after report generation when validation errors exist")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    if argv and argv[0].endswith((".py", ".exe")):
        argv = argv[1:]
    if argv and "--cli" in argv:
        argv = [arg for arg in argv if arg != "--cli"]
    return main(argv)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        effective_date = date.fromisoformat(args.run_date) if args.run_date else None
        resolved = resolve_runtime_paths(RuntimePathInputs(args.input, args.output_dir, args.log_dir, args.config))
        if resolved.input_path is None:
            raise ValueError("Missing input path")
        etl_result = procesar_dia(
            EtlConfig(resolved.output_dir, resolved.log_dir, resolved.config_path, effective_date, args.strict),
            InputFiles(resolved.input_path),
            log_cb=print,
        )
        if not etl_result.ok:
            raise SystemExit("; ".join(etl_result.errors) or "ETL failed")
        result = etl_result.to_legacy_dict()
    except (ConfigError, IngestError, ValueError) as exc:
        parser.exit(2, f"cartasur-etl: {exc}\n")
    except SystemExit as exc:
        parser.exit(1, f"cartasur-etl: {exc}\n")

    paths = result["paths"]
    print(f"CSV: {paths['csv']}")
    print(f"E1KIA phone CSV: {paths['e1kia_csv']}")
    print(f"Validation report: {paths['validation_report_csv']}")
    print(f"Valid records: {result['valid_records']} | Issues: {result['issues']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

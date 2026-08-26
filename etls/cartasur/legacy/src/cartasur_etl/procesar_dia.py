from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from cartasur_etl.config import load_config
from cartasur_etl.export import write_outputs
from cartasur_etl.ingest import read_input
from cartasur_etl.models import EtlConfig, EtlResult, InputFiles
from cartasur_etl.normalize import normalize_customers
from cartasur_etl.runtime_paths import ResolvedPaths, ensure_runtime_dirs
from cartasur_etl.transform import group_customers
from cartasur_etl.validate import validate_records
from cartasur_etl.validators_archivos import validate_inputs

LogCallback = Callable[[str], None]


def procesar_dia(config: EtlConfig, archivos: InputFiles, log_cb: LogCallback | None = None) -> EtlResult:
    def log(line: str) -> None:
        if log_cb:
            log_cb(line)

    resolved = ResolvedPaths(archivos.raw_input, config.output_dir, config.log_dir, config.config_path)
    ensure_runtime_dirs(resolved)
    validation = validate_inputs(config, archivos)
    if not validation.ok:
        return EtlResult(False, 0, 0, errors=validation.errors)

    effective_run_date = config.run_date or date.today()
    log(f"Leyendo base: {archivos.raw_input}")
    cfg = load_config(config.config_path)
    rows = read_input(archivos.raw_input, cfg)
    log(f"Filas crudas leídas: {len(rows)}")
    grouped = group_customers(rows, cfg)
    log(f"Clientes agrupados por CUIL: {len(grouped)}")
    normalized = normalize_customers(grouped, cfg, effective_run_date)
    valid, issues = validate_records(normalized, cfg)
    log(f"Registros válidos: {len(valid)} | Incidencias: {len(issues)}")
    paths = write_outputs(valid, issues, config.output_dir, cfg, effective_run_date)
    if config.strict and any(issue.severity == "ERROR" for issue in issues):
        return EtlResult(False, len(valid), len(issues), paths, [f"Strict mode failed; validation errors found. Reports written to {paths['validation_report_csv']}"])
    log(f"CSV generado: {paths['csv']}")
    log(f"CSV teléfonos E1KIA generado: {paths['e1kia_csv']}")
    log(f"Reporte de validación: {paths['validation_report_csv']}")
    return EtlResult(True, len(valid), len(issues), paths)


def procesar_paths(input_path: str | Path, output_dir: str | Path, config_path: str | Path | None = None, run_date: date | None = None, strict: bool = False, log_cb: LogCallback | None = None) -> EtlResult:
    out = Path(output_dir)
    cfg = EtlConfig(output_dir=out, log_dir=out / ".logs", config_path=Path(config_path) if config_path else None, run_date=run_date, strict=strict)
    return procesar_dia(cfg, InputFiles(Path(input_path)), log_cb=log_cb)

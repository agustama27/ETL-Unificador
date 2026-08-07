from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
import shutil
from typing import Sequence

from procesos.logcall_consolidator import (
    build_output_filename,
    generate_consolidated_dataframe,
    get_consolidation_summary,
    write_consolidated_excel,
)


SUPPORTED_EXTENSION = ".csv"


@dataclass
class LuzProcessResult:
    run_root: Path
    roman_copied_files: list[Path]
    logcall_copied_files: list[Path]
    output_excel_path: Path
    log_file_path: Path
    total_output_rows: int
    summary: dict


def process_luz_files(
    roman_files: Sequence[str | Path],
    logcall_files: Sequence[str | Path],
    output_root: str | Path,
) -> LuzProcessResult:
    roman_paths = _validate_input_files(roman_files, "Roman")
    logcall_paths = _validate_input_files(logcall_files, "Logcall")

    output_root_path = Path(output_root).expanduser().resolve()
    run_root, roman_dir, logcall_dir, results_dir, logs_dir = _build_run_directories(output_root_path)
    logger, log_file_path = _build_logger(logs_dir)

    logger.info("Iniciando corrida de flujo luz")
    logger.info("Roman seleccionados: %s", len(roman_paths))
    logger.info("Logcall seleccionados: %s", len(logcall_paths))

    roman_copied_files = _copy_files_to_folder(roman_paths, roman_dir)
    logcall_copied_files = _copy_files_to_folder(logcall_paths, logcall_dir)

    consolidated_df = generate_consolidated_dataframe(roman_dir, logcall_dir)
    summary = get_consolidation_summary(roman_dir, logcall_dir)

    output_excel_path = results_dir / build_output_filename()
    write_consolidated_excel(consolidated_df, output_excel_path)

    logger.info("Archivo Excel generado: %s", output_excel_path)
    logger.info("Total de filas output: %s", len(consolidated_df))

    return LuzProcessResult(
        run_root=run_root,
        roman_copied_files=roman_copied_files,
        logcall_copied_files=logcall_copied_files,
        output_excel_path=output_excel_path,
        log_file_path=log_file_path,
        total_output_rows=len(consolidated_df),
        summary=summary,
    )


def _validate_input_files(files: Sequence[str | Path], label: str) -> list[Path]:
    if not files:
        raise ValueError(f"Debe seleccionar al menos un archivo {label}.")

    validated: list[Path] = []
    for raw_path in files:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"No existe el archivo {label}: {path}")
        if path.suffix.lower() != SUPPORTED_EXTENSION:
            raise ValueError(
                f"Archivo {label} no soportado: {path.name}. Solo se permite {SUPPORTED_EXTENSION}."
            )
        validated.append(path)

    return validated


def _build_run_directories(output_root: Path) -> tuple[Path, Path, Path, Path, Path]:
    now = datetime.now()
    date_folder = now.strftime("%d-%m-%Y")
    run_id = now.strftime("corrida_%H-%M-%S-%f")

    run_root = output_root / date_folder / run_id
    roman_dir = run_root / "entradas" / "roman"
    logcall_dir = run_root / "entradas" / "logcall"
    results_dir = run_root / "resultados"
    logs_dir = run_root / "logs"

    roman_dir.mkdir(parents=True, exist_ok=True)
    logcall_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    return run_root, roman_dir, logcall_dir, results_dir, logs_dir


def _copy_files_to_folder(files: Sequence[Path], destination: Path) -> list[Path]:
    copied_paths: list[Path] = []
    used_names: set[str] = set()

    for source_path in files:
        target_name = _build_non_colliding_name(source_path.name, used_names)
        target_path = destination / target_name
        shutil.copy2(source_path, target_path)
        copied_paths.append(target_path)

    return copied_paths


def _build_non_colliding_name(original_name: str, used_names: set[str]) -> str:
    candidate = original_name
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    counter = 2

    while candidate in used_names:
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1

    used_names.add(candidate)
    return candidate


def _build_logger(logs_dir: Path) -> tuple[logging.Logger, Path]:
    log_file_path = logs_dir / f"luz_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logger_name = f"luz_exe_{datetime.now().strftime('%H%M%S%f')}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    return logger, log_file_path

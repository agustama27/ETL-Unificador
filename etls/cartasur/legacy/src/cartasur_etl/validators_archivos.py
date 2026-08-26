from __future__ import annotations

import ctypes
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from cartasur_etl.config import load_config
from cartasur_etl.ingest import IngestError, read_input
from cartasur_etl.models import InputFiles
from cartasur_etl.runtime_paths import ResolvedPaths


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def validate_for_processing(paths: ResolvedPaths, check_preconditions: bool = True) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    if paths.input_path is None:
        errors.append("Seleccioná el archivo de base a procesar.")
    else:
        _validate_input_file(paths.input_path, errors, warnings)
    for label, folder in (("salida", paths.output_dir), ("logs", paths.log_dir)):
        _validate_writable_dir(folder, label, errors)
    if paths.config_path is not None and not paths.config_path.exists():
        errors.append(f"La configuración YAML no existe: {paths.config_path}")
    if check_preconditions and not errors and paths.input_path is not None:
        try:
            cfg = load_config(paths.config_path)
            read_input(paths.input_path, cfg)
        except (IngestError, ValueError, OSError) as exc:
            errors.append(f"La base no cumple las precondiciones del ETL: {exc}")
    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def validate_inputs(config, archivos: InputFiles) -> ValidationResult:
    from cartasur_etl.runtime_paths import ResolvedPaths

    return validate_for_processing(
        ResolvedPaths(archivos.raw_input, config.output_dir, config.log_dir, config.config_path),
        check_preconditions=True,
    )


def _validate_input_file(path: Path, errors: list[str], warnings: list[str]) -> None:
    if not path.exists():
        errors.append(f"El archivo no existe: {path}")
        return
    if path.suffix.lower() not in {".xlsx", ".xlsm", ".csv"}:
        errors.append("El archivo debe ser .xlsx, .xlsm o .csv.")
    if _is_onedrive_placeholder(path):
        errors.append("El archivo parece estar solo en la nube. Abrilo o marcá 'Siempre conservar en este dispositivo'.")
    try:
        with path.open("rb") as fh:
            fh.read(1)
    except OSError as exc:
        errors.append(f"No se puede leer el archivo. Cerralo en Excel o verificá permisos: {exc}")
    if _looks_locked(path):
        warnings.append("No se pudo confirmar acceso exclusivo; si el proceso falla, cerrá Excel y reintentá.")


def _validate_writable_dir(path: Path, label: str, errors: list[str]) -> None:
    if not path.exists() or not path.is_dir():
        errors.append(f"La carpeta de {label} no existe: {path}")
        return
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix="cartasur_write_", delete=True):
            pass
    except OSError as exc:
        errors.append(f"La carpeta de {label} no es escribible: {path} ({exc})")


def _is_onedrive_placeholder(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    except Exception:
        return False
    if attrs == -1:
        return False
    offline = 0x1000
    recall_on_open = 0x40000
    recall_on_data_access = 0x400000
    return bool(attrs & (offline | recall_on_open | recall_on_data_access))


def _looks_locked(path: Path) -> bool:
    if os.name != "nt" or not path.exists():
        return False
    try:
        os.rename(path, path)
        return False
    except OSError:
        return True

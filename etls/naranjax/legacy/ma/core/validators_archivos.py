from __future__ import annotations

import ctypes
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path


MENSAJE_NO_ENCONTRADO = "El archivo no fue encontrado"
MENSAJE_ONEDRIVE = (
    "El archivo esta en la nube y no se puede leer todavia. Para descargarlo: "
    "abri el Explorador de Windows -> navega hasta el archivo -> hace clic derecho -> "
    "seleciona 'Mantener siempre en este dispositivo'. Espera a que aparezca el tilde verde "
    "y volve a intentarlo. Para evitar este problema en el futuro, podes hacer lo mismo sobre "
    "toda la carpeta donde recibis los archivos."
)
MENSAJE_EXTENSION = "El formato del archivo no es el esperado"
MENSAJE_LOCK = "El archivo esta siendo usado por otro programa. Cerralo e intenta de nuevo"
MENSAJE_CSV_INVALIDO = "El archivo PAGOS no se puede leer como CSV valido"

_RECALL_ON_OPEN = 0x00040000
_RECALL_ON_DATA_ACCESS = 0x00400000
_INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str


def _is_onedrive_placeholder(path: Path) -> bool:
    if sys.platform != "win32":
        return False
    attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if attrs == _INVALID_FILE_ATTRIBUTES:
        return False
    return bool(attrs & (_RECALL_ON_OPEN | _RECALL_ON_DATA_ACCESS))


def _is_locked(path: Path) -> bool:
    try:
        with path.open("rb+"):
            return False
    except PermissionError:
        return True
    except OSError:
        return False


def validar_archivo(path: Path, extensiones_permitidas: tuple[str, ...]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if not path.exists():
        issues.append(ValidationIssue(code="MISSING", message=MENSAJE_NO_ENCONTRADO))
        return issues

    if path.suffix.lower() not in extensiones_permitidas:
        issues.append(ValidationIssue(code="EXTENSION", message=MENSAJE_EXTENSION))

    if _is_onedrive_placeholder(path):
        issues.append(ValidationIssue(code="ONEDRIVE_PLACEHOLDER", message=MENSAJE_ONEDRIVE))

    if _is_locked(path):
        issues.append(ValidationIssue(code="LOCKED", message=MENSAJE_LOCK))

    return issues


def validar_estado_mensual(estado_dir: Path, mes: str) -> list[ValidationIssue]:
    estado_path = estado_dir / f"estado_{mes}.csv"
    if estado_path.exists():
        return []
    return [
        ValidationIssue(
            code="STATE_MISSING",
            message=f"No hay estado mensual para {mes[:4]}-{mes[4:6]}. Es la primera ejecucion del mes?",
        )
    ]


def aggregate_messages(issues: list[ValidationIssue]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        if issue.message in seen:
            continue
        seen.add(issue.message)
        deduped.append(issue.message)
    return deduped


def validar_csv_basico(path: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(4096)
            fh.seek(0)
            if not sample.strip():
                issues.append(ValidationIssue(code="CSV_INVALID", message=MENSAJE_CSV_INVALIDO))
                return issues

            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;")
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ";" if sample.count(";") >= sample.count(",") else ","

            reader = csv.reader(fh, delimiter=delimiter)
            header = next(reader, None)
            if not header or all(not str(cell).strip() for cell in header):
                issues.append(ValidationIssue(code="CSV_INVALID", message=MENSAJE_CSV_INVALIDO))
                return issues
    except (OSError, UnicodeDecodeError, csv.Error):
        issues.append(ValidationIssue(code="CSV_INVALID", message=MENSAJE_CSV_INVALIDO))
    return issues

"""Log persistence and redaction of secrets and host paths.

El ``Redactor`` enmascara secretos declarados y rutas absolutas del host. **NO
enmascara datos personales del negocio** (DNI, teléfonos, montos): los artefactos
y logs pueden contener PII y ``var/`` debe tratarse como material sensible, con
la política de retención de la API activa (``ETL_RETENTION_DAYS``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


REDACTED = "[REDACTED]"
HOST_PATH = "[HOST_PATH]"
_ABSOLUTE_PATH = re.compile(r"(?<![\w:/])(?:\"(?:[A-Za-z]:[\\/]|[\\/]{2}|/)[^\"\r\n]+\"|'(?:[A-Za-z]:[\\/]|[\\/]{2}|/)[^'\r\n]+'|(?:[A-Za-z]:[\\/]|[\\/]{2}|/)(?!/)[^\s\"'<>|]+)")


class Redactor:
    def __init__(self, secret_values: Iterable[str] = (), host_paths: Iterable[object] = ()) -> None:
        self._secrets = tuple(sorted(filter(None, secret_values), key=len, reverse=True))
        paths = (str(path) for path in host_paths if path)
        self._paths = tuple(sorted({form for path in paths for form in (path, path.replace("\\", "/"))}, key=len, reverse=True))

    def __call__(self, value: str) -> str:
        for secret in self._secrets:
            value = value.replace(secret, REDACTED)
        for path in self._paths:
            value = value.replace(path, HOST_PATH)
        return _ABSOLUTE_PATH.sub(HOST_PATH, value) if self._paths else value

    def redact_values(self, values: Iterable[str]) -> tuple[str, ...]:
        return tuple(self(value) for value in values)


def _write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def persist_logs(
    directory: Path,
    stdout: str,
    stderr: str,
    legacy_logs: Iterable[Path] = (),
    secret_values: Iterable[str] = (),
    host_paths: Iterable[object] = (),
) -> tuple[Path, ...]:
    directory.mkdir(parents=True, exist_ok=True)
    redact = Redactor(secret_values, host_paths)
    evidence = [(Path("stdout.log"), stdout), (Path("stderr.log"), stderr)]
    evidence.extend(
        (Path(f"legacy-{source.name}"), source.read_text(encoding="utf-8", errors="replace"))
        for source in sorted(legacy_logs, key=lambda path: path.name)
    )
    for relative, content in evidence:
        _write(directory / relative, redact(content))
    return tuple(relative for relative, _ in evidence)

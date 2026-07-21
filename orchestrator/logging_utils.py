from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


REDACTED = "[REDACTED]"


class Redactor:
    def __init__(self, secret_values: Iterable[str] = ()) -> None:
        self._secrets = tuple(sorted(filter(None, secret_values), key=len, reverse=True))

    def __call__(self, value: str) -> str:
        for secret in self._secrets:
            value = value.replace(secret, REDACTED)
        return value

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
) -> tuple[Path, ...]:
    directory.mkdir(parents=True, exist_ok=True)
    redact = Redactor(secret_values)
    evidence = [(Path("stdout.log"), stdout), (Path("stderr.log"), stderr)]
    evidence.extend(
        (Path(f"legacy-{source.name}"), source.read_text(encoding="utf-8", errors="replace"))
        for source in sorted(legacy_logs, key=lambda path: path.name)
    )
    for relative, content in evidence:
        _write(directory / relative, redact(content))
    return tuple(relative for relative, _ in evidence)

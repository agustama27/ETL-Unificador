from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from cartasur_etl.config_store import PROJECT_ENV_PREFIX, SavedSettings, load_settings


@dataclass(frozen=True)
class RuntimePathInputs:
    input_path: str | None = None
    output_dir: str | None = None
    log_dir: str | None = None
    config_path: str | None = None


@dataclass(frozen=True)
class ResolvedPaths:
    input_path: Path | None
    output_dir: Path
    log_dir: Path
    config_path: Path | None


def resolve_runtime_paths(explicit: RuntimePathInputs | None = None, settings: SavedSettings | None = None) -> ResolvedPaths:
    explicit = explicit or RuntimePathInputs()
    settings = settings or load_settings()
    cwd = Path.cwd()
    return ResolvedPaths(
        input_path=_optional_path(_pick(explicit.input_path, _env("INPUT"), settings.input_path, "")),
        output_dir=_path(_pick(explicit.output_dir, _env("OUTPUT_DIR"), settings.output_dir, str(cwd / "out"))),
        log_dir=_path(_pick(explicit.log_dir, _env("LOG_DIR"), settings.log_dir, str(cwd / "logs"))),
        config_path=_optional_path(_pick(explicit.config_path, _env("CONFIG"), settings.config_path, "")),
    )


def ensure_runtime_dirs(paths: ResolvedPaths) -> None:
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.log_dir.mkdir(parents=True, exist_ok=True)


def _env(name: str) -> str | None:
    return os.environ.get(f"{PROJECT_ENV_PREFIX}_{name}")


def _pick(*values: str | None) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value)
    return ""


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _optional_path(value: str) -> Path | None:
    return _path(value) if value else None

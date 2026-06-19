from __future__ import annotations

import os
from pathlib import Path

# Kept for dev scripts that import it explicitly — never used as a runtime fallback.
DEFAULT_DEV_PERSISTENCE_DIR = Path(r"C:\Users\agustin.tamagusuku\OneDrive - EVOLTIS\NARANJAX_MA_PERSISTENCIA")


def _clean(value: str | None) -> str:
    return value.strip() if value else ""


def _path_from(value: str | None) -> Path | None:
    cleaned = _clean(value)
    return Path(cleaned).expanduser() if cleaned else None


def _resolve_explicit_or_env(explicit: str | None, env_key: str, legacy_env_key: str | None = None) -> Path | None:
    explicit_path = _path_from(explicit)
    if explicit_path is not None:
        return explicit_path

    env_specific = _path_from(os.getenv(env_key))
    if env_specific is not None:
        return env_specific

    if legacy_env_key:
        legacy_env = _path_from(os.getenv(legacy_env_key))
        if legacy_env is not None:
            return legacy_env

    env_base = _path_from(os.getenv("NARANJAX_RUNTIME_BASE_DIR"))
    if env_base is not None:
        return env_base

    return None


def resolve_estado_dir(configured_estado_dir: str | None = None, explicit_estado_dir: str | None = None) -> Path | None:
    resolved = _resolve_explicit_or_env(explicit_estado_dir, "NARANJAX_ESTADO_DIR")
    if resolved is not None:
        return resolved
    configured = _path_from(configured_estado_dir)
    return configured


def resolve_output_dir(configured_output_dir: str | None = None, explicit_output_dir: str | None = None) -> Path | None:
    resolved = _resolve_explicit_or_env(explicit_output_dir, "NARANJAX_OUTPUT_DIR", legacy_env_key="NARANJAX_DEV_OUTPUT_DIR")
    if resolved is not None:
        return resolved
    configured = _path_from(configured_output_dir)
    return configured

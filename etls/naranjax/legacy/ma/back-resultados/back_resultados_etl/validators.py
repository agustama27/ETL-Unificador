"""Validation helpers for hard-fail and warning-level rules."""

from __future__ import annotations

from .cleaners import to_clean_str
from .constants import REQUIRED_SOURCE_COLUMNS


def validate_required_columns(columns: list[str]) -> None:
    """Raise when required source columns are missing."""
    missing = [column for column in REQUIRED_SOURCE_COLUMNS if column not in columns]
    if missing:
        raise ValueError(
            "Missing required source columns: "
            f"{', '.join(missing)}. Expected at least: {', '.join(REQUIRED_SOURCE_COLUMNS)}"
        )


def validate_dni(dni: str) -> bool:
    """Return True when DNI is present after cleaning."""
    return bool(to_clean_str(dni))

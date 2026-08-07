from __future__ import annotations


def validate_required_columns(columns: list[str], required: list[str]) -> None:
    missing = [col for col in required if col not in columns]
    if missing:
        raise ValueError(f"Missing required source columns: {', '.join(missing)}")


def validate_dni(dni_clean: str) -> bool:
    return bool(dni_clean)

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when ETL configuration is invalid."""


REQUIRED_TOP_LEVEL = {"columns", "required_mappings", "output_columns", "phone", "date", "tramo", "name", "id_llamada"}
REQUIRED_PARAMETERS = {
    "phone.ambiguous_10_digit_policy",
    "phone.canonical_mobile_international",
    "phone.default_fixed_country_prefix",
    "phone.default_mobile_country_prefix",
    "phone.local_mobile_prefixes",
    "phone.preserve_existing_country_prefixes",
    "date.pre_mora_due_day",
    "date.mora_temprana_days_to_add",
    "date.exclude_weekdays",
    "tramo.pre_mora_min",
    "tramo.pre_mora_max",
    "tramo.mora_temprana_min",
    "tramo.mora_temprana_max",
    "tramo.out_of_scope_above",
    "id_llamada.strategy",
}


def default_config_path() -> Path:
    local = Path(__file__).resolve().parent / "config" / "default_mapping.yaml"
    if local.exists():
        return local
    # Fallback for unusual import loaders where __file__ is unavailable in the bundle.
    from importlib import resources

    return Path(str(resources.files("cartasur_etl").joinpath("config/default_mapping.yaml")))


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else default_config_path()
    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    missing_top = sorted(REQUIRED_TOP_LEVEL - set(config))
    if missing_top:
        raise ConfigError(f"Invalid config: missing top-level keys: {', '.join(missing_top)}")

    columns = config.get("columns") or {}
    required_mappings = config.get("required_mappings") or []
    missing_mappings = [key for key in required_mappings if not columns.get(key)]
    if missing_mappings:
        raise ConfigError(f"Invalid config: missing column mappings: {', '.join(missing_mappings)}")

    missing_params = [key for key in sorted(REQUIRED_PARAMETERS) if _get_nested(config, key) in (None, "")]
    if missing_params:
        raise ConfigError(f"Invalid config: missing parameters: {', '.join(missing_params)}")

    output_columns = config.get("output_columns") or []
    if not output_columns or len(output_columns) != len(set(output_columns)):
        raise ConfigError("Invalid config: output_columns must be a non-empty list without duplicates")

    ambiguous_policy = config.get("phone", {}).get("ambiguous_10_digit_policy")
    if ambiguous_policy not in {"fixed", "keep", "unknown"}:
        raise ConfigError("Invalid config: phone.ambiguous_10_digit_policy must be one of: fixed, keep, unknown")


def _get_nested(config: dict[str, Any], dotted_key: str) -> Any:
    current: Any = config
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current

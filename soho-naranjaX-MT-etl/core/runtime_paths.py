import os
from pathlib import Path

from core.config_store import load_config
from core.modelos import ConfigDia


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_estado_dir(cli_value: str | None = None) -> Path:
    if cli_value:
        return Path(cli_value)
    env = os.getenv("NARANJAX_MT_ESTADO_DIR")
    if env:
        return Path(env)
    base = os.getenv("NARANJAX_MT_RUNTIME_BASE_DIR")
    if base:
        return Path(base) / "estado"
    cfg = load_config()
    if cfg.get("carpeta_estado"):
        return Path(cfg["carpeta_estado"])
    return _project_root() / "estado"


def resolve_output_dir(cli_value: str | None = None) -> Path:
    if cli_value:
        return Path(cli_value)
    env = os.getenv("NARANJAX_MT_OUTPUT_DIR")
    if env:
        return Path(env)
    base = os.getenv("NARANJAX_MT_RUNTIME_BASE_DIR")
    if base:
        return Path(base) / "output"
    cfg = load_config()
    if cfg.get("carpeta_salida"):
        return Path(cfg["carpeta_salida"])
    return _project_root() / "base_procesada"


def build_config(estado_cli: str | None = None, salida_cli: str | None = None) -> ConfigDia:
    estado_dir = resolve_estado_dir(estado_cli)
    output_dir = resolve_output_dir(salida_cli)
    logs_dir = output_dir / "logs"
    procesados_dir = output_dir / "procesados"
    return ConfigDia(
        estado_dir=estado_dir,
        output_dir=output_dir,
        logs_dir=logs_dir,
        procesados_dir=procesados_dir,
    )

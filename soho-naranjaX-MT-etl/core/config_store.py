import json
from pathlib import Path


APP_DIR_NAME = "soho-naranjax-mt-etl"


def _config_path() -> Path:
    base = Path.home() / ".config" / APP_DIR_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.json"


def load_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: dict) -> None:
    path = _config_path()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

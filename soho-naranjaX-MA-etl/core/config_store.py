from __future__ import annotations

import json
import os
from pathlib import Path


def config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else (Path.home() / ".config")
    return base / "NaranjaXETL" / "config.json"


def load_config() -> dict[str, str]:
    path = config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(values: dict[str, str]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8")


def remove_config_key(key: str) -> None:
    current = load_config()
    if key not in current:
        return
    current.pop(key, None)
    save_config(current)

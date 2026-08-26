from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

APP_NAME = "CartaSur ETL"
PROJECT_ENV_PREFIX = "CARTASUR_ETL"


@dataclass(frozen=True)
class SavedSettings:
    input_path: str = ""
    output_dir: str = ""
    log_dir: str = ""
    config_path: str = ""


def default_settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "CartaSurETL" / "settings.json"


def load_settings(path: str | Path | None = None) -> SavedSettings:
    settings_path = Path(path) if path else default_settings_path()
    if not settings_path.exists():
        return SavedSettings()
    try:
        data: dict[str, Any] = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return SavedSettings()
    return SavedSettings(**{field: str(data.get(field) or "") for field in SavedSettings.__dataclass_fields__})


def save_settings(settings: SavedSettings, path: str | Path | None = None) -> Path:
    settings_path = Path(path) if path else default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return settings_path

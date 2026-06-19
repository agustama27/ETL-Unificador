from __future__ import annotations

import sys
from pathlib import Path


def get_project_root() -> Path:
    """
    Devuelve la carpeta raíz de trabajo.

    - En modo ejecutable (PyInstaller): carpeta donde vive el .exe.
    - En modo script: raíz del proyecto (padre de `procesos/`).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

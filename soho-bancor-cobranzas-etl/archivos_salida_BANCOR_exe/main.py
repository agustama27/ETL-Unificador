"""Punto de entrada para la app ROMAN-only de salida Bancor."""

from pathlib import Path
import sys


def _asegurar_ruta_local() -> None:
    """Agrega la carpeta del proyecto al sys.path si falta."""
    base_dir = Path(__file__).resolve().parent
    base_dir_str = str(base_dir)
    if base_dir_str not in sys.path:
        sys.path.insert(0, base_dir_str)


_asegurar_ruta_local()
from ui.app import ejecutar_app


if __name__ == "__main__":
    ejecutar_app()

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACK_BASE_DIR = ROOT_DIR / "back-base"
if str(BACK_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BACK_BASE_DIR))

from back_base_etl.estado_persistente import inicializar_estado
from back_base_etl.io import load_input


def generar_estado_inicial(estado_dir: Path, input_base: Path, mes: str) -> Path:
    df_base = load_input(str(input_base))
    estado_path = inicializar_estado(df_base, str(estado_dir), mes)
    return Path(estado_path)

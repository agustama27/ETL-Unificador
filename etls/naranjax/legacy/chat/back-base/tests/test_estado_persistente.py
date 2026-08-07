from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import pytest


BACK_BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_BASE_DIR))
from back_base_etl.estado_persistente import (  # noqa: E402
    cargar_estado,
    guardar_estado,
    inicializar_estado,
)


def test_inicializar_estado_crea_archivo_mensual(tmp_path: Path) -> None:
    df_base = pd.DataFrame([{"nroproducto": "1", "total_deuda": "1000"}])

    path_vigente = inicializar_estado(df_base, str(tmp_path), "202604")

    assert Path(path_vigente).name == "estado_202604.csv"
    assert Path(path_vigente).exists()


def test_cargar_estado_lee_estado_vigente(tmp_path: Path) -> None:
    df_base = pd.DataFrame([{"nroproducto": "100", "recupero": "NO"}])
    inicializar_estado(df_base, str(tmp_path), "202604")

    cargado = cargar_estado(str(tmp_path), "202604")

    assert list(cargado["nroproducto"]) == ["100"]
    assert list(cargado["recupero"]) == ["NO"]


def test_guardar_estado_crea_vigente_y_snapshot_inmutable(tmp_path: Path) -> None:
    df_estado = pd.DataFrame(
        [
            {"nroproducto": "2", "recupero": "NO", "tipo_pago": "PAGO_LINK"},
        ]
    )

    path_vigente, path_snapshot = guardar_estado(df_estado, str(tmp_path), "20260418")

    assert Path(path_vigente).name == "estado_202604.csv"
    assert Path(path_snapshot).name == "estado_20260418.csv"
    assert Path(path_vigente).exists()
    assert Path(path_snapshot).exists()

    with pytest.raises(FileExistsError, match="Snapshot diario inmutable ya existe"):
        guardar_estado(df_estado, str(tmp_path), "20260418")


def test_cargar_estado_inexistente_lanza_error_descriptivo(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Inicializa el mes con inicializar_estado"):
        cargar_estado(str(tmp_path), "202604")


def test_inicializar_estado_filtra_m90_puro_con_case_y_espacios(tmp_path: Path) -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "1001", "cajon": "m90", "ecosistema": "puro"},
            {"nroproducto": "1002", "cajon": " M90 ", "ecosistema": " PURO "},
            {"nroproducto": "1003", "cajon": "M60", "ecosistema": "PURO"},
            {"nroproducto": "1004", "cajon": "M90", "ecosistema": "ECO_B"},
            {"nroproducto": "1005", "cajon": "", "ecosistema": "PURO"},
        ]
    )

    inicializar_estado(df_base, str(tmp_path), "202604")
    estado = cargar_estado(str(tmp_path), "202604")

    assert list(estado["nroproducto"]) == ["1001", "1002"]

"""Regression tests for load_input header-based mapping and inicializar_estado guard."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from back_base_etl.constants import INPUT_COLUMN_ALIASES, INPUT_COLUMNS
from back_base_etl.estado_persistente import inicializar_estado
from back_base_etl.io import load_input


def _legacy_21_column_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dni": "20111222",
                "nombre_apellido": "Cliente Uno",
                "deuda_vencida_tc": "100",
                "deuda_vencida_nd": "50",
                "total_vencida": "150",
                "deuda_total_tc": "1000",
                "deuda_total_nd": "500",
                "total_deuda": "1500",
                "estrategia": "E1",
                "nroproducto": "P-100",
                "marca_plan": "NARANJA",
                "telefono1": "5491111111111",
                "telefono2": "5491111111112",
                "telefono3": "5491111111113",
                "telefono4": "5491111111114",
                "email1": "uno@example.com",
                "email2": "dos@example.com",
                "email3": "tres@example.com",
                "cajon": "M90",
                "ecosistema": "PURO",
                "asignacion": "MORA_AVANZADA",
            }
        ]
    )


def _shifted_23_column_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "DNI": "20999888",
                "NRO_DOC": "20999888",
                "NOMBRE": "Cliente Shifted",
                "DEUDA_VENCIDA_TC": "30",
                "DEUDA_VENCIDA_ND": "40",
                "TOTAL_VENCIDA": "70",
                "DEUDA_TOTAL_TC": "1000",
                "DEUDA_TOTAL_ND": "1500",
                "TOTAL_DEUDA": "2500",
                "ESTRATEGIA": "E1",
                "PRODUCTO": "P-200",
                "MARCA_PLAN": "NARANJA",
                "TELEFONO_1": "5492222222221",
                "TELEFONO_2": "5492222222222",
                "TELEFONO_3": "5492222222223",
                "TELEFONO_4": "5492222222224",
                "EMAIL_1": "shifted1@example.com",
                "EMAIL_2": "shifted2@example.com",
                "EMAIL_3": "shifted3@example.com",
                "EMAIL4": "extra4@example.com",
                "CAJON_ASIGNACION_CLIENTE": "M90",
                "ECOSISTEMA": "PURO",
                "ASIGNACION": "MORA_AVANZADA",
            }
        ]
    )


def _write_workbook(path: Path, df: pd.DataFrame, sheet_name: str = "Asignacion") -> Path:
    with pd.ExcelWriter(path, engine="openpyxl") as workbook:
        df.to_excel(workbook, sheet_name=sheet_name, index=False)
    return path


def test_load_input_legacy_21_column_format(tmp_path: Path) -> None:
    workbook_path = _write_workbook(tmp_path / "legacy.xlsx", _legacy_21_column_df())

    df = load_input(str(workbook_path))

    assert list(df.columns) == INPUT_COLUMNS
    row = df.iloc[0]
    assert str(row["dni"]) == "20111222"
    assert row["cajon"] == "M90"
    assert row["ecosistema"] == "PURO"
    assert row["asignacion"] == "MORA_AVANZADA"
    assert row["email3"] == "tres@example.com"


def test_load_input_shifted_23_columns_with_nombre_and_email4(tmp_path: Path) -> None:
    workbook_path = _write_workbook(
        tmp_path / "shifted.xlsx",
        _shifted_23_column_df(),
        sheet_name="ASIGNACION",
    )

    df = load_input(str(workbook_path))

    assert list(df.columns) == INPUT_COLUMNS
    row = df.iloc[0]
    # The whole point of the fix: cajon must contain M90, not the EMAIL4 leak.
    assert row["cajon"] == "M90"
    assert row["ecosistema"] == "PURO"
    assert row["nombre_apellido"] == "Cliente Shifted"
    assert str(row["dni"]) == "20999888"
    assert row["nroproducto"] == "P-200"
    # EMAIL4 in the source must NOT have leaked into any canonical column.
    assert "extra4@example.com" not in df.values.flatten().tolist()


def test_load_input_handles_accented_headers(tmp_path: Path) -> None:
    df_source = _legacy_21_column_df().rename(
        columns={
            "cajon": "Cajón",
            "asignacion": "Asignación",
            "estrategia": "Estrategía",
        }
    )
    workbook_path = _write_workbook(tmp_path / "accents.xlsx", df_source)

    df = load_input(str(workbook_path))

    row = df.iloc[0]
    assert row["cajon"] == "M90"
    assert row["asignacion"] == "MORA_AVANZADA"
    assert row["estrategia"] == "E1"


def test_load_input_missing_required_dni_raises_clear_error(tmp_path: Path) -> None:
    df_source = _legacy_21_column_df().drop(columns=["dni"])
    workbook_path = _write_workbook(tmp_path / "missing_dni.xlsx", df_source)

    with pytest.raises(ValueError) as exc_info:
        load_input(str(workbook_path))

    message = str(exc_info.value)
    assert "Unsupported base mensual format" in message
    assert "dni" in message
    assert "Available columns:" in message
    assert "nombre_apellido" in message or "ecosistema" in message
    assert any(alias in message for alias in INPUT_COLUMN_ALIASES["dni"])


def test_load_input_missing_optional_asignacion_returns_na_column(tmp_path: Path) -> None:
    df_source = _legacy_21_column_df().drop(columns=["asignacion"])
    workbook_path = _write_workbook(tmp_path / "no_asignacion.xlsx", df_source)

    df = load_input(str(workbook_path))

    assert "asignacion" in df.columns
    assert df["asignacion"].isna().all()
    assert df.iloc[0]["cajon"] == "M90"


def test_inicializar_estado_zero_row_guard_raises_when_no_m90_match(tmp_path: Path) -> None:
    df_base = pd.DataFrame(
        [
            {"nroproducto": "1", "cajon": "M30", "ecosistema": "PURO"},
            {"nroproducto": "2", "cajon": "M60", "ecosistema": "PURO"},
            {"nroproducto": "3", "cajon": "M30", "ecosistema": "ECO_B"},
        ]
    )

    with pytest.raises(ValueError) as exc_info:
        inicializar_estado(df_base, str(tmp_path), "202604")

    message = str(exc_info.value)
    assert "M90+PURO" in message
    assert "cajon" in message
    assert "ecosistema" in message
    assert "M30" in message
    assert "M60" in message

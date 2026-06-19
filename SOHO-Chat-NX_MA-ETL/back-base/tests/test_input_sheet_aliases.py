from __future__ import annotations

import pandas as pd
import pytest

from back_base_etl.constants import INPUT_COLUMNS
from back_base_etl.io import load_input


def _legacy_base_df() -> pd.DataFrame:
    data = {column: [f"v_{column}"] for column in INPUT_COLUMNS}
    return pd.DataFrame(data)


def _aliased_base_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "NOMBRE": ["Cliente X"],
            "DEUDA_TOTAL": ["2500"],
            "NRO_DOC": ["12345678"],
            "EMAIL4": ["extra@example.com"],
            "CAJON_ASIGNACION_CLIENTE": ["M90"],
            "DEUDA_VENCIDA_ND": ["40"],
            "TELEFONO_2": ["5491111111112"],
            "TELEFONO_1": ["5491111111111"],
            "MARCa_PLAN": ["NARANJA"],
            "DEUDA_VENCIDA_TC": ["30"],
            "TOTAL_VENCIDA": ["70"],
            "DEUDA_TOTAL_TC": ["1000"],
            "DEUDA_TOTAL_ND": ["1500"],
            "PRODUCTO": ["P-1"],
            "EMAIL_1": ["mail1@example.com"],
            "EMAIL_2": ["mail2@example.com"],
            "EMAIL_3": ["mail3@example.com"],
            "TELEFONO_3": ["5491111111113"],
            "TELEFONO_4": ["5491111111114"],
            "ECOSISTEMA": ["APP"],
            "ASIGNACION": ["MORA_AVANZADA"],
            "ESTRATEGIA": ["E1"],
        }
    )


def _write_input_workbook(path, sheet_name: str) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as workbook:
        _legacy_base_df().to_excel(workbook, sheet_name=sheet_name, index=False)


def test_load_input_supports_legacy_asignacion_sheet(tmp_path) -> None:
    workbook_path = tmp_path / "input_legacy.xlsx"
    _write_input_workbook(workbook_path, "Asignacion")

    df = load_input(str(workbook_path))

    assert list(df.columns)[0] == "dni"
    assert len(df) == 1


def test_load_input_supports_m90_sheet_pattern(tmp_path) -> None:
    workbook_path = tmp_path / "input_m90.xlsx"
    _write_input_workbook(workbook_path, "Asignación M90 - Mayo")

    df = load_input(str(workbook_path))

    assert list(df.columns)[0] == "dni"
    assert len(df) == 1


def test_load_input_maps_alias_headers_with_extra_columns(tmp_path) -> None:
    workbook_path = tmp_path / "input_aliases.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as workbook:
        _aliased_base_df().to_excel(workbook, sheet_name="Asignación M90 - Mayo (1)", index=False)

    df = load_input(str(workbook_path))

    assert list(df.columns) == INPUT_COLUMNS
    assert str(df.loc[0, "dni"]) == "12345678"
    assert df.loc[0, "nroproducto"] == "P-1"
    assert df.loc[0, "cajon"] == "M90"
    assert df.loc[0, "nombre_apellido"] == "Cliente X"


def test_load_input_raises_clear_error_without_matching_sheet(tmp_path) -> None:
    workbook_path = tmp_path / "input_invalid.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as workbook:
        _legacy_base_df().to_excel(workbook, sheet_name="Resumen", index=False)
        _legacy_base_df().to_excel(workbook, sheet_name="Hoja1", index=False)

    with pytest.raises(ValueError, match="Available sheets: Resumen, Hoja1") as exc:
        load_input(str(workbook_path))

    assert "Expected one of:" in str(exc.value)


def test_load_input_raises_clear_error_when_required_columns_missing(tmp_path) -> None:
    workbook_path = tmp_path / "input_missing_required.xlsx"
    source = _aliased_base_df().drop(columns=["NRO_DOC", "PRODUCTO", "CAJON_ASIGNACION_CLIENTE"])
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as workbook:
        source.to_excel(workbook, sheet_name="Asignacion", index=False)

    with pytest.raises(ValueError, match="Unsupported base mensual format") as exc:
        load_input(str(workbook_path))

    error = str(exc.value)
    assert "dni" in error
    assert "nroproducto" in error
    assert "cajon" in error
    assert "Available columns:" in error

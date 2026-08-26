from __future__ import annotations

import pandas as pd
import pytest

from cartasur_etl.config import ConfigError, load_config, validate_config
from cartasur_etl.ingest import IngestError, read_input, read_workbook


FIXTURE = "tests/fixtures/CabeceraconDatos.xlsx"


def test_load_default_config():
    cfg = load_config()
    assert cfg["columns"]["id_cuil"] == "CUIL"
    assert "id_llamada" in cfg["output_columns"]
    assert cfg["output_columns"][-1] == "txt_productos"


def test_invalid_config_reports_missing_mapping():
    cfg = load_config()
    del cfg["columns"]["id_cuil"]
    with pytest.raises(ConfigError, match="id_cuil"):
        validate_config(cfg)


def test_read_workbook_preserves_strings_and_classifies_rows():
    cfg = load_config()
    rows = read_workbook(FIXTURE, cfg)
    martinez = rows[rows["id_cuil"] == "27289872804"]
    assert martinez["tel_cliente"].iloc[0] == "1121743961"
    assert martinez["id_producto"].iloc[0] == "6590651"
    assert martinez["row_type"].tolist().count("LOAN") == 4
    assert martinez["row_type"].tolist().count("INSURANCE") == 1


def test_read_csv_preserves_excel_ingest_behavior(tmp_path):
    cfg = load_config()
    path = tmp_path / "input.csv"
    pd.DataFrame(
        [
            {
                "CUIL": " 27289872804 ",
                "NOMBRE APELLIDO": " MARTINEZ ANA ",
                "NRO DE DOCUMENTO": "28987280",
                "NRO DE PRODUCTO": " 6590651 ",
                "NRO DE CUOTA": "8",
                "SALDO EXIGIBLE": "224200",
                "DIAS DE MORA": "13",
                "CANTIDAD DE CUOTAS A VENCER": "5",
                "SEGURO DESCRIPCION": "",
                "IMPORTE A ABONAR POR SEGURO": "",
                "TELEFONO CLIENTE": " 1121743961 ",
            },
            {
                "CUIL": "27289872804",
                "NOMBRE APELLIDO": "MARTINEZ ANA",
                "NRO DE DOCUMENTO": "28987280",
                "NRO DE PRODUCTO": "",
                "NRO DE CUOTA": "",
                "SALDO EXIGIBLE": "",
                "DIAS DE MORA": "",
                "CANTIDAD DE CUOTAS A VENCER": "",
                "SEGURO DESCRIPCION": " SEGURO VIDA ",
                "IMPORTE A ABONAR POR SEGURO": "1200",
                "TELEFONO CLIENTE": "1121743961",
            },
        ]
    ).to_csv(path, sep=";", index=False, encoding="utf-8")

    rows = read_input(path, cfg)

    assert rows["source_row_number"].tolist() == [2, 3]
    assert rows["id_cuil"].tolist() == ["27289872804", "27289872804"]
    assert rows["id_producto"].tolist() == ["6590651", ""]
    assert rows["tel_cliente"].iloc[0] == "1121743961"
    assert rows["seguro_descripcion"].iloc[1] == "SEGURO VIDA"
    assert rows["row_type"].tolist() == ["LOAN", "INSURANCE"]


def test_read_csv_falls_back_to_windows_encoding(tmp_path):
    cfg = load_config()
    path = tmp_path / "windows.csv"
    pd.DataFrame(
        [
            {
                "CUIL": "27289872804",
                "NOMBRE APELLIDO": "MUÑOZ ANA",
                "NRO DE DOCUMENTO": "28987280",
                "NRO DE PRODUCTO": "6590651",
                "NRO DE CUOTA": "8",
                "SALDO EXIGIBLE": "224200",
                "DIAS DE MORA": "13",
                "CANTIDAD DE CUOTAS A VENCER": "5",
                "SEGURO DESCRIPCION": "",
                "IMPORTE A ABONAR POR SEGURO": "",
                "TELEFONO CLIENTE": "1121743961",
            }
        ]
    ).to_csv(path, sep=";", index=False, encoding="cp1252")

    rows = read_input(path, cfg)

    assert rows["customer_name"].iloc[0] == "MUÑOZ ANA"


def test_missing_required_column_reports_column(tmp_path):
    cfg = load_config()
    path = tmp_path / "missing.xlsx"
    pd.DataFrame({"CUIL": ["20123456789"]}).to_excel(path, index=False)
    with pytest.raises(IngestError, match="NOMBRE APELLIDO"):
        read_workbook(path, cfg)

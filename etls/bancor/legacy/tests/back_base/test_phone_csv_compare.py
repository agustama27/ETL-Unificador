import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def phone_csv_compare_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "back-base"
        / "procesos"
        / "phone_csv_compare.py"
    )
    spec = importlib.util.spec_from_file_location("phone_csv_compare", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def escribir_csv(path: Path, data: dict[str, list[str]]) -> None:
    df = pd.DataFrame(data)
    df.to_csv(path, sep=";", encoding="utf-8", index=False)


def test_limpiar_numero_normaliza_digitos(phone_csv_compare_module):
    assert phone_csv_compare_module.limpiar_numero(" (351) 204-3044 ") == "3512043044"
    assert phone_csv_compare_module.limpiar_numero("3512043044.0") == "3512043044"
    assert phone_csv_compare_module.limpiar_numero("nan") == ""
    assert phone_csv_compare_module.limpiar_numero(None) == ""


def test_expandir_equivalencias_prefijos_549_y_54(phone_csv_compare_module):
    assert phone_csv_compare_module.expandir_equivalencias("5493511234567") == {
        "5493511234567",
        "3511234567",
    }
    assert phone_csv_compare_module.expandir_equivalencias("543512222222") == {
        "543512222222",
        "3512222222",
    }


def test_detectar_faltantes_source_vs_target(phone_csv_compare_module, tmp_path):
    source_path = tmp_path / "source.csv"
    target_path = tmp_path / "target.csv"
    output_path = tmp_path / "faltantes.csv"

    escribir_csv(
        source_path,
        {
            "NumeroCelular": [
                "5493511111111",
                "3512222222",
                "3513333333",
                "3513333333",
            ]
        },
    )
    escribir_csv(target_path, {"NumeroCelular": ["3511111111", "5493512222222"]})

    resultado = phone_csv_compare_module.main(
        [
            "--source",
            str(source_path),
            "--target",
            str(target_path),
            "--source-column",
            "NumeroCelular",
            "--target-column",
            "NumeroCelular",
            "--output",
            str(output_path),
        ]
    )

    assert resultado["faltantes_apariciones"] == 2
    assert resultado["faltantes_unicos"] == 1

    df_faltantes = pd.read_csv(output_path, sep=";")
    assert len(df_faltantes) == 1
    assert str(df_faltantes.loc[0, "numero_referencia"]) == "3513333333"
    assert int(df_faltantes.loc[0, "apariciones_source"]) == 2


def test_infiere_columnas_telefonicas_si_no_son_explicitas(phone_csv_compare_module, tmp_path):
    source_path = tmp_path / "source.csv"
    target_path = tmp_path / "target.csv"

    escribir_csv(source_path, {"Telefono contacto": ["5493519998888"], "Otro": ["x"]})
    escribir_csv(target_path, {"movil": ["3519998888"], "Extra": ["y"]})

    resultado = phone_csv_compare_module.main(
        [
            "--source",
            str(source_path),
            "--target",
            str(target_path),
        ]
    )

    assert resultado["source_apariciones"] == 1
    assert resultado["target_apariciones"] == 1
    assert resultado["faltantes_apariciones"] == 0


def test_usa_columnas_explicitas_en_cli(phone_csv_compare_module, tmp_path):
    source_path = tmp_path / "source.csv"
    target_path = tmp_path / "target.csv"

    escribir_csv(source_path, {"Principal": ["5493511230000"], "Aux": ["111"]})
    escribir_csv(target_path, {"Destino": ["3511230000"], "Aux2": ["222"]})

    resultado = phone_csv_compare_module.main(
        [
            "--source",
            str(source_path),
            "--target",
            str(target_path),
            "--source-column",
            "Principal",
            "--target-column",
            "Destino",
        ]
    )

    assert resultado["source_apariciones"] == 1
    assert resultado["target_apariciones"] == 1
    assert resultado["faltantes_apariciones"] == 0

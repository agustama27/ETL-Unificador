"""Contract tests for the ClaroUY base chain — first coverage for this repo."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "procesos"))

from base_generator import deduplicar_por_telefonos, procesar_base  # noqa: E402
from phone_extractor import buscar_base_generada, extraer_telefonos  # noqa: E402


def _write_input(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "clientes.csv").write_text(
        "telefono,nombre\n"
        "098123456,CLIENTE UNO\n"
        "098123457,CLIENTE DOS\n",
        encoding="utf-8",
    )


def test_chain_generates_dedup_base_and_phones(tmp_path: Path) -> None:
    entrada, salida = tmp_path / "in", tmp_path / "out"
    _write_input(entrada)
    salida.mkdir()

    df = procesar_base(entrada, salida)
    df = deduplicar_por_telefonos(df, salida / "backup")
    assert {"msisdn", "customer_id", "nombre_cliente"} <= set(df.columns)
    assert len(df) == 2

    base_csv = salida / "base_clarouy_test.csv"
    df.to_csv(base_csv, sep=";", index=False, encoding="utf-8")
    encontrado = buscar_base_generada(salida)
    assert encontrado is not None
    telefonos = salida / "telefonos_test.csv"
    cantidad = extraer_telefonos(encontrado, telefonos)
    assert telefonos.exists()
    assert cantidad >= 1


def test_procesar_base_fails_without_input(tmp_path: Path) -> None:
    vacia = tmp_path / "vacia"
    vacia.mkdir()

    with pytest.raises(FileNotFoundError):
        procesar_base(vacia, tmp_path / "out")

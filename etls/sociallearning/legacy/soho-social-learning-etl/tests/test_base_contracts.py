"""Contract tests for the Social Learning base generators (ARG + CHI).

First pytest coverage for this repo: pin the explicit-path seam, the
country-specific column contracts, and the derived output schema.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _generate(country: str, header: str, row: str, tmp_path: Path) -> Path:
    sys.path.insert(0, str(ROOT / country))
    try:
        from procesos.base_generator import generate_base  # noqa: PLC0415
        source = tmp_path / "in.csv"
        source.write_text(header + "\n" + row + "\n", encoding="utf-8")
        output = tmp_path / "out.csv"
        return generate_base(input_path=source, output_path=output)
    finally:
        sys.path.pop(0)
        sys.modules.pop("procesos.base_generator", None)
        sys.modules.pop("procesos", None)


def test_argentina_generates_cartera_schema(tmp_path: Path) -> None:
    result = _generate(
        "base_argentina",
        "APELLIDO,NOMBRE,DOCUMENTO,Monto Cuota,MONTO,% Descuento,Dias Mora",
        "PEREZ,JUAN,30111222,1000,5000,10,30",
        tmp_path,
    )

    text = result.read_text(encoding="utf-8-sig")
    header = text.splitlines()[0]
    assert header.startswith("customer_name,documento,monto,descuento,dias_mora")
    assert "JUAN PEREZ" in text and "900.00" in text


def test_chile_generates_cartera_schema(tmp_path: Path) -> None:
    result = _generate(
        "base_chile",
        "Apellido,Nombre,RUT,Monto Cuota,Monto,Dias Mora",
        "PEREZ,JUAN,12345678-9,1000,5000,30",
        tmp_path,
    )

    text = result.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0].startswith("customer_name,rut,monto,dias_mora")
    assert "JUAN PEREZ" in text


def test_argentina_fails_without_headers(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        _generate("base_argentina", "SIN,COLUMNAS", "x,y", tmp_path)

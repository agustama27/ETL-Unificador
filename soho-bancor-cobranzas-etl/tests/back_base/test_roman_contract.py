import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def base_generator_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "back-base"
        / "procesos"
        / "base_generator.py"
    )
    spec = importlib.util.spec_from_file_location("base_generator", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_construir_resumen_productos_formato_y_oferta(base_generator_module):
    grupo = pd.DataFrame(
        [
            {
                "AgrupadorProducto": "Prestamos Personales",
                "NumeroOperacion": "2",
                "MontoVencido": 100.0,
                "OFERTA_Importe": 0,
            },
            {
                "AgrupadorProducto": "Cuenta Corriente",
                "NumeroOperacion": "1",
                "MontoVencido": 200.5,
                "OFERTA_Importe": 50.25,
            },
        ]
    )

    resumen = base_generator_module.construir_resumen_productos(grupo)

    assert resumen.startswith("[")
    assert resumen.endswith("]")
    assert "OfertaImporte:NO" in resumen
    assert "OfertaImporte:50.25" in resumen
    assert resumen.count(" ; ") == 1


def test_validar_contrato_roman_ok(base_generator_module, capsys):
    salida = pd.DataFrame(
        [
            {
                "id_cuil": "1",
                "oferta_importe": "si",
                "monto_adeudado_ars": "100.0",
                "resumen_productos": "[A DeudaVencida:100.00 OfertaImporte:10.00]",
            },
            {
                "id_cuil": "2",
                "oferta_importe": "no",
                "monto_adeudado_ars": "50.0",
                "resumen_productos": "[B DeudaVencida:50.00 OfertaImporte:NO]",
            },
        ]
    )
    origen = pd.DataFrame(
        [
            {"CUIL": "1", "NumeroOperacion": "op1"},
            {"CUIL": "2", "NumeroOperacion": "op2"},
        ]
    )

    base_generator_module.validar_contrato_roman(salida, origen)
    out = capsys.readouterr().out
    assert "[VALIDACION ROMAN] OK" in out

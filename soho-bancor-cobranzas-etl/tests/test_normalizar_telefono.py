"""Tests unitarios para normalización de teléfonos."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from filtrosAplicados_base_BANCOR.procesos.pipeline_wfm import (
    _remover_prefijo_15,
    normalizar_telefono,
)


def _check(etiqueta, obtenido, esperado):
    marca = "OK " if obtenido == esperado else "FAIL"
    print(f"[{marca}] {etiqueta}: {obtenido!r} == {esperado!r}")
    return obtenido == esperado


def tests():
    resultados = []

    # _remover_prefijo_15: casos directos
    resultados.append(_check("remover_15 '0351151234567' (13: 0+area+15+local)", _remover_prefijo_15("0351151234567"), "3511234567"))
    resultados.append(_check("remover_15 '0351123456 (11 digits)'", _remover_prefijo_15("03511234567"), "3511234567"))
    resultados.append(_check("remover_15 '3511234567' (sin 0)", _remover_prefijo_15("3511234567"), "3511234567"))
    resultados.append(_check("remover_15 vacio", _remover_prefijo_15(""), ""))
    resultados.append(_check("remover_15 sin pattern '12345678901' (11)", _remover_prefijo_15("12345678901"), "12345678901"))
    resultados.append(_check("remover_15 14 digitos (basura)", _remover_prefijo_15("03511512345670"), "3511512345670"))

    # normalizar_telefono celular
    resultados.append(_check("cel 0351-15-1234567", normalizar_telefono("0351-15-1234567", "celular"), "5493511234567"))
    resultados.append(_check("cel 03511512345670 (14 digitos basura)", normalizar_telefono("03511512345670", "celular"), ""))
    resultados.append(_check("cel ya formado 5493511234567", normalizar_telefono("5493511234567", "celular"), "5493511234567"))
    resultados.append(_check("cel con 54 (no 549) 543511234567", normalizar_telefono("543511234567", "celular"), "5493511234567"))
    resultados.append(_check("cel con 9 local 93511234567", normalizar_telefono("93511234567", "celular"), "5493511234567"))
    resultados.append(_check("cel 3511234567 sin nada", normalizar_telefono("3511234567", "celular"), "5493511234567"))

    # normalizar_telefono fijo
    resultados.append(_check("fijo 0351-1234567", normalizar_telefono("0351-1234567", "fijo"), "543511234567"))
    resultados.append(_check("fijo 3516123456", normalizar_telefono("3516123456", "fijo"), "543516123456"))
    resultados.append(_check("fijo ya formado 543511234567", normalizar_telefono("543511234567", "fijo"), "543511234567"))
    resultados.append(_check("fijo CABA 01143215678", normalizar_telefono("01143215678", "fijo"), "541143215678"))

    # Casos borde
    resultados.append(_check("placeholder", normalizar_telefono("3519999999", "celular"), ""))
    resultados.append(_check("vacio string", normalizar_telefono("", "fijo"), ""))
    resultados.append(_check("nan", normalizar_telefono("nan", "celular"), ""))
    resultados.append(_check("basura cortita", normalizar_telefono("123", "fijo"), ""))
    resultados.append(_check("basura muy larga", normalizar_telefono("5491234567890123", "celular"), ""))
    resultados.append(_check("con espacios y guiones", normalizar_telefono(" 0351 - 15 - 1234567 ", "celular"), "5493511234567"))
    resultados.append(_check("sufijo .0 excel", normalizar_telefono("3511234567.0", "fijo"), "543511234567"))
    resultados.append(_check("prefijo 00 internacional", normalizar_telefono("005493511234567", "celular"), "5493511234567"))

    ok = sum(resultados)
    total = len(resultados)
    print(f"\nResultados: {ok}/{total} OK")
    return ok == total


if __name__ == "__main__":
    exito = tests()
    sys.exit(0 if exito else 1)

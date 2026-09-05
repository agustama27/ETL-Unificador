"""Carga de configuración JSON: el archivo aporta defaults, el entorno gana.

Esa precedencia es lo que mantiene intacto el fail-closed de la API: `config/dev.json`
no define `ETL_CONSOLE_TOKEN`, y aunque lo definiera, el token del cluster lo pisaría.
"""

import json

import pytest

from config_loader import SECCION_ENTORNO, cargar, sembrar_entorno


def _escribir(tmp_path, contenido):
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return ruta


def test_carga_un_objeto_json(tmp_path):
    ruta = _escribir(tmp_path, {"service": "api", SECCION_ENTORNO: {"A": "1"}})

    assert cargar(ruta) == {"service": "api", SECCION_ENTORNO: {"A": "1"}}


def test_falla_si_no_existe(tmp_path):
    """Fail-fast: arrancar con la config equivocada es peor que no arrancar."""
    with pytest.raises(FileNotFoundError):
        cargar(tmp_path / "ausente.json")


def test_rechaza_un_json_que_no_es_objeto(tmp_path):
    ruta = tmp_path / "lista.json"
    ruta.write_text("[1, 2]", encoding="utf-8")

    with pytest.raises(ValueError, match="objeto JSON"):
        cargar(ruta)


def test_siembra_las_ausentes(tmp_path):
    entorno = {}

    sembradas = sembrar_entorno({SECCION_ENTORNO: {"A": "1", "B": "2"}}, entorno)

    assert sembradas == ["A", "B"]
    assert entorno == {"A": "1", "B": "2"}


def test_no_pisa_lo_que_ya_esta_definido():
    """La regla que hace que el mismo JSON sirva en local y en el cluster."""
    entorno = {"A": "del-entorno"}

    sembradas = sembrar_entorno({SECCION_ENTORNO: {"A": "del-archivo", "B": "2"}}, entorno)

    assert sembradas == ["B"]
    assert entorno["A"] == "del-entorno"


def test_convierte_a_string_porque_el_entorno_solo_tiene_strings():
    entorno = {}

    sembrar_entorno({SECCION_ENTORNO: {"N": 30, "NADA": None}}, entorno)

    assert entorno == {"N": "30", "NADA": ""}


def test_una_config_sin_seccion_env_no_hace_nada():
    entorno = {"A": "1"}

    assert sembrar_entorno({"service": "api"}, entorno) == []
    assert entorno == {"A": "1"}


@pytest.mark.parametrize("nombre", ["local", "local-compose", "dev"])
def test_los_config_del_repo_son_validos(nombre):
    from orchestrator.workspace import workspace_root

    configuracion = cargar(workspace_root() / "config" / f"{nombre}.json")

    assert configuracion[SECCION_ENTORNO]["TZ"] == "America/Argentina/Buenos_Aires"


def test_dev_no_trae_el_token():
    """Si `dev.json` definiera el token, el fail-closed seria decorativo."""
    from orchestrator.workspace import workspace_root

    configuracion = cargar(workspace_root() / "config" / "dev.json")

    assert "ETL_CONSOLE_TOKEN" not in configuracion[SECCION_ENTORNO]
    assert "ETL_AUTH_DISABLED" not in configuracion[SECCION_ENTORNO]

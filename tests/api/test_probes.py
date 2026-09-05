"""Sondas de Kubernetes: liveness y readiness.

Contrato con el chart: `/health` dice si hay que reiniciar el pod, `/ready` dice si
hay que sacarlo de rotación. Ninguna de las dos pasa por el middleware de token,
que sólo cubre el prefijo `/api`.
"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestrator.workspace import workspace_root
from platform_api.main import create_app

WORKSPACE = workspace_root()


def _workspace(tmp_path: Path) -> Path:
    for manifest in WORKSPACE.glob("etls/*/manifest.yaml"):
        destino = tmp_path / manifest.relative_to(WORKSPACE)
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest, destino)
    return tmp_path


@pytest.fixture
def cliente(tmp_path):
    return TestClient(create_app(workspace=_workspace(tmp_path), token="secreto"))


def test_health_responde_sin_token(cliente):
    """Un probe con token seria un secreto mas para rotar en el chart, a cambio de nada."""
    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_ready_responde_sin_token_y_cuenta_los_etls(cliente):
    respuesta = cliente.get("/ready")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ready"
    assert cuerpo["etls"] > 0


def test_api_sigue_exigiendo_token(cliente):
    """Las sondas no aflojan el fail-closed del resto."""
    assert cliente.get("/api/catalog").status_code == 401


def test_ready_falla_si_el_catalogo_no_esta(tmp_path):
    """Sin `etls/` montado el servicio arranca igual: readiness lo saca de rotacion."""
    vacio = tmp_path / "sin-etls"
    (vacio / "etls").mkdir(parents=True)
    cliente = TestClient(create_app(workspace=vacio, token="secreto"))

    respuesta = cliente.get("/ready")

    assert respuesta.status_code == 503
    assert respuesta.json()["status"] == "unready"


def test_health_sigue_vivo_aunque_ready_falle(tmp_path):
    """La distincion que le importa a k8s: sin catalogo no hay que reiniciar, hay que esperar."""
    vacio = tmp_path / "sin-etls"
    (vacio / "etls").mkdir(parents=True)
    cliente = TestClient(create_app(workspace=vacio, token="secreto"))

    assert cliente.get("/health").status_code == 200
    assert cliente.get("/ready").status_code == 503

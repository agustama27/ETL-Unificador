"""El chart de Helm y el código tienen que seguir contándose la misma historia.

El acoplamiento no es obvio y no lo cubre ningún otro test: el `config.json` que el
chart proyecta como ConfigMap lo lee `config_loader`, las sondas del Deployment son
rutas que define `platform_api`, y el `terminationGracePeriodSeconds` tiene que
cubrir el `timeout_seconds` más largo del catálogo. Si alguna de las tres se mueve
de un solo lado, el pod arranca y falla en producción.

Se saltea si no hay `helm` en el PATH. **Un skip no es un pase**: en CI, helm está.
"""

import json
import shutil
import subprocess

import pytest
import yaml

from config_loader import SECCION_ENTORNO
from orchestrator.catalog import Catalog
from orchestrator.workspace import workspace_root

HELM = shutil.which("helm")
CHART = workspace_root() / "deploy" / "package"
SERVICIO = "etl-platform-api"

pytestmark = pytest.mark.skipif(HELM is None, reason="helm no esta en el PATH")


def _render(*overrides):
    argumentos = [HELM, "template", "etl", str(CHART)]
    for override in overrides:
        argumentos += ["--set", override]
    resultado = subprocess.run(argumentos, capture_output=True, text=True, timeout=120)
    assert resultado.returncode == 0, resultado.stderr
    return [d for d in yaml.safe_load_all(resultado.stdout) if d]


def _de_tipo(documentos, kind):
    return next(d for d in documentos if d["kind"] == kind)


@pytest.fixture(scope="module")
def documentos():
    return _render()


@pytest.fixture(scope="module")
def contenedor(documentos):
    return _de_tipo(documentos, "Deployment")["spec"]["template"]["spec"]["containers"][0]


def test_el_chart_lintea():
    resultado = subprocess.run([HELM, "lint", str(CHART)], capture_output=True, text=True,
                               timeout=120)

    assert resultado.returncode == 0, resultado.stdout


def test_el_configmap_tiene_la_forma_que_espera_el_loader(documentos):
    """`sembrar_entorno` lee la clave `env`. Si el chart la renombra, no siembra nada."""
    configuracion = json.loads(_de_tipo(documentos, "ConfigMap")["data"]["config.json"])

    assert SECCION_ENTORNO in configuracion
    assert configuracion[SECCION_ENTORNO]["TZ"] == "America/Argentina/Buenos_Aires"


def test_las_sondas_apuntan_a_rutas_que_existen(contenedor):
    rutas = {nombre: valor["httpGet"]["path"]
             for nombre, valor in contenedor.items() if nombre.endswith("Probe")}

    assert rutas == {"startupProbe": "/health",
                     "livenessProbe": "/health",
                     "readinessProbe": "/ready"}


@pytest.mark.parametrize("ruta", ["/health", "/ready"])
def test_las_sondas_viven_fuera_del_prefijo_autenticado(ruta):
    """El middleware de token cubre `/api`. Una sonda ahi adentro recibiria 401."""
    assert not ruta.startswith("/api")


def test_la_ventana_de_terminacion_cubre_el_etl_mas_largo(documentos):
    """Si no, un despliegue mata una corrida a la mitad y deja artefactos parciales."""
    raiz = workspace_root()
    timeouts = [d.timeout_seconds for d in Catalog.load_workspace(raiz)
                if d.timeout_seconds]
    gracia = _de_tipo(documentos, "Deployment")["spec"]["template"]["spec"][
        "terminationGracePeriodSeconds"]

    assert gracia > max(timeouts), (
        f"gracia {gracia}s no cubre el timeout mas largo del catalogo ({max(timeouts)}s)")


def test_una_sola_replica_y_sin_rolling_update(documentos):
    """Dos replicas no dan alta disponibilidad: los lock files de estado no coordinan."""
    especificacion = _de_tipo(documentos, "Deployment")["spec"]

    assert especificacion["replicas"] == 1
    assert especificacion["strategy"]["type"] == "Recreate"


def test_var_se_monta_desde_el_volumen_persistente(documentos, contenedor):
    assert "/app/var" in [m["mountPath"] for m in contenedor["volumeMounts"]]
    volumen = next(v for v in _de_tipo(documentos, "Deployment")["spec"]["template"]["spec"][
        "volumes"] if v["name"] == "var")
    assert "persistentVolumeClaim" in volumen
    assert _de_tipo(documentos, "PersistentVolumeClaim")["metadata"]["annotations"][
        "helm.sh/resource-policy"] == "keep"


def test_sin_persistencia_no_se_crea_el_pvc_y_var_es_efimero():
    documentos = _render(f"services.{SERVICIO}.persistence.enabled=false")
    volumen = next(v for v in _de_tipo(documentos, "Deployment")["spec"]["template"]["spec"][
        "volumes"] if v["name"] == "var")

    assert "PersistentVolumeClaim" not in [d["kind"] for d in documentos]
    assert volumen["emptyDir"] == {}


def test_sin_secret_la_api_queda_fail_closed():
    """No inventar un token por default: sin el, la API responde 503 y eso esta bien."""
    documentos = _render(f"services.{SERVICIO}.tokenSecret=null")
    entorno = [e["name"] for e in _de_tipo(documentos, "Deployment")["spec"]["template"][
        "spec"]["containers"][0]["env"]]

    assert "ETL_CONSOLE_TOKEN" not in entorno


def test_el_tamanio_del_volumen_es_obligatorio():
    resultado = subprocess.run(
        [HELM, "template", "etl", str(CHART), "--set", f"services.{SERVICIO}.persistence.size=null"],
        capture_output=True, text=True, timeout=120)

    assert resultado.returncode != 0

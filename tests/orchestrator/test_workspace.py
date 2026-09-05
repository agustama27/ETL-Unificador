"""Resolución de la raíz del workspace por marcador, no por conteo de niveles."""

import pytest

from orchestrator.workspace import MARCADORES, workspace_root


def _marcar(directorio):
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / "pyproject.toml").write_text("", encoding="utf-8")
    (directorio / "etls").mkdir(exist_ok=True)
    return directorio


def test_encuentra_la_raiz_desde_un_descendiente_profundo(tmp_path):
    raiz = _marcar(tmp_path / "repo")
    hondo = raiz / "apps" / "commons" / "orchestrator"
    hondo.mkdir(parents=True)

    assert workspace_root(hondo / "run.py") == raiz


def test_es_indiferente_a_la_profundidad(tmp_path):
    """La garantía que se perdía con `parents[n]`: mover el paquete no rompe nada."""
    raiz = _marcar(tmp_path / "repo")
    poco = raiz / "orchestrator"
    mucho = raiz / "apps" / "commons" / "orchestrator"
    poco.mkdir()
    mucho.mkdir(parents=True)

    assert workspace_root(poco / "run.py") == workspace_root(mucho / "run.py") == raiz


def test_la_propia_raiz_califica(tmp_path):
    raiz = _marcar(tmp_path / "repo")

    assert workspace_root(raiz) == raiz


def test_exige_todos_los_marcadores(tmp_path):
    """Un `pyproject.toml` suelto no alcanza: sin `etls/` no hay catálogo que cargar."""
    parcial = tmp_path / "repo"
    parcial.mkdir()
    (parcial / "pyproject.toml").write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="raiz del workspace"):
        workspace_root(parcial)


def test_falla_rapido_si_no_hay_raiz(tmp_path):
    """Fail-fast: un workspace mal resuelto escribe evidencia en el lugar equivocado."""
    with pytest.raises(RuntimeError, match="ningun ancestro"):
        workspace_root(tmp_path / "sin" / "marcadores")


def test_el_repositorio_real_se_resuelve_solo():
    raiz = workspace_root()

    assert all((raiz / m).exists() for m in MARCADORES)
    assert (raiz / "apps" / "commons" / "orchestrator" / "workspace.py").exists()

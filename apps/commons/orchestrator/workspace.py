"""Resolución de la raíz del workspace.

El núcleo necesita la raíz del repositorio para dos cosas: descubrir los
`manifest.yaml` bajo `etls/` y anclar `var/runs` y `var/state`.

Se resuelve buscando un marcador hacia arriba, no contando niveles con
``parents[n]``. Contar niveles ata el código a su profundidad en el árbol: la
adopción de ADR-ARC-002, que bajó los paquetes a ``apps/commons/``, rompió los
dos call sites que lo hacían y se llevó puestos 103 tests de una sola vez.
"""

from pathlib import Path

MARCADORES = ("pyproject.toml", "etls")


def workspace_root(start: Path | None = None) -> Path:
    """Primer ancestro que contiene todos los marcadores, incluido ``start``.

    Args:
        start: desde dónde subir. Por defecto, el directorio de este módulo.

    Raises:
        RuntimeError: si ningún ancestro califica. Es fail-fast a propósito: un
            workspace mal resuelto escribe evidencia de corridas en el lugar
            equivocado, y eso se descubre tarde.
    """
    origen = (start or Path(__file__)).resolve()
    for candidato in (origen, *origen.parents):
        if candidato.is_dir() and all((candidato / m).exists() for m in MARCADORES):
            return candidato
    raise RuntimeError(
        f"no se encontro la raiz del workspace desde {origen}: "
        f"ningun ancestro contiene {' y '.join(MARCADORES)}")

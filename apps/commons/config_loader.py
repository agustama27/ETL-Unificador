"""Carga de configuración JSON para entornos bajos (ADR-ARC-002 §config).

El contrato es deliberadamente angosto: el JSON aporta **defaults**, y el entorno
siempre gana. Eso mantiene intacta la semántica fail-closed de la API —sin
``ETL_CONSOLE_TOKEN`` en el entorno la API rechaza ``/api/*``— y hace que el
ConfigMap del chart de Helm y los ``config/*.json`` del repo sean la misma cosa
vista desde dos lados.

No reemplaza la configuración de runtime del cluster: los JSON de ``config/`` son
para desarrollo y pruebas, y no llevan secretos de producción.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Clave del JSON cuyo contenido se proyecta como variables de entorno.
SECCION_ENTORNO = "env"


def cargar(ruta: Path) -> dict[str, Any]:
    """Lee un archivo de configuración JSON.

    Raises:
        FileNotFoundError: si no existe. Es fail-fast: arrancar con la config
            equivocada es peor que no arrancar.
        ValueError: si el contenido no es un objeto JSON.
    """
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        raise ValueError(f"la configuracion debe ser un objeto JSON: {ruta}")
    return datos


def sembrar_entorno(configuracion: dict[str, Any],
                    entorno: dict[str, str] | None = None) -> list[str]:
    """Proyecta ``configuracion[SECCION_ENTORNO]`` como defaults del entorno.

    Una variable que ya está definida **no se pisa**: el entorno tiene prioridad
    sobre el archivo, que es lo que permite que el mismo JSON sirva en local y en
    el cluster sin que el chart tenga que reescribirlo.

    Returns:
        Los nombres efectivamente sembrados, en orden. Sirve para logear qué
        aportó el archivo y qué venía de afuera.
    """
    destino = os.environ if entorno is None else entorno
    sembradas = []
    for clave, valor in (configuracion.get(SECCION_ENTORNO) or {}).items():
        if clave in destino:
            continue
        destino[clave] = "" if valor is None else str(valor)
        sembradas.append(clave)
    return sembradas

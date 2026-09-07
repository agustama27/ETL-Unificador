"""Herramientas MCP sobre la API de la consola (ADR-001, Fase 5).

Funciones puras sobre un cliente httpx inyectado — el wiring MCP vive en
``platform_mcp.server``. Reciben cualquier cliente compatible (incluido el
``TestClient`` de la API), así el contrato se testea sin transporte.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any


class LocalPathsUnavailable(RuntimeError):
    """Se pidió cargar por ruta local contra un servidor que no ve ese disco.

    La salida NO es mandar el contenido como argumento de tool: esos argumentos
    son JSON que emite el modelo, y un modelo regenera los bytes en vez de
    copiarlos. Eso rompe la paridad byte a byte contra los upstream, que es la
    garantía central del sistema. Se usa `preparar_carga`.
    """


def _checked(response: Any) -> Any:
    if response.status_code >= 400:
        detail = response.json().get("detail", response.text)
        raise RuntimeError(f"API error {response.status_code}: {detail}")
    return response


def list_etls(client: Any) -> list[dict[str, Any]]:
    entries = _checked(client.get("/api/catalog")).json()
    return [
        {"id": entry["id"], "name": entry["name"], "client": entry["client"],
         "executable": entry["executable"], "reason": entry["reason"]}
        for entry in entries
    ]


def describe_etl(client: Any, etl_id: str) -> dict[str, Any]:
    entries = _checked(client.get("/api/catalog")).json()
    for entry in entries:
        if entry["id"] == etl_id:
            return entry
    raise RuntimeError(f"ETL desconocido: {etl_id}")


def preparar_carga(client: Any, etl_id: str) -> dict[str, Any]:
    """Emite un link de un solo uso para que una persona suelte los archivos."""
    return _checked(client.post("/api/uploads", data={"etl_id": etl_id})).json()


def estado_carga(client: Any, upload_id: str) -> dict[str, Any]:
    """Qué roles ya aterrizaron y cuáles faltan para poder lanzar."""
    return _checked(client.get(f"/api/uploads/{upload_id}")).json()


def run_etl(client: Any, etl_id: str, business_date: str,
            inputs: dict[str, str] | None = None,
            params: dict[str, Any] | None = None, *,
            upload_id: str | None = None,
            allow_local_paths: bool = True) -> dict[str, Any]:
    """Dispara una corrida, por upload_id o subiendo rutas locales.

    ``allow_local_paths`` lo fija el transporte: verdadero en stdio (el proceso
    corre en la máquina del usuario), falso sobre HTTP.
    """
    if upload_id and inputs:
        raise RuntimeError("Elegí un solo modo de carga: inputs o upload_id")
    if inputs and not allow_local_paths:
        raise LocalPathsUnavailable(
            "Este servidor no ve tu disco. Pedí un link con preparar_carga, "
            "pasáselo a la persona y volvé con el upload_id.")

    data = {"etl_id": etl_id, "business_date": business_date,
            "params": _json.dumps(params or {})}
    if upload_id:
        data["upload_id"] = upload_id
        return _checked(client.post("/api/runs", data=data)).json()

    files = {}
    for role, path in (inputs or {}).items():
        source = Path(path)
        files[role] = (source.name, source.read_bytes())
    return _checked(client.post("/api/runs", data=data, files=files)).json()


def get_run(client: Any, run_id: str) -> dict[str, Any]:
    return _checked(client.get(f"/api/runs/{run_id}")).json()


def download_artifact(client: Any, run_id: str, role: str, destination: str) -> str:
    response = _checked(client.get(f"/api/runs/{run_id}/artifacts/{role}"))
    target_dir = Path(destination)
    target_dir.mkdir(parents=True, exist_ok=True)
    disposition = response.headers.get("content-disposition", "")
    name = disposition.split("filename=")[-1].strip('"') if "filename=" in disposition else role
    target = target_dir / name
    target.write_bytes(response.content)
    return str(target)

"""Herramientas MCP sobre la API de la consola (ADR-001, Fase 5).

Funciones puras sobre un cliente httpx inyectado — el wiring MCP vive en
``platform_mcp.server``. Reciben cualquier cliente compatible (incluido el
``TestClient`` de la API), así el contrato se testea sin transporte.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


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


def run_etl(client: Any, etl_id: str, business_date: str,
            inputs: dict[str, str], params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispara una corrida subiendo los archivos locales indicados por rol."""
    import json as _json

    files = {}
    for role, path in inputs.items():
        source = Path(path)
        files[role] = (source.name, source.read_bytes())
    data = {"etl_id": etl_id, "business_date": business_date,
            "params": _json.dumps(params or {})}
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

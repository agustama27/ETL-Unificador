"""Servidor MCP sobre la API de la consola.

Uso: ``pip install -e ".[mcp]"`` y registrar en el cliente MCP::

    {"command": "python", "args": ["-m", "platform_mcp.server"],
     "env": {"ETL_API_URL": "http://localhost:8000", "ETL_CONSOLE_TOKEN": "..."}}
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from platform_mcp import tools

mcp = FastMCP("etl-unificador")


def _local_paths_allowed() -> bool:
    """Solo en stdio: ahí el proceso corre en la máquina de quien lo invoca."""
    return os.environ.get("ETL_MCP_TRANSPORT", "stdio") == "stdio"


def _client() -> httpx.Client:
    headers = {}
    token = os.environ.get("ETL_CONSOLE_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=os.environ.get("ETL_API_URL", "http://localhost:8000"),
                        headers=headers, timeout=120)


@mcp.tool()
def list_etls() -> list[dict[str, Any]]:
    """Lista los ETLs del catálogo con su cliente, estado y motivo si están inertes."""
    with _client() as client:
        return tools.list_etls(client)


@mcp.tool()
def describe_etl(etl_id: str) -> dict[str, Any]:
    """Detalle de un ETL: entradas requeridas, salidas prometidas, params y timeout."""
    with _client() as client:
        return tools.describe_etl(client, etl_id)


@mcp.tool()
def preparar_carga(etl_id: str) -> dict[str, Any]:
    """Devuelve un link de un solo uso para subir los archivos de un ETL.

    Pasale el link a la persona, esperá a que suelte los archivos y volvé con
    el upload_id. Nunca pidas ni transcribas el contenido de un archivo: los
    datos deben llegar por el link, no por la conversación.
    """
    with _client() as client:
        return tools.preparar_carga(client, etl_id)


@mcp.tool()
def estado_carga(upload_id: str) -> dict[str, Any]:
    """Qué roles ya se subieron y cuáles faltan. Consultalo antes de lanzar."""
    with _client() as client:
        return tools.estado_carga(client, upload_id)


@mcp.tool()
def run_etl(etl_id: str, business_date: str,
            upload_id: str | None = None,
            inputs: dict[str, str] | None = None,
            params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispara una corrida. Preferí upload_id, obtenido con preparar_carga.

    inputs mapea rol → ruta local (ej. {"base": "./base.csv"}) y solo sirve
    cuando el servidor corre en la misma máquina que los archivos.
    business_date debe ser la fecha de hoy en formato ISO (regla del sistema).
    """
    with _client() as client:
        return tools.run_etl(client, etl_id, business_date, inputs, params,
                             upload_id=upload_id,
                             allow_local_paths=_local_paths_allowed())


@mcp.tool()
def get_run(run_id: str) -> dict[str, Any]:
    """Estado y evidencia de una corrida: lifecycle, artefactos, logs y errores."""
    with _client() as client:
        return tools.get_run(client, run_id)


@mcp.tool()
def download_artifact(run_id: str, role: str, destination: str) -> str:
    """Descarga un artefacto por rol a un directorio local y devuelve la ruta guardada."""
    with _client() as client:
        return tools.download_artifact(client, run_id, role, destination)


def main() -> None:
    """stdio por default; `ETL_MCP_TRANSPORT=streamable-http` lo vuelve servicio."""
    if os.environ.get("ETL_MCP_TRANSPORT", "stdio") == "stdio":
        mcp.run()
        return

    import uvicorn

    from platform_mcp.http import build_app

    uvicorn.run(build_app(mcp),
                host=os.environ.get("ETL_MCP_HOST", "0.0.0.0"),
                port=int(os.environ.get("PORT", "9000")))


if __name__ == "__main__":
    main()

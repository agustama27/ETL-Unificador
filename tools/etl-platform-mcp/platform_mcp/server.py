"""Servidor MCP (stdio) sobre la API de la consola.

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
def run_etl(etl_id: str, business_date: str, inputs: dict[str, str],
            params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispara una corrida. inputs mapea rol → ruta local del archivo (ej. {"base": "./base.csv"}).

    business_date debe ser la fecha de hoy en formato ISO (regla del sistema).
    """
    with _client() as client:
        return tools.run_etl(client, etl_id, business_date, inputs, params)


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
    mcp.run()


if __name__ == "__main__":
    main()

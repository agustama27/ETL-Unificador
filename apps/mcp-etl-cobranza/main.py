"""Entrypoint del servidor MCP. Espeja el de la API para que el contenedor
arranque igual en los dos servicios.

    python apps/mcp-etl-cobranza/main.py --transport streamable-http --port 9000
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
for ruta in (RAIZ / "apps/mcp-etl-cobranza",):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Servidor MCP del ETL Unificador")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"),
                        default=os.environ.get("ETL_MCP_TRANSPORT", "stdio"))
    parser.add_argument("--host", default=os.environ.get("ETL_MCP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "9000")))
    args = parser.parse_args(argv)

    # El servidor lee el transporte del entorno: la bandera solo lo siembra, para
    # que valgan lo mismo `--transport` y ETL_MCP_TRANSPORT.
    os.environ["ETL_MCP_TRANSPORT"] = args.transport
    os.environ["ETL_MCP_HOST"] = args.host
    os.environ["PORT"] = str(args.port)

    from platform_mcp.server import main as serve

    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

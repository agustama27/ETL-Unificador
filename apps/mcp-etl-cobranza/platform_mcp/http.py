"""Adaptador HTTP del servidor MCP: auth de borde y sondas.

`FastMCP.run("streamable-http")` sirve el endpoint pero no deja meter nada
alrededor, y este proceso necesita dos cosas más: rechazar a quien no trae el
token, y responder una sonda para el orquestador de contenedores. Por eso se
construye la app ASGI y se envuelve.

El guard es ASGI puro y no `BaseHTTPMiddleware`: ese intermedia el cuerpo de la
respuesta y rompe el streaming SSE del que depende Streamable HTTP.
"""

from __future__ import annotations

import hmac
import json
import os
from typing import Any, Callable

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

# La sonda queda abierta a proposito: un probe con token es un secreto mas para
# rotar a cambio de nada. Es el mismo criterio que ya usa la API con /health.
OPEN_PATHS = frozenset({"/health"})


class BearerGuard:
    """Exige un bearer compartido en todo lo que no sea una sonda."""

    def __init__(self, app: Any, token: str, *, unconfigured: bool) -> None:
        self._app, self._token, self._unconfigured = app, token, unconfigured

    async def _refuse(self, send: Callable[..., Any], status: int, detail: str) -> None:
        body = json.dumps({"detail": detail}).encode("utf-8")
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") in OPEN_PATHS:
            return await self._app(scope, receive, send)
        if self._unconfigured:
            return await self._refuse(
                send, 503, "Autenticación no configurada: seteá ETL_MCP_TOKEN o, "
                           "sólo para desarrollo, ETL_MCP_AUTH_DISABLED=1")
        if self._token:
            headers = {name.lower(): value for name, value in scope.get("headers", ())}
            supplied = headers.get(b"authorization", b"").decode("latin-1")
            supplied = supplied.removeprefix("Bearer ").strip()
            if not hmac.compare_digest(supplied.encode("utf-8"),
                                       self._token.encode("utf-8")):
                return await self._refuse(send, 401, "Token inválido o ausente")
        return await self._app(scope, receive, send)


def _trust_hosts(server: Any, hosts: list[str]) -> None:
    """Declara los Host/Origin legítimos sin apagar la protección.

    El servidor valida el header `Host` contra una allowlist para frenar DNS
    rebinding, y por default solo acepta localhost. Detrás de un proxy llega el
    host público (`10.0.32.181:8082`) y la petición se rechaza con **421
    Misdirected Request** — que no es un 401 y no se parece a un problema de
    autenticación, así que conviene reconocerlo.

    Se declaran los hosts en vez de desactivar la protección: apagarla dejaría
    que cualquier página web le hable a este servidor desde el navegador de
    alguien que esté en la red.
    """
    if not hosts:
        return
    server.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=[f"{scheme}://{host}"
                         for host in hosts for scheme in ("http", "https")],
    )


def build_app(server: Any, *, token: str | None = None,
              stateless: bool = True,
              allowed_hosts: list[str] | None = None) -> Starlette:
    """App ASGI del MCP: endpoint /mcp, sonda /health y guard de token.

    `stateless` evita la afinidad de sesión, que es lo que permite correr más de
    una réplica detrás de un balanceador plano.

    Ojo al testear: el session manager del servidor admite **un solo arranque
    por proceso**. Levantar el lifespan de esta app dos veces sobre el mismo
    `server` falla. En producción da igual (un proceso, un arranque); en tests
    conviene ejercitar el guard aparte, sobre una app trivial.
    """
    if token is not None:
        required, unconfigured = token, False
    else:
        required = os.environ.get("ETL_MCP_TOKEN", "")
        unconfigured = (not required and os.environ.get(
            "ETL_MCP_AUTH_DISABLED", "").lower() not in ("1", "true"))

    if allowed_hosts is None:
        allowed_hosts = [item.strip() for item
                         in os.environ.get("ETL_MCP_ALLOWED_HOSTS", "").split(",")
                         if item.strip()]
    _trust_hosts(server, allowed_hosts)

    server.settings.stateless_http = stateless
    app: Starlette = server.streamable_http_app()

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.add_route("/health", health, methods=["GET"])
    app.add_middleware(BearerGuard, token=required, unconfigured=unconfigured)
    return app

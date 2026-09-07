# Contexto de build: la RAIZ del repositorio, no esta carpeta.
#   docker build -f apps/mcp-etl-cobranza/Dockerfile -t <imagen> .
#
# Mucho mas flaco que el de la API a proposito: este servicio NO ejecuta ETLs.
# Es un cliente HTTP sobre etl-platform-api, asi que no necesita el arbol etls/,
# ni pandas, ni apps/commons, ni un volumen. Todo el estado vive del otro lado.
FROM python:3.12-slim

# TZ acompaña a la del backend para que las fechas que el agente ve y las que la
# API valida (business_date == hoy) sean el mismo dia.
ENV TZ=America/Argentina/Buenos_Aires \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && useradd --create-home --uid 1000 mcp

COPY --from=ghcr.io/astral-sh/uv:0.11.10 /uv /usr/local/bin/uv

WORKDIR /app

# Solo el extra [mcp]: sin --all-extras no entran pandas ni las deps de cliente.
# --no-install-project porque el paquete llega por PYTHONPATH, y instalarlo
# obligaria a copiar etls/ y apps/commons para que setuptools los encuentre.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra mcp --no-install-project

COPY --chown=mcp:mcp apps/mcp-etl-cobranza ./apps/mcp-etl-cobranza

ENV PYTHONPATH=/app/apps/mcp-etl-cobranza:/app \
    ETL_MCP_TRANSPORT=streamable-http \
    PORT=9000

USER mcp
EXPOSE 9000

CMD ["python", "apps/mcp-etl-cobranza/main.py", \
     "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9000"]

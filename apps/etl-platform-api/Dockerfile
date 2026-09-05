# Contexto de build: la RAIZ del repositorio, no esta carpeta.
#   docker build -f apps/etl-platform-api/Dockerfile -t <imagen> .
# El servicio necesita apps/commons y el arbol etls/ completo, porque ejecuta los
# ETLs legacy como subprocesos.
FROM python:3.12-slim

# TZ es funcional, no cosmetico: los wrappers de etls/ nombran sus archivos de
# salida con la fecha LOCAL (`date.today()`), y los manifests declaran
# `output_date_source: system_date`. Un pod en UTC a las 21:00 de Argentina ya
# esta en el dia siguiente y los globs no encuentran los artefactos.
ENV TZ=America/Argentina/Buenos_Aires \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && useradd --create-home --uid 1000 etl

COPY --from=ghcr.io/astral-sh/uv:0.11.10 /uv /usr/local/bin/uv

WORKDIR /app

# Capa de dependencias: solo se invalida si cambian el manifiesto o el lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --all-extras --no-install-project

COPY --chown=etl:etl . .
RUN uv sync --locked --all-extras \
    && mkdir -p var && chown -R etl:etl /app/var

# Los paquetes conservan su nombre de import de primer nivel: los manifest.yaml
# resuelven el adapter por string en runtime (etl_core.contracts:SubprocessAdapter).
ENV PYTHONPATH=/app/apps/commons:/app/apps/etl-platform-api:/app

USER etl
EXPOSE 8000

# var/ es un volumen: guarda index.sqlite, la evidencia de corridas, el estado
# promovido y los uploads. Sin volumen se pierde en cada reinicio del pod.
VOLUME ["/app/var"]

CMD ["python", "apps/etl-platform-api/main.py", "--config", "config/dev.json", \
     "--host", "0.0.0.0", "--port", "8000"]

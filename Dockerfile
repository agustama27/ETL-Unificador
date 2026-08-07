FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --uid 1000 etl

WORKDIR /app

COPY --chown=etl:etl . .

RUN pip install -e ".[etl,api,test]" \
    && mkdir -p var \
    && chown etl:etl /app var

USER etl

EXPOSE 8000

CMD ["uvicorn", "platform_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

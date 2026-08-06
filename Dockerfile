FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY . .

RUN pip install -e ".[etl,api,test]"

RUN useradd --create-home --uid 1000 etl \
    && mkdir -p var \
    && chown -R etl:etl var

USER etl

EXPOSE 8000

CMD ["uvicorn", "platform_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

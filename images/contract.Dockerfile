# One image for the Stage 9 kind contract. It carries the API, the runtime
# worker, the gateways, the sandbox manager, fake-llm and alembic. Each
# deployment sets AR_APP_MODULE or its console command. Tag it as ar-api,
# ar-runtime, ar-mcp-gateway, ar-sandbox-manager, ar-model-gateway,
# ar-fake-llm and ar-migrate.
FROM ghcr.io/astral-sh/uv:0.13.3 AS uvbin

FROM python:3.14.8-slim-bookworm

COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini tesseract-ocr tesseract-ocr-eng chromium \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY services services
COPY connectors connectors
RUN uv sync --frozen --no-dev --no-editable \
        --package ar-api \
        --package ar-runtime \
        --package ar-mcp-gateway \
        --package ar-sandbox-manager \
        --package ar-model-gateway \
        --package ar-fake-llm \
        --package ar-domain \
    && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AR_PORT=8000

USER 10001
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "ar_common.serve"]

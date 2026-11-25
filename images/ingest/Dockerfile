# Ingest image. Docling is the layout parser. The API image does not install it.
FROM ghcr.io/astral-sh/uv:0.13.3 AS uvbin
FROM python:3.14.8-slim-bookworm
COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini tesseract-ocr tesseract-ocr-eng \
        libreoffice-writer libreoffice-calc poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY services services
# The policy decision rules; the ar-domain package build copies them in (see python-service.Dockerfile).
COPY policies/rego/ar policies/rego/ar
RUN uv sync --frozen --no-dev --no-editable --package ar-ingest \
    && chown -R app:app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 AR_APP_MODULE=ar_ingest.main AR_PORT=8014
USER 10001
EXPOSE 8014
ENTRYPOINT ["tini", "--", "python", "-m", "ar_common.serve"]

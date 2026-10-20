# One image build for every Python deployable. Spec: docs/07-ops/ci-cd.md §3.
FROM ghcr.io/astral-sh/uv:0.13.3 AS uvbin

FROM python:3.14.8-slim-bookworm

COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY services services
COPY connectors connectors

ARG SERVICE=api
RUN package="ar-$(printf '%s' "$SERVICE" | tr '_' '-')" \
    && uv sync --frozen --no-dev --no-editable --package "$package" \
    && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AR_PORT=8000

USER 10001
EXPOSE 8000
ENTRYPOINT ["tini", "--", "python", "-m", "ar_common.serve"]

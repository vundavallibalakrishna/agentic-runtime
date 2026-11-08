# The ar-sandbox image. It bakes the sandbox-agent, which runs one sandbox's
# commands and file operations, and the shell tools a computer needs. uid 10001,
# no package-manager credentials. The scientific-Python set, LibreOffice and the
# other document libraries are M40-T02; Chromium and Playwright are not here
# (OQ-37, OQ-87) — the browser tools run in the API process until that image is
# published. Spec: docs/03-specs/12-sandbox-manager.md §7.1.
FROM ghcr.io/astral-sh/uv:0.13.3 AS uvbin

FROM python:3.14.8-slim-bookworm

COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tini git curl ca-certificates jq ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY services services
COPY connectors connectors

RUN uv sync --frozen --no-dev --no-editable --package ar-sandbox-agent \
    && mkdir -p /workspace \
    && chown -R sandbox:sandbox /app /workspace

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AR_SANDBOX_ROOT=/ \
    AR_SANDBOX_AGENT_HOST_PORT=8080

USER 10001
WORKDIR /workspace
EXPOSE 8080
ENTRYPOINT ["tini", "--", "ar-sandbox-agent"]

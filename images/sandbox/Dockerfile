# The ar-sandbox image: the computer an agent gets per conversation. It bakes the
# sandbox-agent (which runs one sandbox's commands and file operations) and the
# toolbox user code reaches — the scientific-Python and document libraries
# (sandbox-tools.txt), LibreOffice headless, poppler, tesseract (configurable
# languages via SANDBOX_TESSERACT_LANGS), ffmpeg and Noto fonts. uid 10001, no
# package-manager credentials. Chromium and Playwright are not here (OQ-37, OQ-87);
# the browser tools run in the API process until that image is published.
# Spec: docs/03-specs/12-sandbox-manager.md §7.1.
FROM ghcr.io/astral-sh/uv:0.13.3 AS uvbin

FROM python:3.14.8-slim-bookworm

COPY --from=uvbin /uv /uvx /usr/local/bin/

# System tools and the document/OCR/media stack a computer carries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tini git curl ca-certificates jq ripgrep \
        libreoffice-calc libreoffice-writer libreoffice-impress \
        poppler-utils tesseract-ocr ffmpeg \
        fonts-noto fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox

# Tesseract language data. Default English; override at build time, e.g.
# --build-arg SANDBOX_TESSERACT_LANGS="eng hin tam deu".
ARG SANDBOX_TESSERACT_LANGS="eng"
RUN apt-get update \
    && for lang in ${SANDBOX_TESSERACT_LANGS}; do \
        apt-get install -y --no-install-recommends "tesseract-ocr-${lang}"; \
    done \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY services services
COPY connectors connectors
COPY images/sandbox/sandbox-tools.txt ./sandbox-tools.txt

# The agent, then the user toolbox into the same environment so a command that runs
# ``python3`` finds pandas, numpy, matplotlib and the document libraries.
RUN uv sync --frozen --no-dev --no-editable --package ar-sandbox-agent \
    && uv pip install --python /app/.venv/bin/python --no-cache -r sandbox-tools.txt \
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

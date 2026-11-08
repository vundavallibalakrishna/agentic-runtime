# The ar-sandbox image: the computer an agent gets per conversation. It bakes the
# sandbox-agent (which runs one sandbox's commands and file operations) and the
# toolbox user code reaches — the scientific-Python and document libraries
# (sandbox-tools.txt), LibreOffice headless, poppler, tesseract (configurable
# languages via SANDBOX_TESSERACT_LANGS), ffmpeg and Noto fonts. uid 10001, no
# package-manager credentials. Node, Playwright and Chromium are added only with
# --build-arg WITH_BROWSER=1 (the `browser` template); CI's default image leaves them
# out so it stays small (OQ-37, OQ-87). Spec: docs/03-specs/12-sandbox-manager.md §7.1.
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

# The browser, built only for the `browser` template (OQ-37, OQ-87): Node 24 with pnpm
# for user JavaScript, and Playwright-driven Chromium the agent's browser tools use. CI's
# default image leaves it out (WITH_BROWSER=0) so it stays small; build the browser image
# with --build-arg WITH_BROWSER=1.
ARG WITH_BROWSER=0
ARG NODE_VERSION=24.22.2
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
COPY images/sandbox/browser-tools.txt ./browser-tools.txt
RUN if [ "$WITH_BROWSER" = "1" ]; then \
        set -eux; \
        apt-get update && apt-get install -y --no-install-recommends xz-utils && rm -rf /var/lib/apt/lists/*; \
        arch="$(dpkg --print-architecture)"; \
        case "$arch" in \
            amd64) nodearch=x64 ;; \
            arm64) nodearch=arm64 ;; \
            *) echo "unsupported arch $arch" >&2; exit 1 ;; \
        esac; \
        curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${nodearch}.tar.xz" \
            | tar -xJ -C /usr/local --strip-components=1; \
        corepack enable; \
        uv pip install --python /app/.venv/bin/python --no-cache -r browser-tools.txt; \
        mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"; \
        /app/.venv/bin/playwright install --with-deps chromium; \
        chown -R sandbox:sandbox "$PLAYWRIGHT_BROWSERS_PATH"; \
    fi

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AR_SANDBOX_ROOT=/ \
    AR_SANDBOX_AGENT_HOST_PORT=8080

USER 10001
WORKDIR /workspace
EXPOSE 8080
ENTRYPOINT ["tini", "--", "ar-sandbox-agent"]

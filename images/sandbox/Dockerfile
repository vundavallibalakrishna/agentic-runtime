# The ar-sandbox image: the computer an agent gets per conversation. It bakes the
# sandbox-agent (which runs one sandbox's commands and file operations) and the
# toolbox user code reaches — the scientific-Python and document libraries
# (sandbox-tools.txt, pinned by uv.lock), LibreOffice headless, poppler, tesseract
# (languages via SANDBOX_TESSERACT_LANGS), ffmpeg and Noto fonts. Chromium is baked
# too: Node is pinned by NODE_VERSION and Playwright's Chromium by the lockfile.
# Set WITH_BROWSER=0 only for a slim local experiment. The in-process browser is
# dev-only. uid 10001, no package-manager credentials.
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

# Node is pinned. Playwright Chromium is the version locked for ar-sandbox-agent's
# browser extra. WITH_BROWSER=0 skips that layer for a slim local build.
ARG WITH_BROWSER=1
ARG NODE_VERSION=24.22.2
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
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
        uv sync --frozen --no-dev --no-editable --package ar-sandbox-agent --extra browser; \
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

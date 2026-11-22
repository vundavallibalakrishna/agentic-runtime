# One image build for every Python deployable. Spec: docs/07-ops/ci-cd.md §3.
FROM ghcr.io/astral-sh/uv:0.13.3 AS uvbin

FROM python:3.14.8-slim-bookworm

COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN apt-get update \
    && apt-get install -y --no-install-recommends tini tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY services services
COPY connectors connectors
# The task templates every install has (summarise, compare, obligations, outline). The
# product reads them from AR_PACKS_DIR, which is this folder unless a customer mounts
# their own. No other pack is part of the image.
COPY packs/examples/task-templates packs/examples/task-templates
# The policy decision rules. The ar-domain package build copies them in beside the code
# that serves the OPA bundle; without them that build fails, which is the intent.
COPY policies/rego/ar policies/rego/ar

# SERVICE names the package to install. A second package, for an image that runs two
# workers in one process, is named in ALSO.
ARG SERVICE=api
ARG ALSO=
RUN packages="--package ar-$(printf '%s' "$SERVICE" | tr '_' '-')" \
    && if [ -n "$ALSO" ]; then packages="$packages --package ar-$(printf '%s' "$ALSO" | tr '_' '-')"; fi \
    && uv sync --frozen --no-dev --no-editable $packages \
    && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AR_PORT=8000

USER 10001
EXPOSE 8000
ENTRYPOINT ["tini", "--", "python", "-m", "ar_common.serve"]

# Computer image. uid 10001, no package-manager credentials.
# Chromium, LibreOffice and the scientific Python set are published with the
# digest pin. CI does not build this Dockerfile; the dev computer runs in-process.
FROM python:3.14.8-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git jq \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox
COPY images/sandbox/health.py /health.py
USER 10001
WORKDIR /workspace
EXPOSE 8080
CMD ["python", "/health.py"]

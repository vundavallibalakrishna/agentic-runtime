# Placeholder until M7. The full sandbox toolchain (Chromium, LibreOffice, Node) is not baked in.
FROM python:3.14.8-slim-bookworm
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY images/sandbox/health.py /health.py
USER 10001
EXPOSE 8080
CMD ["python", "/health.py"]

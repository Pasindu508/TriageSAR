# syntax=docker/dockerfile:1
# Multi-stage build: 1) build the web app, 2) run API + static web app from one small image.
# Works locally (docker compose), on Hugging Face Spaces (user 1000, app_port 8000) and on hosts that set $PORT.

FROM node:24-slim AS web
WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    TRIAGESAR_DATA_DIR=/app/data/fixtures TRIAGESAR_WEB_DIST=/app/apps/web/dist \
    TRIAGESAR_CONFIG=/app/config/triagesar.toml
WORKDIR /app
COPY pyproject.toml README.md ./
COPY science/ science/
COPY apps/api/ apps/api/
# Editable install keeps the package next to config/ and data/, which it locates relative to itself.
RUN pip install -e .
COPY config/ config/
COPY data/fixtures/ data/fixtures/
COPY --from=web /src/apps/web/dist apps/web/dist
# Hugging Face Spaces runs containers as uid 1000; use the same everywhere.
RUN useradd --create-home --uid 1000 triagesar
USER triagesar
ENV PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4).status == 200 else 1)"
# No Earthdata credentials are ever needed or present in this image: it serves the prepared fixtures only.
CMD ["sh", "-c", "exec python -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]

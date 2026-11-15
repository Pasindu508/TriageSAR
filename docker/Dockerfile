# syntax=docker/dockerfile:1
# Multi-stage build: 1) build the web app, 2) run API + static web app from one small image.

FROM node:24-slim AS web
WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    TRIAGESAR_DATA_DIR=/app/data/fixtures TRIAGESAR_WEB_DIST=/app/apps/web/dist
WORKDIR /app
COPY pyproject.toml README.md ./
COPY science/ science/
COPY apps/api/ apps/api/
RUN pip install .
COPY config/ config/
COPY data/fixtures/ data/fixtures/
COPY --from=web /src/apps/web/dist apps/web/dist
RUN useradd --create-home --uid 10001 triagesar
USER triagesar
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
# No Earthdata credentials are ever needed or present in this image: it serves the prepared fixture only.
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]

# Deployment

The public demo is one process: the FastAPI service, which also serves the built web app. It reads the
prepared fixture only. Ingesting NASA data is a developer workflow (`scripts/`) and is never triggered by a
visitor.

## Local

```bash
make setup
make start           # release app on http://localhost:8000
```

Development with hot reload: run `.venv/bin/python -m uvicorn app.main:app --app-dir apps/api --reload` and,
in `apps/web`, `npm run dev` (http://localhost:5173, proxies `/api` to port 8000).

## Docker

```bash
make docker          # docker compose up --build  →  http://localhost:8000
```

`docker/Dockerfile` is a multi-stage build: Node builds the web app, then a `python:3.12-slim` image installs
the Python package and copies `config/`, `data/fixtures/` and the built web app. The container runs as a
non-root user on a read-only file system and has a health check on `/health`.

Build the real-data fixture **before** building the image, so that it is copied in. The image never contains
Earthdata credentials (`.env` is excluded by `.dockerignore`) and the web bundle contains none either.

> Status: the Dockerfile and compose file are written but were not built on the development machine, because
> no Docker daemon was running there. Treat the image as untested until `make docker` has succeeded once.

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `TRIAGESAR_DATA_DIR` | `./data/fixtures` | fixture registry and files |
| `TRIAGESAR_CONFIG` | `./config/triagesar.toml` | analysis configuration |
| `TRIAGESAR_WEB_DIST` | `./apps/web/dist` | built web app to serve; if absent, only the API is served |
| `TRIAGESAR_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | origins allowed for the dev server |
| `TRIAGESAR_INCLUDE_SYNTHETIC` | unset | development only: also serve the synthetic test event. Never set on a public demo. |

## Caching and headers

- `/assets/*` (hashed file names): `public, max-age=31536000, immutable`
- overlay PNGs: `public, max-age=3600`
- JSON and `index.html`: `no-cache`
- all responses: `X-Content-Type-Options: nosniff`

## Hosting notes

Any host that runs a container works (one small instance is enough; analysis takes well under a second and is
cached). Put it behind HTTPS. There is no database and no state to back up beyond the repository.

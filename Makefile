# TriageSAR - common tasks. `make setup` then `make demo`.
PY ?= .venv/bin/python
PIP ?= .venv/bin/pip
WEB := apps/web
EVENT ?= venezuela-2026-06-24

.PHONY: help setup lint typecheck test test-e2e build start demo auto-ingest auto-ingest-check static-site demo-synthetic docker verify-data discover fixture roads analyse openapi clean

help:
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup: ## Create the Python environment and install web dependencies
	python3.12 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	cd $(WEB) && npm ci

lint: ## Lint Python and the web app
	$(PY) -m ruff check .
	cd $(WEB) && npm run lint

typecheck: ## Type-check Python and TypeScript
	$(PY) -m mypy science/triagesar apps/api/app scripts
	cd $(WEB) && npm run typecheck

test: ## Unit and API tests (offline; no NASA access needed)
	$(PY) -m pytest --cov=triagesar --cov=app --cov-report=term-missing:skip-covered
	cd $(WEB) && npm test

test-e2e: build ## Playwright happy path against the TEST ONLY synthetic event
	cd $(WEB) && npx playwright install chromium && npx playwright test

build: ## Build the production web app into apps/web/dist
	cd $(WEB) && npm run build

start: build ## Run the release app (production build, real data only) on http://localhost:8000
	env -u TRIAGESAR_INCLUDE_SYNTHETIC $(PY) -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000

demo: build ## Same as start (kept for the docs)
	$(PY) -m uvicorn app.main:app --app-dir apps/api --port 8000

demo-synthetic: build ## Same, plus the clearly labelled TEST ONLY synthetic event (for development)
	$(PY) scripts/make_synthetic_fixture.py
	TRIAGESAR_INCLUDE_SYNTHETIC=1 $(PY) -m uvicorn app.main:app --app-dir apps/api --port 8000

static-site: ## Export a static snapshot (web app + pre-computed API files) into .cache/site
	$(PY) scripts/export_static_site.py --out .cache/site --base /

docker: ## Build and run the single-container deployment on http://localhost:8000
	docker compose up --build

auto-ingest-check: ## List earthquakes with new NISAR coverage that would be added (no login, writes nothing)
	$(PY) scripts/auto_ingest.py --dry-run

auto-ingest: ## Add new case studies from newly published NISAR data (needs EARTHDATA_TOKEN)
	$(PY) scripts/auto_ingest.py

verify-data: ## Verify SHA-256 checksums of the fixtures
	$(PY) scripts/verify_fixture_hashes.py

discover: ## Query the ASF catalogue for NISAR GUNW granules over the demo area (no credentials)
	$(PY) scripts/discover_nisar.py --bbox -68.5 9.5 -65.5 11.5 --start 2026-06-10 --end 2026-07-05 --product GUNW

fixture: ## Build the real-data fixture (needs Earthdata credentials in .env or ~/.netrc)
	$(PY) scripts/build_demo_fixture.py --event $(EVENT)

roads: ## Refresh the cached OpenStreetMap road extract
	$(PY) scripts/fetch_osm_roads.py --event $(EVENT)

analyse: ## Print the inspection queue and the masking ablation for the event
	$(PY) scripts/run_analysis.py --event $(EVENT) --ablation

openapi: ## Regenerate packages/shared/openapi.json and the web test payloads
	$(PY) scripts/export_openapi.py --web-fixtures

clean:
	rm -rf $(WEB)/dist $(WEB)/test-results $(WEB)/playwright-report .cache .pytest_cache .mypy_cache .ruff_cache .coverage

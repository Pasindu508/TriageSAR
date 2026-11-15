# Architecture

```
            developer workflow (needs Earthdata login)             public demo (offline, no credentials)
  ASF Search API ──► discover_nisar.py                       ┌──────────────────────────────────────────┐
  NISAR GUNW .h5 ──► build_demo_fixture.py ──► data/fixtures │ FastAPI (apps/api)                        │
  Overpass API  ──► fetch_osm_roads.py     ──► data/fixtures │   loads fixture ─► science pipeline       │
                                                             │   caches result ─► JSON + PNG overlays    │
                                                             │   serves built web app (apps/web/dist)    │
                                                             └───────────────▲──────────────────────────┘
                                                                             │ /api/v1/*
                                                             React + MapLibre GL JS (apps/web)
```

## Components

| Path | Role |
|---|---|
| `science/triagesar/nisar` | ASF discovery, Earthdata authentication, defensive HDF5 reader, metadata |
| `science/triagesar/processing` | phase conversion, quality states, product mask, georeferencing, zones, statistics |
| `science/triagesar/infrastructure` | Overpass client, road loading, zone–road intersection, corridor evidence |
| `science/triagesar/prioritisation` | score, ranking, sensitivity analysis, template explanations |
| `science/triagesar/provenance` | fixture manifest schema, SHA-256 |
| `science/triagesar/fixture.py` | build (local file or remote HTTP range reads) and load fixtures |
| `science/triagesar/pipeline.py` | one deterministic function: fixture + roads + config → `AnalysisResult` |
| `science/triagesar/render.py` | display-only PNG overlays (Web Mercator) |
| `science/triagesar/evaluation.py` | reference-product consistency metrics |
| `apps/api/app` | `api/` routes, `schemas/` versioned responses, `services/` cached analysis and methodology text, `repositories/` event registry, `core/` settings and JSON logging, `models/` errors |
| `apps/web/src` | `pages/`, `features/` (map, queue, evidence, scene summary), `components/`, `hooks/` (TanStack Query), `lib/`, `types/`, `accessibility/` |
| `packages/shared/openapi.json` | generated API contract |
| `config/triagesar.toml` | every threshold and weight, with rationale |

## Data flow at run time

1. The API lists events from `data/fixtures/demo_manifest.json`.
2. On the first request for an event it loads the GeoTIFF fixture and the cached road extract, runs
   `run_analysis` (well under a second for a fixture-sized grid) and caches the result in memory, keyed by
   the modification times of the manifest, the roads and the configuration.
3. JSON endpoints return slices of that result. The two overlay PNGs are rendered once and cached.
4. If the fixture is missing, every analysis endpoint answers `409 fixture_not_built` with the command that
   builds it. Nothing is substituted.

## API

`GET /health`, `/api/v1/events`, `/api/v1/events/{id}`, `/api/v1/events/{id}/raster/metadata`,
`/api/v1/events/{id}/raster/{displacement|quality}.png`, `/api/v1/events/{id}/hotspots`,
`/api/v1/events/{id}/inspection-queue`, `/api/v1/events/{id}/roads`, `/api/v1/events/{id}/ablation`,
`/api/v1/events/{id}/profile/{target}` (LOS values sampled along a ranked road or across a zone),
`/api/v1/events/{id}/thumbnail/{target}.png` (small picture of local motion and quality),
`/api/v1/inspection/{id}`, `/api/v1/provenance`, `/api/v1/methodology`. Interactive documentation is served at
`/docs`. Every response carries `schema_version` and `app_version`.

## Design decisions

- **Analysis at request time, not precomputed files.** The result can never drift from the fixture or the
  configuration, and a judge can change a weight in the TOML file and reload.
- **Basemap optional and NASA-only.** The analysis layers come from the API; the optional Satellite (Blue
  Marble) and Terrain (ASTER GDEM relief) basemaps are NASA GIBS tiles fetched by the browser. Offline, the
  plain background remains and nothing else changes. Labels are DOM elements because MapLibre text layers
  would need a glyph server.
- **Fewer dependencies than first planned.** The original plan listed xarray, rioxarray, GeoPandas, pandas,
  pyarrow, DuckDB, `asf_search` and `earthaccess`. They are not used: NumPy, h5py, Rasterio, Shapely and pyproj
  cover the pipeline, and ASF's documented REST Search API is called directly with Requests. Fewer packages
  mean a smaller image and less to audit. PostGIS is not needed at this scale.
- **Remote cropping.** `build_demo_fixture.py` opens the remote product with HTTP range requests (fsspec +
  h5py) and reads only the study-area window, so a 2.3 GB download is avoided.
- **Deterministic everything.** Ordering is fixed by explicit sort keys; the sensitivity analysis uses a fixed
  seed; the same inputs give byte-identical JSON (`test_pipeline_is_deterministic`).

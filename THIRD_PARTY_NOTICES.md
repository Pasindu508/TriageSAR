# Third-party notices

TriageSAR's own code is licensed under Apache-2.0 (see `LICENSE`). It depends on the open-source software
below. Licences are as declared by each project; consult each project for the full text.

## Python (runtime)

| Package | Licence | Use |
|---|---|---|
| NumPy | BSD-3-Clause | arrays |
| SciPy | BSD-3-Clause | connected-region labelling |
| h5py (and HDF5) | BSD-3-Clause (HDF5: BSD-style) | reading NISAR HDF5 |
| Rasterio (bundles GDAL, PROJ, GEOS) | BSD-3-Clause (GDAL: MIT, PROJ: MIT, GEOS: LGPL-2.1) | GeoTIFF I/O, polygonisation, display reprojection |
| pyproj | MIT | coordinate transforms |
| Shapely | BSD-3-Clause | vector geometry |
| affine | BSD-3-Clause | grid transforms |
| Pydantic | MIT | typed schemas |
| Pillow | MIT-CMU (HPND) | PNG overlays |
| Requests | Apache-2.0 | ASF, Earthdata and Overpass HTTP calls |
| fsspec, aiohttp | BSD-3-Clause, Apache-2.0 | HTTP range reads of remote HDF5 |
| FastAPI, Starlette | MIT, BSD-3-Clause | API |
| Uvicorn | BSD-3-Clause | ASGI server |

## Python (development)

pytest (MIT), pytest-cov (MIT), httpx (BSD-3-Clause), Ruff (MIT), mypy (MIT), pre-commit (MIT).

## JavaScript (runtime)

| Package | Licence | Use |
|---|---|---|
| React, React DOM | MIT | UI |
| React Router | MIT | routing |
| MapLibre GL JS | BSD-3-Clause | map rendering (no proprietary map SDK, no hosted tiles) |
| TanStack Query | MIT | data fetching |

## JavaScript (development)

Vite (MIT), TypeScript (Apache-2.0), Vitest (MIT), Testing Library (MIT), jsdom (MIT), Playwright (Apache-2.0),
ESLint and typescript-eslint (MIT), eslint-plugin-jsx-a11y (MIT), eslint-plugin-react-hooks (MIT), Prettier (MIT).

## Data

See `DATA_SOURCES.md` for NISAR (NASA/ISRO via ASF DAAC), USGS and OpenStreetMap (ODbL) terms and attribution.

## Colours

The motion colours (orange `#E69F00`, sky blue `#56B4E9`) are from the Okabe–Ito colour-blind-safe palette.

## Not used

No NASA logo or insignia is used. TriageSAR is not affiliated with or endorsed by NASA, ISRO, JPL, ASF, USGS
or OpenStreetMap.

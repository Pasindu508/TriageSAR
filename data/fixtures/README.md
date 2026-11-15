# data/fixtures

Only **real** data may live here. Synthetic test data are generated under `.cache/synthetic/` and are never
stored in this directory.

| Path | Content |
|---|---|
| `demo_manifest.json` | Registry of demo events (id, event definition, fixture directories). |
| `nisar/<event>/` | Value-preserving crop of one NISAR L2 GUNW product: one lossless GeoTIFF per layer plus `manifest.json` (provenance and SHA-256 checksums). Created by `scripts/build_demo_fixture.py`. |
| `infrastructure/<event>/` | Cached OpenStreetMap extract (`roads.geojson`, `places.geojson`) plus `osm_manifest.json`. Created by `scripts/fetch_osm_roads.py`. © OpenStreetMap contributors, ODbL 1.0. |

## Build the NISAR fixture

A free NASA Earthdata Login is required (https://urs.earthdata.nasa.gov/). Put `EARTHDATA_TOKEN=...` in `.env`, then:

```bash
python scripts/build_demo_fixture.py --event venezuela-2026-06-24
python scripts/verify_fixture_hashes.py
```

The script reads only the requested window of the 2.3 GB product through HTTP range requests, so the full
file is never stored (about ten minutes on a home connection). The fixture for `venezuela-2026-06-24` has been
built and is included: 1,579 × 906 pixels, six layers, 14.4 MB. On a machine where it is missing, the
application shows "fixture not built" instead of any observation.

## What "value-preserving" means

Each layer is written with the same data type, without scaling, resampling or interpolation, in the product's
native projection. `science/tests/test_fixture_provenance.py` checks bit-for-bit equality against the source.

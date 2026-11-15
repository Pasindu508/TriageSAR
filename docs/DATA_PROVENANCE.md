# Data provenance

Every real scientific output traces back to: event → source granule → source collection → acquisition dates →
processing version → fixture-generation command → application version.

## Where each link is recorded

| Link | Recorded in | Shown in |
|---|---|---|
| Event (time, place, source) | `config/events/<event>.json` (USGS ids and URLs) | landing page, timeline, Provenance drawer |
| Granule discovery | `granule.discovered_with`, `discovered_on` in the event definition | Provenance drawer |
| Source granule, collection, provider | fixture `manifest.json` → `source` | evidence panel, Provenance drawer, text queue |
| Acquisition dates | `manifest.json` → `acquisition` (read from the product's `identification` group) | timeline, evidence panel |
| Product and processor version | `manifest.json` → `source.product_version`, `software_version` | Provenance drawer |
| Wavelength and where it came from | `manifest.json` → `radar` (value, derivation, HDF5 path) | scene summary, Provenance drawer |
| Crop window and bounding box | `manifest.json` → `aoi`, `grid` | Provenance drawer |
| Layer source paths and checksums | `manifest.json` → `layers[*].hdf5_path`, `sha256` | Provenance drawer |
| Transformations | `manifest.json` → `transformations` | Provenance drawer |
| Corrections available / applied | `manifest.json` → `corrections` (applied is empty) | evidence panel, Provenance drawer |
| Fixture command and tool versions | `manifest.json` → `build` | Provenance drawer |
| Roads | `osm_manifest.json` (query, OSM timestamp, licence, checksums) | map attribution, Provenance drawer |
| Application version | `app_version` in every API response | Provenance drawer |

The manifest schema is `FixtureManifest` in `science/triagesar/provenance/manifest.py`; unknown fields are
rejected.

## Integrity

`python scripts/verify_fixture_hashes.py` (or `make verify-data`) recomputes the SHA-256 of every fixture file
and compares it with the manifest. The API reports the same check in `/api/v1/provenance`. Tests confirm that
a single changed byte is detected.

## Reproducing the fixture

```bash
python scripts/build_demo_fixture.py --event venezuela-2026-06-24   # needs Earthdata credentials
python scripts/fetch_osm_roads.py --event venezuela-2026-06-24      # optional refresh; OSM changes over time
```

The NISAR crop is reproducible exactly, because the granule is immutable. The road extract depends on the
state of OpenStreetMap at retrieval time, which the manifest records.

## Synthetic data

Synthetic test data never enter `data/fixtures/`. Their manifest has `data_kind: "synthetic_test"`, their
granule id is `TEST_ONLY_SYNTHETIC_GUNW_NOT_A_NASA_PRODUCT`, and the UI shows a warning banner whenever the API
is serving them.

# Build report

Updated 15 November 2026 (four case studies, dashboard redesign). Application version 0.1.0. Every figure below was computed by the commands listed
and can be reproduced from the repository.

## What is implemented

| Area | State |
|---|---|
| NISAR discovery (`scripts/discover_nisar.py`, ASF Search API) | Working against the live catalogue |
| Earthdata authentication (token, username/password, `.netrc`; secrets never logged) | Working with a real token |
| Defensive GUNW HDF5 reader, metadata, `inspect_hdf5.py` | Working on the real product (all six expected layers recognised) |
| Fixture builder (value-preserving crop over HTTP range reads, manifest, SHA-256) | Real fixture built and verified |
| Phase → LOS range change, sign convention, units | Implemented, analytic tests; sign confirmed against the NASA/JPL product (below) |
| Quality states, product-mask decoding (uint32 layout), reasons | Working on real data |
| Local-plane reference, screening threshold, zone extraction | Working on real data (see "What the first real run changed") |
| OpenStreetMap extract, road–zone intersection, nearest road, unobserved-road share | Working on real data |
| Inspection priority score, explanations, sensitivity analysis | Implemented and tested; on the real event the queue is empty (below) |
| Masking ablation; reference-product consistency evaluation | Computed on real data |
| FastAPI service, web app, accessibility basics | Working, tested, checked in a browser on the real event |
| Makefile, Dockerfile, compose, GitHub Actions, pre-commit | Written. **Docker image not built** (no Docker daemon running). CI not run (no remote). |
| Documentation, submission materials, screenshots | Written; screenshots in `docs/screenshots/` are of the real case study |

## What uses real data

| Item | Detail |
|---|---|
| NISAR product | `NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001` (collection `NISAR_L2_GUNW_PROVISIONAL_V1`, product version 1.0.11, spec 1.5.0, processed 2026-08-11). Reference 13 Jun 2026 10:06:56 UTC, secondary 25 Jun 2026 10:06:55 UTC; ascending track 162, frame 7. |
| Fixture | 1,579 × 906 pixels at 80 m (EPSG:32619), rows/columns cropped from the 4,149 × 4,239 source; six layers, 14.4 MB; checksums verified |
| Wavelength | 0.241963 m, from `centerFrequency` = 1.239 GHz in the product |
| Roads | 4,081 OpenStreetMap ways, 108 place labels; OSM data as of 2026-11-14T15:24:05Z |
| Event context | USGS `us6000t7zp` (M 7.5) and `us6000t7zc` (M 7.2) |
| Reference product (not committed) | NASA/JPL `NISAR_A162_20260613_20260625_displacements_cm_v2.tif`, downloaded to `.cache/reference/` |

## Automatic ingestion (added 15 November 2026)

`scripts/auto_ingest.py` finds significant shallow earthquakes in the USGS catalogue, looks for NISAR GUNW
products that bracket them in the ASF catalogue, and runs the full fixture pipeline for the best one, with
rollback on failure, skips for offshore areas and reused interferograms, and a per-run cap. A daily GitHub
workflow opens a pull request with whatever it adds. A live dry run on 15 November 2026 checked 42 earthquakes
(M ≥ 6.0, depth ≤ 40 km, since 17 June 2026) and listed the candidates it would try; nothing was ingested
automatically yet, so the four case studies above are unchanged. Details: `docs/AUTO_INGEST.md`.

## Responsive layout (added 15 November 2026)

Desktop, laptop, tablet and phone layouts. At ≤ 960 px the sidebar becomes an off-canvas menu behind a top bar;
the dashboard stacks into one column; the queue reveals 20 items at a time (Kumamoto ranks 936); the map legend
and attribution collapse on phones; the profile chart is drawn at its real width. An end-to-end test checks for
horizontal overflow at 375 px and 768 px on four pages and exercises the menu.

## Four case studies (added 15 November 2026)

Same code and settings for all four. Granules and study areas: `config/events/*.json` and `DATA_SOURCES.md`.

| | Venezuela | Kumamoto | Panama | Flores |
|---|---|---|---|---|
| Earthquake (USGS) | M 7.5, 24 Jun | M 6.8, 28 Jul | M 7.7, 9 Oct | M 7.8, 14 Aug (offshore) |
| NISAR pair | 13 → 25 Jun (12 d) | 21 Jul → 14 Aug (24 d) | 5 → 17 Oct (12 d, partial frame) | 12 → 24 Aug (12 d) |
| Fixture | 1,579 × 906, 14.4 MB | 1,363 × 922, 12.9 MB | 1,260 × 837, 6.9 MB | 1,586 × 905, 15.0 MB |
| Valid / caution / excluded | 30 / 20 / 49% | 37 / 22 / 41% | 11 / 5 / 84% | 40 / 13 / 47% |
| Local scatter (robust σ) | 0.54 cm | 0.67 cm | 1.02 cm | 0.44 cm |
| Threshold | 3.0 cm (floor) | 3.0 cm (floor) | 3.1 cm (robust rule) | 3.0 cm (floor) |
| Zones (total area) | 3 (2.2 km²) | 16 (44.2 km²) | 18 (211.4 km²) | 0 |
| Road segments ranked | 0 | 936 | 72 | 0 |
| Ranking stability | n/a | UNSTABLE (top item changes in 42% of runs) | stable (0%) | n/a |
| Road pixels unobserved | 20.0% | 24.5% | 63.4% | 3.2% |
| Without quality gate: zones / ranked roads | 117 / 76 | 121 / 1,800 | 12 / 140 | 195 / 74 |

Top of the Kumamoto queue: 1. 九州自動車道 (Kyushu Expressway, E3), motorway, 9.9 km inside Z01, 68.5, CAUTION;
2. 国道3号 (National Route 3), trunk, 67.8, CAUTION; 3. an unnamed tertiary road, 65.8, CAUTION.
Top of the Panama queue: Carretera Dorindo Cárdenas (5.3 km inside Z11), 81.4, CAUTION.

## Dashboard redesign (added 15 November 2026)

Light dashboard following the team's mockup, with real values only: sidebar navigation; case-study selector;
four KPI cards (zones, roads to inspect, unobserved road pixels, valid pixels); map with motion-layer selector,
extra layers and NASA GIBS Satellite/Terrain basemaps (online only); queue cards with map thumbnails rendered from
the analysis; zone cards with nearest road; an evidence strip with a line-of-sight profile chart, the real NISAR
acquisition timeline from ASF, key evidence and the share of valid pixels; and a full evidence drawer. Mockup
elements with no basis in the data (confidence percentages, risk levels, site photos, monitored-site counts,
period-over-period trends) were not reproduced.

## Results on the Venezuela event (`make analyse`)

| Quantity | Value |
|---|---|
| Pixels | 1,430,574: 30.2% VALID, 20.3% CAUTION, 49.5% EXCLUDED |
| Main exclusion reasons (a pixel can have several) | low coherence 654,704; not reliably unwrapped 498,268; product mask 503,704 (454,420 water, 68,629 invalid sub-swath) |
| Unwrapped regions | one (component 1) plus component 0 |
| Local scatter (robust σ of local LOS range change) | 0.54 cm |
| Screening threshold | 3.0 cm (the fixed floor; 3σ would be 1.6 cm) |
| Deformation zones | 3, each 0.6–0.9 km² |
| Roads ranked | **0** |
| Road-crossed pixels with no usable observation | 20.0% |

| Zone | Area | Local LOS (median / largest) | Scene-relative median | Quality (valid / caution / excluded) | Median coherence | Nearest mapped road |
|---|---:|---|---:|---|---:|---|
| Z01 | 0.89 km² | +4.1 / 8.1 cm | +20.3 cm | 22% / 72% / 6% | 0.40 | Carretera Carayaca – Colonia Tovar (L-6), 1.8 km |
| Z02 | 0.62 km² | +3.9 / 5.2 cm | +26.3 cm | 15% / 83% / 2% | 0.43 | Carretera Catia La Mar – Carayaca (L-6), 1.3 km |
| Z03 | 0.74 km² | +3.6 / 5.0 cm | +22.4 cm | 16% / 78% / 6% | 0.40 | unnamed tertiary road, 5.3 km |

**Interpretation, stated plainly.** In this interferogram, around the mapped road network of the study area,
TriageSAR finds no quality-approved patch of motion that stands out from its surroundings by 3 cm over at
least 0.5 km². The three zones it does find are small, mostly CAUTION quality and more than 1 km from any
mapped motorway-to-tertiary road, so the queue is empty. This is not a statement that the roads are
undamaged: a fifth of road-crossed pixels are unobserved, and the method does not see damage at all.

**Masking ablation.** Without the quality gate the same pipeline reports 117 zones over 1,370 km² and ranks
76 road segments, instead of 3 zones over 2.2 km² and none. The difference is made almost entirely of
low-coherence and unwrapping-failure pixels, which is why they are excluded.

**Reference-product consistency** (`scripts/evaluate_reference.py`, NASA/JPL map of the same pair). This is
consistency between two processings of the same radar data, not ground truth.

| Metric | Value |
|---|---|
| Common pixels | 706,489 |
| Pearson correlation of scene-relative LOS | 0.991 with the JPL product read as "positive = towards the satellite"; −0.991 with the opposite reading |
| Difference: median / MAD / 95th percentile of \|difference\| / RMSE | −0.04 cm / 3.1 cm / 7.0 cm / 3.9 cm |
| Zone overlap (same referencing, threshold and minimum area applied to both) | IoU 0.59 (254 vs 349 zone pixels) |

The correlation sign confirms empirically that TriageSAR's convention (positive = range increase, away from
the satellite) is right. Differences are expected: the JPL product was made by the Urgent Response system,
had ionosphere and a ramp removed and water masked. The distance between the centres of mass of the two
zone sets (13.6 km) is reported by the script but is not meaningful for several small, separate zones.

## What the first real run changed

1. **Reference method.** The original rule referenced each unwrapped region to its median over the whole
   study area and set the threshold at 3 × the robust spread of that field. On this co-seismic scene the whole
   coastal range moved: scene-relative values span about ±35 cm, the threshold rose to 46 cm, and **no zone
   was found**. The analysis now compares each pixel with a plane fitted to its surroundings (4 km window,
   same unwrapped region) and applies the unchanged rule to that local field. The fixed values (3 cm floor,
   3σ, 0.5 km², coherence 0.30 / 0.50, weights) were not changed. The old method is still available
   (`[reference] method = "component_median"`) and a regression test reproduces its failure on synthetic data.
   This is a method change made after seeing real data, and is disclosed as such in the docs and the FAQ.
2. **Speed.** Buffering a zone outline with tens of thousands of pixel-edge vertices took over two minutes in
   the ablation run and blocked the map images in the API. The road search now uses a spatial index on the
   zone's pieces; the ablation runs in about 3 s and the main analysis in under 0.5 s.
3. **Interface.** A deformation-zones list (with nearest road), a "local motion" map layer, a scene-relative
   context value on every card, and an explicit "No road is ranked" statement were added, because an empty
   queue must still show its evidence.

## What remains

- `make docker` on a machine with Docker running.
- Push to a GitHub repository so the CI workflow runs, then `pre-commit install`.
- Rehearse the demo with `submission/DEMO_SCRIPT.md`, which describes the empty-queue result.

## Commands

```bash
make setup
make start             # release app on http://localhost:8000, four real case studies
make demo-synthetic    # adds the labelled synthetic event, which does produce a non-empty queue
make discover          # ASF catalogue search, no account needed
make fixture           # rebuild the real fixture (needs EARTHDATA_TOKEN in .env)
make verify-data
make analyse           # inspection queue + masking ablation
python scripts/evaluate_reference.py --event venezuela-2026-06-24 \
  --reference .cache/reference/NISAR_A162_20260613_20260625_displacements_cm_v2.tif --reference-units cm
node scripts/capture_screenshots.mjs http://localhost:8000   # regenerate docs/screenshots
```

## Test results (15 November 2026, macOS arm64, Python 3.12.16, Node 24.22.2)

| Check | Result |
|---|---|
| `ruff check .` | passed |
| `mypy science/triagesar apps/api/app scripts` | no issues in 60 source files |
| `pytest` (science + API) | 123 passed, 1 skipped; line coverage 95% |
| skipped test | live ASF search; skipped unless `TRIAGESAR_RUN_INTEGRATION=1`; passed when run with it |
| `eslint` + `prettier --check`, `tsc -b --noEmit` | passed |
| `vitest run` | 24 passed |
| `vite build` | succeeded |
| `playwright test` (Chromium; synthetic event, all four real case studies, phone and tablet layouts, no network) | 7 passed |
| `make verify-data` | 8 fixture sets (4 NISAR, 4 OSM) checksums OK |
| `make docker` | **not run** (no Docker daemon) |

## Deviations from the brief

- The repository root is this folder, not a nested `triagesar/` directory.
- xarray, rioxarray, GeoPandas, pandas, pyarrow, DuckDB, `asf_search` and `earthaccess` are not used.
- Analysis runs in the API at request time (cached) instead of being stored as derived files.
- The evaluation is a script, not a notebook.

## Known limitations

See `docs/LIMITATIONS.md`: one viewing direction; relative values; no atmospheric correction; provisional
product; thresholds and weights never calibrated; never compared with field inspections. Specific to this
event: the local reference deliberately ignores motion that is smooth over kilometres, so the earthquake's
broad deformation (tens of centimetres) does not create zones by itself.

## Three-minute judge demo sequence

Full version: `submission/DEMO_SCRIPT.md`.

1. Landing page; **Explore the 2026 case study**.
2. Surface-motion layer: the coastal range moved up to tens of centimetres along the line of sight, relative
   to the rest of the scene. Hatching: half the scene is unobserved (sea, vegetation, decorrelation).
3. Switch to **Local motion**: only three small patches stand out from their surroundings by 3 cm or more.
4. Deformation-zones list: each zone, its quality, its nearest road (1.3 km at best). **No road is ranked**,
   and the panel says why and that this is not a clearance.
5. Scene summary: 20% of road pixels unobserved; without the quality gate there would be 117 zones and 76
   "priorities", almost all of them noise.
6. Provenance drawer: granule, dates, checksums, build command.
7. Say what was checked: against the NASA/JPL map of the same pair the correlation is 0.991, which also
   confirms the sign convention. (The figure is in this report; the app does not compute it live.)
8. Limitations; then, if time allows, `make demo-synthetic` to show a populated queue on clearly labelled
   synthetic data.

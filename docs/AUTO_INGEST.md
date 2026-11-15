# Automatic ingestion of new NISAR data

`scripts/auto_ingest.py` adds a new case study whenever NASA publishes a NISAR interferogram over a significant
earthquake. It uses the same steps, checks and provenance as the hand-made case studies; nothing is estimated
or filled in.

## How it decides

1. **Earthquakes.** USGS catalogue: magnitude ≥ 6.0, depth ≤ 40 km (configurable), from the last check onwards
   (looking back `--wait-days`, 60 by default, so late-published products are still found). The first run starts
   at 17 June 2026, the first NISAR acquisitions ASF has released.
2. **Interferograms.** ASF Search API: NISAR L2 GUNW products over the epicentre whose reference acquisition is
   before the earthquake and whose secondary acquisition is after it (from the timestamps in the granule name),
   at most 48 days apart, covering at least half of the default 120 km × 70 km study area. Urgent-response
   duplicates are ignored. The best product is chosen: validated over provisional, then most coverage, then the
   shortest pair.
3. **Skips.**
   - Earthquakes already covered by a case study, or whose best interferogram is already used by one
     (aftershocks).
   - Study areas with fewer than 25 mapped road ways (`--min-roads`), which in practice means offshore events.
   - Earthquakes with no published interferogram are marked *waiting* and re-checked on every run until they
     are older than `--wait-days`.
4. **Pipeline.** For the chosen product it writes `config/events/<id>.json` (marked `"added_by": "auto_ingest"`),
   then runs `fetch_osm_roads.py`, `build_demo_fixture.py`, `fetch_acquisitions.py` and
   `verify_fixture_hashes.py`. If any step fails, the event is removed again and retried on the next run.
5. **Limits.** At most `--max-new` (3) new case studies per run. Each fixture is about 7–15 MB and takes about
   ten minutes to read remotely.

State is kept in `data/fixtures/auto_ingest_state.json`, including checks that find no new case studies.
Automatically added case studies carry an "Added automatically" label. The public release shows its
publication time; the check history remains in the data and workflow logs.

## Commands

```bash
make auto-ingest-check     # dry run: what would be added (no login, writes nothing)
make auto-ingest           # add them (needs EARTHDATA_TOKEN in the environment or .env)
python scripts/auto_ingest.py --max-new 1 --min-magnitude 6.5 --since 2026-10-01
```

## Running it on a schedule

- **GitHub Actions:** `.github/workflows/auto-ingest.yml` runs daily at 03:00 UTC (08:30 in Sri Lanka) and on
  demand. The repository secret `EARTHDATA_TOKEN` supplies NASA access. After ingestion, fixture checksums and
  the science/API tests must pass before new case studies and check history are committed to the default
  branch. The workflow then dispatches CI and the Pages deployment explicitly, since pushes using
  `GITHUB_TOKEN` do not trigger push workflows. The Pages build validates and exports the data before the
  updated release is served at https://triagesar.devdragons.lk/.
- **A server or laptop (cron):**

  ```cron
  0 3 * * * cd /path/to/TriageSAR && make auto-ingest >> .cache/logs/auto-ingest.log 2>&1
  ```

## What it does not do

- It does not review results. Automatically added case studies have not been looked at by a person; the label
  says so. Check them before presenting them.
- It does not refine the study area: it uses the default box around the epicentre, clipped to the NISAR frame.
- It covers earthquakes only. Other surface-change events (landslides, subsidence, volcanoes) are not in a
  catalogue it can query reliably.
- It does not replace existing case studies when a newer (for example validated) product appears.

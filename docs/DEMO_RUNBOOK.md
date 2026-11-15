# Demo runbook

How to prepare and run the demo reliably, including without an internet connection.

## The day before

1. `make setup`
2. Build the real-data fixture once (needs Earthdata credentials in `.env`): `make fixture`
3. `make verify-data` → every line must say OK.
4. `make analyse` → read the queue in the terminal. **Write down what you actually see**; do not rehearse
   numbers you have not seen on screen.
5. `make build && make demo`, open http://localhost:8000 and walk through `submission/DEMO_SCRIPT.md`.
6. Optional: download the NASA/JPL reference GeoTIFF (URL in `DATA_SOURCES.md`) and run
   `python scripts/evaluate_reference.py --event venezuela-2026-06-24 --reference <file> --reference-units cm`.

## On the day

```bash
make demo        # http://localhost:8000 ; works with Wi-Fi switched off
```

Pre-flight (30 seconds): http://localhost:8000/health shows `"events_ready": 1`; the case study shows a
coloured motion layer; the Provenance drawer says all checksums match.

## If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| "No NISAR observations loaded" | fixture not built on this machine | `make fixture`, or copy `data/fixtures/nisar/<event>/` from the machine where it was built |
| Blank page | web app not built | `make build` |
| Port in use | another server on 8000 | `.venv/bin/python -m uvicorn app.main:app --app-dir apps/api --port 8080` |
| `configuration_invalid` | edited `config/triagesar.toml` incorrectly | `git checkout config/triagesar.toml` |
| Checksum mismatch | fixture file changed or corrupted | rebuild with `make fixture` |
| Map empty but queue present | WebGL disabled in the browser | use the "Queue as a text table" view, or another browser |

## Fallback without the real fixture

`make demo-synthetic` shows the complete interface on a made-up event. Say clearly that it is synthetic; the
banner says so too. Do not present its numbers as observations.

## Do not

- Do not call TriageSAR a damage detector, and do not quote an accuracy: none has been measured.
- Do not tune thresholds or weights during the demo to make a result look better. If you change a weight to
  show the sensitivity analysis, say that this is what you are doing and change it back.

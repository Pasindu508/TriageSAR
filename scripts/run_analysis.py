#!/usr/bin/env python
"""Run the full analysis for an event and print the inspection queue (optionally as JSON).

    python scripts/run_analysis.py --event venezuela-2026-06-24
    python scripts/run_analysis.py --event venezuela-2026-06-24 --ablation --json out.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import fail
from triagesar.config import load_config
from triagesar.events import get_event
from triagesar.fixture import load_fixture
from triagesar.infrastructure.osm import load_roads
from triagesar.pipeline import ablation_summary, run_analysis
from triagesar.prioritisation.explanation import fmt_cm, fmt_pct


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", required=True)
    ap.add_argument("--config", type=Path, help="alternative TOML configuration")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--ablation", action="store_true", help="also run without quality masking and compare")
    ap.add_argument("--json", type=Path, help="write the full result (and ablation) to this file")
    args = ap.parse_args()
    entry = get_event(args.event)
    if entry is None:
        fail(f"Unknown event: {args.event}")
    if not entry.fixture_ready:
        fail(f"The real-data fixture for {entry.id} has not been built. Run: python scripts/build_demo_fixture.py --event {entry.id}", 2)
    if not entry.roads_path.is_file():
        fail(f"No road extract for {entry.id}. Run: python scripts/fetch_osm_roads.py --event {entry.id}", 2)
    try:
        config = load_config(args.config)
    except ValueError as exc:
        fail(str(exc))
    fixture = load_fixture(entry.nisar_dir)
    roads = load_roads(entry.roads_path)
    result = run_analysis(fixture, roads, config).result
    m = fixture.manifest
    label = "NASA-ISRO NISAR GUNW" if m.data_kind == "nasa_nisar_gunw" else "SYNTHETIC TEST DATA - NOT NASA OBSERVATIONS"
    print(f"{m.event.title}  [{label}]")
    print(f"granule   : {m.source.granule_id}")
    print(f"dates     : reference {m.acquisition.reference_start_utc}  secondary {m.acquisition.secondary_start_utc}")
    print(f"wavelength: {result.radar.wavelength_m:.6f} m ({result.radar.derivation})")
    q = result.quality
    print(f"quality   : VALID {fmt_pct(q.fractions['VALID'])}  CAUTION {fmt_pct(q.fractions['CAUTION'])}  EXCLUDED {fmt_pct(q.fractions['EXCLUDED'])} of {q.total_pixels:,} pixels")
    t = result.threshold
    print(f"threshold : {fmt_cm(t.threshold_m)} ({t.rule}; binding: {t.binding})")
    print(f"zones     : {len(result.zones)}   road candidates: {len(result.queue)}")
    s = result.sensitivity
    if s.unstable is not None:
        print(f"stability : top item changed in {fmt_pct(s.top1_changed_fraction)} of {s.runs} weight perturbations -> {'UNSTABLE' if s.unstable else 'stable'}")
    print("\nInspection queue (inspection priority, not damage probability)")
    for item in result.queue[: args.top]:
        c = item.corridor
        print(f"{item.rank:>3}. {item.score:5.1f}  {item.asset_name}  [{item.highway_class}, zone {item.zone_id}, {item.relation}]")
        print(f"       p90 |LOS| {fmt_cm(c.p90_abs_los_m)}  valid {fmt_pct(c.valid_fraction)}  evidence quality {item.evidence_quality}")
    payload = {"result": result.model_dump(mode="json")}
    if args.ablation:
        unmasked = run_analysis(fixture, roads, config, apply_quality_mask=False).result
        payload["ablation"] = ablation_summary(result, unmasked)
        print("\nAblation (quality masking on vs off)")
        print(json.dumps(payload["ablation"], indent=2))
    if args.json:
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()

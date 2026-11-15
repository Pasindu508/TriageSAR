#!/usr/bin/env python
"""Reference-product consistency evaluation (NOT ground-truth validation).

Compares TriageSAR's relative LOS range change with an independently processed displacement
GeoTIFF of the same interferometric pair, e.g. the NASA/JPL product for the 24 June 2026
Venezuela earthquakes:

    https://aria-share.jpl.nasa.gov/20260624_Venezuela_EQ/Displacements/NISAR/NISAR_A162_20260613_20260625_displacements_cm_v2.tif

    python scripts/evaluate_reference.py --event venezuela-2026-06-24 --reference path/to/that.tif --reference-units cm

Both products derive from the same radar acquisitions, so agreement shows that two processing
chains are consistent. It says nothing about agreement with the ground.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _common import fail
from triagesar.config import load_config
from triagesar.evaluation import compare_with_reference, load_reference_on_grid
from triagesar.events import get_event
from triagesar.fixture import load_fixture
from triagesar.infrastructure.osm import load_roads
from triagesar.pipeline import run_analysis


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", required=True)
    ap.add_argument("--reference", type=Path, required=True, help="local GeoTIFF of the reference displacement product")
    ap.add_argument("--reference-units", choices=["m", "cm", "mm"], default="cm")
    ap.add_argument("--reference-positive", choices=["towards", "away"], default="towards",
                    help="what a positive reference value means relative to the satellite (JPL product: towards)")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    entry = get_event(args.event)
    if entry is None or not entry.fixture_ready:
        fail(f"No built fixture for event {args.event}")
    if not args.reference.is_file():
        fail(f"Reference file not found: {args.reference}")
    fixture = load_fixture(entry.nisar_dir)
    roads = load_roads(entry.roads_path) if entry.roads_path.is_file() else []
    config = load_config()
    art = run_analysis(fixture, roads, config)
    scale = {"m": 1.0, "cm": 0.01, "mm": 0.001}[args.reference_units]
    sign = -1.0 if args.reference_positive == "towards" else 1.0
    reference = load_reference_on_grid(args.reference, art.grid) * scale * sign
    report = compare_with_reference(art, reference, config)
    report["reference_file"] = args.reference.name
    report["reference_units"] = args.reference_units
    report["reference_positive_means"] = args.reference_positive
    print(json.dumps(report, indent=2))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

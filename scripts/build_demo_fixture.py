#!/usr/bin/env python
"""Build the offline demo fixture: a value-preserving crop of one real NISAR GUNW product.

    # crop the remote product through HTTP range requests (needs Earthdata credentials, ~no disk)
    python scripts/build_demo_fixture.py --event venezuela-2026-06-24

    # or crop a product you already downloaded
    python scripts/build_demo_fixture.py --event venezuela-2026-06-24 --source data/raw/NISAR_L2_PR_GUNW_....h5

Credentials are read from EARTHDATA_TOKEN, or EARTHDATA_USERNAME / EARTHDATA_PASSWORD, in the
environment or .env, or from ~/.netrc. They are never written to the fixture or printed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import REPO_ROOT, fail, quoted_command
from triagesar.events import get_event
from triagesar.fixture import build_fixture
from triagesar.nisar.authentication import AuthenticationError, bearer_token, resolve_credentials
from triagesar.nisar.schema import SchemaError
from triagesar.provenance.manifest import EventInfo


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", required=True, help="event id from data/fixtures/demo_manifest.json")
    ap.add_argument("--source", help="local GUNW .h5 path (default: the event's remote granule)")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"), help="override the event AOI")
    ap.add_argument("--frequency", choices=["A", "B"])
    ap.add_argument("--polarisation", choices=["HH", "VV", "HV", "VH"])
    args = ap.parse_args()

    entry = get_event(args.event)
    if entry is None or entry.data_kind != "nasa_nisar_gunw":
        fail(f"Unknown event: {args.event}")
    definition, granule = entry.definition, entry.definition.get("granule", {})
    bbox = tuple(args.bbox or definition["aoi_bbox_wgs84"])
    source, token = args.source, None
    if source is None:
        source = granule.get("download_url")
        if not source:
            fail("The event has no configured granule; pass --source")
        try:
            token = bearer_token(resolve_credentials(REPO_ROOT / ".env"))
        except AuthenticationError as exc:
            fail(str(exc), code=2)
        print(f"Reading remote product through HTTP range requests:\n  {source}")
    elif not Path(source).is_file():
        fail(f"File not found: {source}")

    event = EventInfo(
        id=definition["id"],
        title=definition["title"],
        summary=definition["summary"],
        event_time_utc=definition.get("event_time_utc"),
        event_source_name=definition.get("event_source_name"),
        event_source_url=definition.get("event_source_url"),
        notes=list(definition.get("notes", [])),
    )
    overrides = {
        k: granule[k]
        for k in ("collection", "concept_id", "provider", "download_url", "source_size_bytes")
        if granule.get(k) is not None
    }
    file_name = str(source).rsplit("/", 1)[-1]
    if granule.get("file_name") and file_name != granule["file_name"]:
        print(f"warning: source file name differs from the event's configured granule ({granule['file_name']})")
        overrides = {k: v for k, v in overrides.items() if k in ("provider",)}
    try:
        manifest = build_fixture(
            str(source), entry.nisar_dir, bbox, event, quoted_command(), token=token,  # type: ignore[arg-type]
            frequency=args.frequency, polarisation=args.polarisation, source_overrides=overrides,
        )
    except (SchemaError, ValueError, OSError) as exc:
        fail(f"Could not build the fixture: {exc}")
    total = sum(layer.bytes for layer in manifest.layers.values())
    print(f"Fixture written to {entry.nisar_dir}")
    print(f"  granule   : {manifest.source.granule_id}")
    print(f"  reference : {manifest.acquisition.reference_start_utc}   secondary: {manifest.acquisition.secondary_start_utc}")
    print(f"  grid      : {manifest.grid.width} x {manifest.grid.height} px, EPSG {manifest.grid.epsg}")
    print(f"  wavelength: {manifest.radar.wavelength_m:.6f} m ({manifest.radar.derivation}: {manifest.radar.source_hdf5_path})")
    print(f"  layers    : {', '.join(manifest.layers)}  ({total / 1e6:.1f} MB)")
    print("Next: python scripts/verify_fixture_hashes.py && python scripts/run_analysis.py --event " + definition["id"])


if __name__ == "__main__":
    main()

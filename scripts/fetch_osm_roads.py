#!/usr/bin/env python
"""Fetch the OpenStreetMap road extract for an event AOI through Overpass and cache it as GeoJSON.

    python scripts/fetch_osm_roads.py --event venezuela-2026-06-24

OSM data are (c) OpenStreetMap contributors, ODbL 1.0. The demo reads the cached files only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

from _common import REPO_ROOT, fail, quoted_command
from triagesar.config import load_config
from triagesar.events import get_event
from triagesar.infrastructure import osm
from triagesar.provenance.manifest import sha256_file


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", required=True)
    ap.add_argument("--refresh", action="store_true", help="ignore the local Overpass cache")
    args = ap.parse_args()
    entry = get_event(args.event)
    if entry is None or entry.data_kind != "nasa_nisar_gunw":
        fail(f"Unknown event: {args.event}")
    bbox = tuple(entry.definition["aoi_bbox_wgs84"])
    classes = tuple(load_config().infrastructure.highway_classes)
    query = osm.build_query(bbox, classes, timeout_s=180)  # type: ignore[arg-type]
    try:
        payload = osm.fetch_overpass(query, REPO_ROOT / ".cache" / "overpass", use_cache=not args.refresh)
    except osm.OverpassError as exc:
        fail(str(exc))
    roads, places = osm.overpass_to_geojson(payload)
    if not roads["features"]:
        fail("Overpass returned no roads for this AOI")
    out = entry.infrastructure_dir
    out.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, collection in (("roads.geojson", roads), ("places.geojson", places)):
        (out / name).write_text(json.dumps(collection, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        files[name] = {"sha256": sha256_file(out / name), "bytes": (out / name).stat().st_size, "features": len(collection["features"])}
    manifest = {
        "dataset": "OpenStreetMap road network extract",
        "provider": "OpenStreetMap contributors, retrieved through the Overpass API",
        "licence": "Open Database Licence (ODbL) 1.0",
        "licence_url": osm.OSM_LICENCE_URL,
        "attribution": osm.OSM_ATTRIBUTION,
        "overpass_endpoint": osm.DEFAULT_OVERPASS_URL,
        "osm_base_timestamp": (payload.get("osm3s") or {}).get("timestamp_osm_base"),
        "retrieved_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "bbox_wgs84": list(bbox),
        "highway_classes": list(classes),
        "query": query,
        "command": quoted_command(),
        "transformations": [
            "Ways converted to GeoJSON LineStrings; only osm_id, highway, name, ref, bridge and tunnel tags kept.",
            "Coordinates rounded to 6 decimal places (about 0.1 m).",
            "Place nodes (city, town) kept as labelled points for map orientation.",
        ],
        "files": files,
    }
    (out / "osm_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {files['roads.geojson']['features']} road ways and {files['places.geojson']['features']} places to {out}")
    print(f"OSM base timestamp: {manifest['osm_base_timestamp']}  |  {osm.OSM_ATTRIBUTION}")


if __name__ == "__main__":
    main()

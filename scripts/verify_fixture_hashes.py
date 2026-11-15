#!/usr/bin/env python
"""Verify SHA-256 checksums of every built fixture (NISAR layers and OSM extracts)."""

from __future__ import annotations

import json

from _common import fail
from triagesar.events import list_events
from triagesar.provenance.manifest import sha256_file, verify_checksums


def main() -> None:
    problems: list[str] = []
    checked = 0
    for entry in list_events():
        if entry.data_kind != "nasa_nisar_gunw":
            continue
        if entry.fixture_ready:
            issues = verify_checksums(entry.nisar_dir)
            problems += [f"{entry.id}: {p}" for p in issues]
            checked += 1
            print(f"{entry.id}: NISAR fixture {'OK' if not issues else 'FAILED'}")
        else:
            print(f"{entry.id}: NISAR fixture not built yet (run scripts/build_demo_fixture.py --event {entry.id})")
        osm_manifest = entry.infrastructure_dir / "osm_manifest.json"
        if osm_manifest.is_file():
            for name, info in json.loads(osm_manifest.read_text(encoding="utf-8")).get("files", {}).items():
                path = entry.infrastructure_dir / name
                ok = path.is_file() and sha256_file(path) == info["sha256"]
                if not ok:
                    problems.append(f"{entry.id}: OSM extract {name} missing or checksum mismatch")
                print(f"{entry.id}: OSM {name} {'OK' if ok else 'FAILED'}")
            checked += 1
        else:
            print(f"{entry.id}: OSM extract not fetched yet (run scripts/fetch_osm_roads.py --event {entry.id})")
    if problems:
        fail("\n  " + "\n  ".join(problems))
    print(f"verify-data: {checked} fixture set(s) verified, no problems")


if __name__ == "__main__":
    main()

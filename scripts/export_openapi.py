#!/usr/bin/env python
"""Export the API's OpenAPI schema to packages/shared/openapi.json and, with --web-fixtures,
regenerate the JSON payloads used by the frontend unit tests from the TEST ONLY synthetic event."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from _common import REPO_ROOT


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--web-fixtures", action="store_true")
    args = ap.parse_args()
    os.environ["TRIAGESAR_WEB_DIST"] = str(REPO_ROOT / ".cache" / "no-dist")
    if args.web_fixtures:
        from tests.support.synthetic import build_synthetic_event

        root = Path(tempfile.mkdtemp(prefix="triagesar-webfx-"))
        build_synthetic_event(root)
        os.environ["TRIAGESAR_SYNTHETIC_DIR"] = str(root)
        os.environ["TRIAGESAR_INCLUDE_SYNTHETIC"] = "1"
        empty = root / "real"
        empty.mkdir()
        (empty / "demo_manifest.json").write_text((REPO_ROOT / "data/fixtures/demo_manifest.json").read_text())
        os.environ["TRIAGESAR_DATA_DIR"] = str(empty)
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    shared = REPO_ROOT / "packages" / "shared"
    shared.mkdir(parents=True, exist_ok=True)
    (shared / "openapi.json").write_text(json.dumps(client.get("/openapi.json").json(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {shared / 'openapi.json'}")
    if args.web_fixtures:
        syn = "synthetic-test-event"
        out = REPO_ROOT / "apps" / "web" / "src" / "test" / "fixtures"
        targets = {
            "events": "/api/v1/events",
            "event": f"/api/v1/events/{syn}",
            "raster": f"/api/v1/events/{syn}/raster/metadata",
            "hotspots": f"/api/v1/events/{syn}/hotspots",
            "queue": f"/api/v1/events/{syn}/inspection-queue?limit=200",
            "roads": f"/api/v1/events/{syn}/roads",
            "ablation": f"/api/v1/events/{syn}/ablation",
            "provenance": "/api/v1/provenance",
            "methodology": "/api/v1/methodology",
            "notBuilt": "/api/v1/events/venezuela-2026-06-24",
        }
        first = client.get(targets["queue"]).json()["items"][0]["id"]
        targets["profileItem"] = f"/api/v1/events/{syn}/profile/{first}"
        targets["profileZone"] = f"/api/v1/events/{syn}/profile/Z01"
        for name, url in targets.items():
            payload = client.get(url).json()
            if name == "provenance":  # machine-specific paths and timestamps are not needed in tests
                for ev in payload["events"]:
                    if ev["fixture_manifest"]:
                        ev["fixture_manifest"]["build"]["built_at_utc"] = "2000-01-01T00:00:00Z"
            (out / f"{name}.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {len(targets)} TEST ONLY payloads to {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Export TriageSAR as a static website: the built web app plus every API response it needs, pre-computed.

    python scripts/export_static_site.py --out .cache/site --base /TriageSAR/

The API is run in-process (FastAPI TestClient) against the committed fixtures, and each response is written as a
file under <out>/static-api/. The web app is built with VITE_STATIC_API=1 so it reads those files. Values are
byte-for-byte the API's output; nothing is recomputed differently. Synthetic test data are never exported.
Used by .github/workflows/pages.yml to publish on GitHub Pages.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess  # noqa: S404  (fixed argument lists, no shell)
from pathlib import Path
from typing import Any

from _common import REPO_ROOT, fail

QUEUE_LIMIT = 200  # what the dashboard requests; the text table shows the same items


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO_ROOT / ".cache" / "site")
    ap.add_argument("--base", default="/", help="URL path the site is served under, e.g. /TriageSAR/")
    ap.add_argument("--skip-web-build", action="store_true", help="reuse an existing apps/web/dist-static")
    args = ap.parse_args()
    base = "/" + args.base.strip("/") + "/" if args.base.strip("/") else "/"

    os.environ.pop("TRIAGESAR_INCLUDE_SYNTHETIC", None)
    os.environ["TRIAGESAR_WEB_DIST"] = str(REPO_ROOT / ".cache" / "no-dist")
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app())
    out = args.out
    if out.exists():
        shutil.rmtree(out)
    data = out / "static-api"

    def get(url: str) -> Any:
        resp = client.get(url)
        if resp.status_code != 200:
            fail(f"{url} answered HTTP {resp.status_code}: {resp.text[:200]}")
        return resp

    def write_json(rel: str, payload: Any) -> None:
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    def write_bytes(rel: str, content: bytes) -> None:
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False)  # noqa: S603, S607
    events = get("/api/v1/events").json()
    events["snapshot"] = {
        "generated_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "commit": commit.stdout.strip() or None,
    }
    write_json("events.json", events)
    write_json("provenance.json", get("/api/v1/provenance").json())
    write_json("methodology.json", get("/api/v1/methodology").json())

    counts: dict[str, int] = {}
    for ev in events["events"]:
        eid = ev["id"]
        api = f"/api/v1/events/{eid}"
        prefix = f"events/{eid}"
        write_json(f"{prefix}/roads.json", get(f"{api}/roads").json())
        if ev["status"] != "ready":
            continue
        write_json(f"{prefix}/event.json", get(api).json())
        write_json(f"{prefix}/hotspots.json", hotspots := get(f"{api}/hotspots").json())
        write_json(f"{prefix}/queue.json", queue := get(f"{api}/inspection-queue?limit={QUEUE_LIMIT}").json())
        write_json(f"{prefix}/ablation.json", get(f"{api}/ablation").json())
        raster = get(f"{api}/raster/metadata").json()
        for key, name in (("displacement_url", "displacement"), ("quality_url", "quality"), ("local_url", "local")):
            if raster.get(key):
                write_bytes(f"{prefix}/{name}.png", get(raster[key]).content)
                raster[key] = f"{base}static-api/{prefix}/{name}.png"
        write_json(f"{prefix}/raster.json", raster)
        targets = [z["id"] for z in hotspots["features"]] + [i["id"] for i in queue["items"]]
        for target in targets:
            write_json(f"{prefix}/profile/{target}.json", get(f"{api}/profile/{target}").json())
            write_bytes(f"{prefix}/thumbnail/{target}.png", get(f"{api}/thumbnail/{target}.png").content)
        counts[eid] = len(targets)

    web = REPO_ROOT / "apps" / "web"
    dist = web / "dist-static"
    if not args.skip_web_build:
        env = {**os.environ, "VITE_STATIC_API": "1", "VITE_BASE": base}
        build = subprocess.run(["npx", "vite", "build", "--outDir", "dist-static", "--emptyOutDir"], cwd=web, env=env, check=False)  # noqa: S603, S607
        if build.returncode != 0:
            fail("web build failed")
    shutil.copytree(dist, out, dirs_exist_ok=True)
    # Static hosts serve 404.html for unknown paths: the app then routes deep links such as /events/<id> itself.
    shutil.copy2(out / "index.html", out / "404.html")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"Static site written to {out} ({size / 1e6:.1f} MB, base {base})")
    for eid, n in counts.items():
        print(f"  {eid}: {n} profiles and thumbnails")


if __name__ == "__main__":
    main()

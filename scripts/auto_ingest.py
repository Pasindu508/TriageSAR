#!/usr/bin/env python
"""Automatically add new case studies when NASA publishes NISAR data over a significant earthquake.

    python scripts/auto_ingest.py --dry-run          # list what would be added, change nothing
    python scripts/auto_ingest.py                    # add up to 3 new case studies
    python scripts/auto_ingest.py --max-new 1 --min-magnitude 6.5

For each USGS earthquake (default M >= 6.0, depth <= 40 km) since the last check, it looks for a NISAR L2 GUNW
interferogram whose acquisitions bracket the earthquake, and for the best one it runs exactly the same steps as
a hand-made case study:

    1. write config/events/<id>.json and register it      (ASF + USGS records, no login)
    2. scripts/fetch_osm_roads.py                         (skipped if the study area has too few roads)
    3. scripts/build_demo_fixture.py                      (needs EARTHDATA_TOKEN in the environment or .env)
    4. scripts/fetch_acquisitions.py
    5. scripts/verify_fixture_hashes.py

Any failure rolls the event back. Earthquakes whose NISAR product is not published yet are re-checked on the
next run for up to --wait-days. State is kept in data/fixtures/auto_ingest_state.json. No value is ever invented:
an event either goes through the full pipeline or is not added.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess  # noqa: S404  (fixed argument lists only, never a shell)
import sys
from pathlib import Path
from typing import Any

from _common import REPO_ROOT, fail
from triagesar.autodiscover import (
    NISAR_PUBLIC_DATA_START,
    AutoDiscoveryError,
    Candidate,
    event_definition,
    event_id_for,
    find_coseismic_granules,
    find_quakes,
)
from triagesar.events import data_dir
from triagesar.nisar.authentication import resolve_credentials
from triagesar.nisar.discovery import DiscoveryError, remote_file_size

STATE_NAME = "auto_ingest_state.json"


def _now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_state(base: Path) -> dict[str, Any]:
    path = base / STATE_NAME
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"last_checked_utc": None, "checked_until": None, "processed": {}, "runs": []}


def save_state(base: Path, state: dict[str, Any]) -> None:
    (base / STATE_NAME).write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def registered(base: Path) -> tuple[dict[str, Any], set[str], set[str], dict[str, str]]:
    """(registry, event ids, USGS ids already covered, granule id -> event id already used)."""
    registry = json.loads((base / "demo_manifest.json").read_text(encoding="utf-8"))
    ids, usgs, granules = set(), set(), {}
    for item in registry.get("events", []):
        ids.add(item["id"])
        cfg = REPO_ROOT / item["event_config"]
        if cfg.is_file():
            definition = json.loads(cfg.read_text(encoding="utf-8"))
            for epi in definition.get("epicentres", []):
                usgs.add(str(epi.get("usgs_id")))
            granule = (definition.get("granule") or {}).get("granule_id")
            if granule:
                granules[granule] = item["id"]
    return registry, ids, usgs, granules


def run_step(script: str, *args: str) -> tuple[bool, str]:
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / script), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=3600, check=False)  # noqa: S603
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
    return proc.returncode == 0, " | ".join(tail)


def count_roads(base: Path, event_id: str) -> int:
    path = base / "infrastructure" / event_id / "roads.geojson"
    return len(json.loads(path.read_text(encoding="utf-8")).get("features", [])) if path.is_file() else 0


def rollback(base: Path, registry: dict[str, Any], event_id: str) -> None:
    registry["events"] = [e for e in registry["events"] if e["id"] != event_id]
    (base / "demo_manifest.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    (REPO_ROOT / "config" / "events" / f"{event_id}.json").unlink(missing_ok=True)
    for sub in ("nisar", "infrastructure"):
        shutil.rmtree(base / sub / event_id, ignore_errors=True)


def ingest(base: Path, registry: dict[str, Any], cand: Candidate, event_id: str, min_roads: int) -> tuple[str, str]:
    """Run the full pipeline for one candidate. Returns (status, detail)."""
    size = remote_file_size(cand.download_url) if cand.download_url else None
    definition = event_definition(cand, event_id, dt.date.today(), size)
    (REPO_ROOT / "config" / "events" / f"{event_id}.json").write_text(
        json.dumps(definition, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    registry["events"].append(
        {
            "id": event_id,
            "event_config": f"config/events/{event_id}.json",
            "nisar_dir": f"nisar/{event_id}",
            "infrastructure_dir": f"infrastructure/{event_id}",
        }
    )
    (base / "demo_manifest.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    ok, detail = run_step("fetch_osm_roads.py", "--event", event_id)
    if not ok:
        rollback(base, registry, event_id)
        return "retry", f"road extract failed: {detail}"
    roads = count_roads(base, event_id)
    if roads < min_roads:
        rollback(base, registry, event_id)
        return "skipped", f"only {roads} mapped road ways in the study area (fewer than {min_roads}; likely offshore)"
    for script, args in (
        ("build_demo_fixture.py", ("--event", event_id)),
        ("fetch_acquisitions.py", ("--event", event_id)),
        ("verify_fixture_hashes.py", ()),
    ):
        ok, detail = run_step(script, *args)
        if not ok:
            rollback(base, registry, event_id)
            return "retry", f"{script} failed: {detail}"
    return "added", f"{roads} road ways; granule {cand.granule_id}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=dt.date.fromisoformat, help="first earthquake date (default: resume from state)")
    ap.add_argument("--until", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--min-magnitude", type=float, default=6.0)
    ap.add_argument("--max-depth", type=float, default=40.0)
    ap.add_argument("--max-new", type=int, default=3, help="at most this many new case studies per run")
    ap.add_argument("--min-roads", type=int, default=25, help="skip study areas with fewer mapped road ways")
    ap.add_argument("--wait-days", type=int, default=60, help="keep re-checking unpublished events this long")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    base = data_dir()
    state = load_state(base)
    registry, ids, covered, used_granules = registered(base)
    resume = state.get("checked_until")
    pending = {k for k, v in state["processed"].items() if v.get("status") in ("waiting", "retry")}
    # Resume from the last check, looking back --wait-days so late-published products are still found.
    since = args.since or (
        dt.date.fromisoformat(resume) - dt.timedelta(days=args.wait_days) if resume else NISAR_PUBLIC_DATA_START
    )
    since = max(since, NISAR_PUBLIC_DATA_START)
    if not args.dry_run and not resolve_credentials(REPO_ROOT / ".env").available:
        fail("Earthdata credentials are needed to build fixtures (EARTHDATA_TOKEN in the environment or .env). "
             "Use --dry-run to list candidates without them.", 2)
    try:
        quakes = find_quakes(since, args.until, args.min_magnitude, args.max_depth)
    except AutoDiscoveryError as exc:
        fail(str(exc))
    print(f"USGS: {len(quakes)} earthquake(s) M>={args.min_magnitude:g}, depth<={args.max_depth:g} km, {since} to {args.until}")

    added: list[str] = []
    for q in quakes:
        prior = state["processed"].get(q.usgs_id, {})
        if q.usgs_id in covered:
            continue
        if prior.get("status") in ("added", "skipped") and q.usgs_id not in pending:
            continue
        label = f"M {q.magnitude:g} {q.place} ({q.date})"
        try:
            cands = find_coseismic_granules(q)
        except DiscoveryError as exc:
            print(f"  ? {label}: ASF search failed ({exc}); will retry")
            continue
        if not cands:
            age = (args.until - q.date).days
            status = "waiting" if age <= args.wait_days else "skipped"
            reason = "no NISAR interferogram spanning the event published yet" if status == "waiting" else (
                f"no NISAR interferogram spanning the event after {age} days")
            print(f"  - {label}: {reason}")
            if not args.dry_run:
                state["processed"][q.usgs_id] = {"status": status, "reason": reason, "checked_utc": _now()}
            continue
        best = cands[0]
        if best.granule_id in used_granules:
            # An aftershock or nearby event already covered by the same interferogram: not a new case study.
            reason = f"same NISAR interferogram as case study {used_granules[best.granule_id]}"
            print(f"  = {label}: {reason}")
            if not args.dry_run:
                state["processed"][q.usgs_id] = {"status": "skipped", "reason": reason, "checked_utc": _now()}
            continue
        event_id = event_id_for(q, ids)
        print(f"  + {label}: {best.granule_id}")
        print(f"      {best.collection}, {best.reference} -> {best.secondary} ({best.baseline_days} d), "
              f"covers {best.aoi_coverage:.0%} of the study area; id {event_id}")
        if args.dry_run:
            used_granules[best.granule_id] = event_id
            continue
        if len(added) >= args.max_new:
            print("      (limit reached for this run; will be considered next time)")
            continue
        status, detail = ingest(base, registry, best, event_id, args.min_roads)
        print(f"      -> {status}: {detail}")
        state["processed"][q.usgs_id] = {"status": status, "reason": detail, "event_id": event_id if status == "added" else None,
                                         "granule_id": best.granule_id, "checked_utc": _now()}
        if status == "added":
            added.append(event_id)
            ids.add(event_id)
            used_granules[best.granule_id] = event_id
    if args.dry_run:
        print("Dry run: nothing was written.")
        return
    state["last_checked_utc"] = _now()
    state["checked_until"] = args.until.isoformat()
    state["runs"] = ([{"utc": state["last_checked_utc"], "added": added, "quakes_checked": len(quakes)}] + state.get("runs", []))[:20]
    save_state(base, state)
    print(f"Added {len(added)} case stud{'y' if len(added) == 1 else 'ies'}: {', '.join(added) or 'none'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Record the NISAR acquisitions of an event's track and frame around the event (ASF Search API, no login).

    python scripts/fetch_acquisitions.py --event venezuela-2026-06-24 [--days 40]

Writes an ``acquisitions`` list into the event definition: every reference or secondary acquisition date of
a GUNW product on the same track and frame within +/- ``days`` of the event, marking the two used here.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re

import requests

from _common import REPO_ROOT, fail
from triagesar.events import get_event
from triagesar.nisar.discovery import ASF_SEARCH_URL, USER_AGENT

_DATES = re.compile(r"_(\d{8})T\d{6}_\d{8}T\d{6}_(\d{8})T\d{6}_")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--event", required=True)
    ap.add_argument("--days", type=int, default=40)
    args = ap.parse_args()
    entry = get_event(args.event)
    if entry is None or entry.data_kind != "nasa_nisar_gunw":
        fail(f"Unknown event: {args.event}")
    d = entry.definition
    g = d["granule"]
    t = dt.datetime.fromisoformat(d["event_time_utc"].replace("Z", "+00:00"))
    params = {
        "dataset": "NISAR",
        "processingLevel": "GUNW",
        "relativeOrbit": g["track"],
        "frame": g["frame"],
        "start": (t - dt.timedelta(days=args.days)).strftime("%Y-%m-%dT00:00:00Z"),
        "end": (t + dt.timedelta(days=args.days)).strftime("%Y-%m-%dT23:59:59Z"),
        "output": "jsonlite",
        "maxResults": "500",
    }
    try:
        resp = requests.get(ASF_SEARCH_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=90)
        resp.raise_for_status()
        results = resp.json()["results"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        fail(f"ASF search failed: {exc}")
    used = _DATES.search(g["granule_id"])
    used_dates = {used.group(1), used.group(2)} if used else set()
    dates: set[str] = set()
    for item in results:
        m = _DATES.search(item.get("granuleName") or "")
        if m and item.get("fileName", "").endswith(".h5"):
            dates.update(m.groups())
    lo, hi = (t - dt.timedelta(days=args.days)).strftime("%Y%m%d"), (t + dt.timedelta(days=args.days)).strftime("%Y%m%d")
    acquisitions = [
        {"date": f"{s[:4]}-{s[4:6]}-{s[6:]}", "used": s in used_dates}
        for s in sorted(dates | used_dates)
        if lo <= s <= hi or s in used_dates
    ]
    d["acquisitions"] = acquisitions
    d["acquisitions_source"] = (
        f"ASF Search API, NISAR GUNW products on track {g['track']}, frame {g['frame']}, "
        f"retrieved {dt.date.today().isoformat()}"
    )
    path = REPO_ROOT / "config" / "events" / f"{entry.id}.json"
    path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    print(f"{entry.id}: {len(acquisitions)} acquisitions ({sum(1 for a in acquisitions if a['used'])} used)")


if __name__ == "__main__":
    main()

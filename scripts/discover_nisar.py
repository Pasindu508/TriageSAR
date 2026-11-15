#!/usr/bin/env python
"""Search the ASF catalogue for NISAR products (no credentials needed).

    python scripts/discover_nisar.py --bbox WEST SOUTH EAST NORTH --start YYYY-MM-DD --end YYYY-MM-DD --product GUNW
"""

from __future__ import annotations

import argparse
import json

from _common import fail
from triagesar.nisar.discovery import ALLOWED_PRODUCTS, DiscoveryError, search_granules


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--product", default="GUNW", choices=ALLOWED_PRODUCTS)
    ap.add_argument("--max-results", type=int, default=250)
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args()
    try:
        records = search_granules(tuple(args.bbox), args.start, args.end, args.product, args.max_results)
    except (ValueError, DiscoveryError) as exc:
        fail(str(exc))
    if args.json:
        print(json.dumps([r.to_dict() for r in records], indent=2))
        return
    print(f"{len(records)} NISAR {args.product} granule(s) from the ASF Search API\n")
    for r in records:
        size = "size not provided" if r.size_mb is None else f"{r.size_mb:.0f} MB"
        print(r.granule_id)
        print(f"  level: {r.processing_level}   collection: {r.collection}   version: {r.pge_version or 'not provided'}")
        print(f"  reference: {r.reference_start_utc}   secondary: {r.secondary_start_utc or 'n/a'}")
        print(f"  pass: {r.flight_direction}   track: {r.track}   frame: {r.frame}   {size}")
        print(f"  footprint: {r.footprint_wkt}")
        print(f"  download: {r.download_url}\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Download one NISAR granule with NASA Earthdata Login (streamed, resumable, never logs secrets).

    python scripts/download_nisar.py --event venezuela-2026-06-24 --out data/raw
    python scripts/download_nisar.py --url https://nisar.asf.earthdatacloud.nasa.gov/... --out data/raw

Building the demo fixture does NOT require this: scripts/build_demo_fixture.py can crop the
remote file through HTTP range requests. Use this script when you want the whole product.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from urllib.parse import urlparse

import requests

from _common import REPO_ROOT, fail
from triagesar.events import get_event
from triagesar.nisar.authentication import AuthenticationError, bearer_token, resolve_credentials
from triagesar.nisar.discovery import USER_AGENT, remote_file_size

ALLOWED_HOST_SUFFIXES = (".earthdatacloud.nasa.gov", ".asf.alaska.edu")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--event", help="event id whose configured granule should be downloaded")
    src.add_argument("--url", help="download URL returned by scripts/discover_nisar.py")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "raw")
    args = ap.parse_args()

    url = args.url
    if args.event:
        entry = get_event(args.event)
        if entry is None or "granule" not in entry.definition:
            fail(f"Unknown event or event without a configured granule: {args.event}")
        url = entry.definition["granule"]["download_url"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(ALLOWED_HOST_SUFFIXES):
        fail("Only https URLs on NASA Earthdata Cloud / ASF hosts are accepted")
    try:
        token = bearer_token(resolve_credentials(REPO_ROOT / ".env"))
    except AuthenticationError as exc:
        fail(str(exc), code=2)

    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / Path(parsed.path).name
    part = target.with_suffix(target.suffix + ".part")
    size = remote_file_size(url)
    free = shutil.disk_usage(args.out).free
    have = part.stat().st_size if part.exists() else 0
    if size is not None and free < (size - have) + 500 * 1024 * 1024:
        fail(f"Not enough free disk space: need {(size - have) / 1e9:.1f} GB plus headroom, have {free / 1e9:.1f} GB. "
             "Use scripts/build_demo_fixture.py without --source to crop the remote file instead.")
    if target.exists() and size is not None and target.stat().st_size == size:
        print(f"Already downloaded: {target}")
        return

    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    if have:
        headers["Range"] = f"bytes={have}-"
    with requests.get(url, headers=headers, stream=True, timeout=(30, 120)) as resp:
        if resp.status_code in (401, 403):
            fail("Earthdata Login rejected the credentials for this download (have you accepted the ASF EULA?)", code=2)
        if resp.status_code not in (200, 206):
            fail(f"Download failed with HTTP {resp.status_code}")
        mode = "ab" if resp.status_code == 206 else "wb"
        done = have if resp.status_code == 206 else 0
        with part.open(mode) as fh:
            for chunk in resp.iter_content(chunk_size=4 * 1024 * 1024):
                fh.write(chunk)
                done += len(chunk)
                if size:
                    print(f"\r{done / 1e6:,.0f} / {size / 1e6:,.0f} MB", end="", flush=True)
    print()
    part.rename(target)
    print(f"Saved {target}")


if __name__ == "__main__":
    main()

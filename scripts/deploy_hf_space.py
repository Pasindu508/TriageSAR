#!/usr/bin/env python
"""Publish TriageSAR to a Hugging Face Space (Docker SDK). Hugging Face builds and hosts the image.

    .venv/bin/hf auth login                      # once; paste a token with write access
    python scripts/deploy_hf_space.py             # creates/updates <your-user>/TriageSAR
    python scripts/deploy_hf_space.py --space-id someone/TriageSAR --private

Uploads exactly the files tracked by git (so .env, credentials and local caches are never sent), with
docker/Dockerfile placed at the root as the Space expects and a short Space README carrying the metadata.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess  # noqa: S404  (fixed argument list, no shell)
import tempfile
from pathlib import Path

from _common import REPO_ROOT, fail

GITHUB_URL = "https://github.com/Pasindu508/TriageSAR"
SPACE_README = """---
title: TriageSAR
emoji: 🛰️
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 8000
pinned: false
license: apache-2.0
short_description: NISAR ground motion to a road inspection queue
---

# TriageSAR

From NASA–ISRO NISAR surface motion to an evidence-ranked infrastructure inspection queue.
NASA Space Apps Challenge 2026, "Dancing with the SARs".

**This is not a damage assessment.** TriageSAR ranks where satellite-observed ground motion meets roads so people
can decide where to inspect first.

Source code, documentation and data provenance: {github}

NISAR data: NASA/ISRO via ASF DAAC · Roads: © OpenStreetMap contributors (ODbL) · Earthquakes: USGS.
"""


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True)  # noqa: S603, S607
    return [f for f in out.stdout.decode().split("\0") if f]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space-id", help="owner/name (default: <your user>/TriageSAR)")
    ap.add_argument("--private", action="store_true", help="create the Space as private")
    ap.add_argument("--message", default="Deploy TriageSAR")
    args = ap.parse_args()
    try:
        from huggingface_hub import HfApi
        from huggingface_hub.errors import HfHubHTTPError
    except ImportError:
        fail("huggingface_hub is not installed: .venv/bin/pip install huggingface_hub")
    api = HfApi()
    try:
        user = api.whoami()["name"]
    except Exception:  # noqa: BLE001
        fail("Not logged in to Hugging Face. Run: .venv/bin/hf auth login", 2)
    space_id = args.space_id or f"{user}/TriageSAR"
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True)  # noqa: S603, S607
    if dirty.stdout.strip():
        print("warning: uncommitted changes are NOT deployed; only files as tracked by git (working-tree copies) are uploaded")

    with tempfile.TemporaryDirectory(prefix="triagesar-space-") as tmp:
        stage = Path(tmp)
        for rel in tracked_files():
            src = REPO_ROOT / rel
            if src.is_file():
                dst = stage / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        shutil.copy2(REPO_ROOT / "README.md", stage / "PROJECT_README.md")
        (stage / "README.md").write_text(SPACE_README.format(github=GITHUB_URL), encoding="utf-8")
        shutil.copy2(REPO_ROOT / "docker" / "Dockerfile", stage / "Dockerfile")
        try:
            api.create_repo(space_id, repo_type="space", space_sdk="docker", private=args.private, exist_ok=True)
            api.upload_folder(
                folder_path=str(stage),
                repo_id=space_id,
                repo_type="space",
                commit_message=args.message,
                delete_patterns=["*"],  # the Space mirrors the repository exactly
            )
        except HfHubHTTPError as exc:
            fail(f"Hugging Face rejected the upload: {exc}")
    owner, name = space_id.split("/", 1)
    print(f"Uploaded. Build progress: https://huggingface.co/spaces/{space_id}")
    print(f"App URL once built:      https://{owner.lower()}-{name.lower().replace('_', '-')}.hf.space")


if __name__ == "__main__":
    main()

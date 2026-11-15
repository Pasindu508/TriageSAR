"""Shared helpers for the command-line scripts."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "science", REPO_ROOT):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def fail(message: str, code: int = 1) -> NoReturn:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def quoted_command() -> str:
    """The command line as typed, for provenance. Arguments never include credentials."""
    import shlex

    return "python " + " ".join(shlex.quote(a) for a in [Path(sys.argv[0]).as_posix().replace(REPO_ROOT.as_posix() + "/", ""), *sys.argv[1:]])

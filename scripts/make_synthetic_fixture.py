#!/usr/bin/env python
"""Create the TEST ONLY synthetic event used by automated tests and UI development.

The output goes to .cache/synthetic (never to data/fixtures). The API only serves it when
TRIAGESAR_INCLUDE_SYNTHETIC=1, and the UI then shows a permanent "synthetic test data" banner.
"""

from __future__ import annotations

from _common import REPO_ROOT  # noqa: F401  (adds the repository root to sys.path)
from tests.support.synthetic import TEST_ONLY_NOTE, build_synthetic_event
from triagesar.events import synthetic_dir


def main() -> None:
    fixture_dir, infra_dir, _ = build_synthetic_event(synthetic_dir())
    print(f"{TEST_ONLY_NOTE}\n  fixture: {fixture_dir}\n  roads  : {infra_dir}")


if __name__ == "__main__":
    main()

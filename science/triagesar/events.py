"""Event registry: which demo events exist and whether their real-data fixture has been built."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import REPO_ROOT
from .provenance.manifest import MANIFEST_NAME

EVENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SYNTHETIC_EVENT_ID = "synthetic-test-event"


@dataclass(frozen=True)
class EventEntry:
    id: str
    definition: dict[str, Any]
    nisar_dir: Path
    infrastructure_dir: Path
    data_kind: str  # "nasa_nisar_gunw" or "synthetic_test"

    @property
    def fixture_ready(self) -> bool:
        return (self.nisar_dir / MANIFEST_NAME).is_file()

    @property
    def roads_path(self) -> Path:
        return self.infrastructure_dir / "roads.geojson"

    @property
    def places_path(self) -> Path:
        return self.infrastructure_dir / "places.geojson"


def data_dir() -> Path:
    return Path(os.environ.get("TRIAGESAR_DATA_DIR") or REPO_ROOT / "data" / "fixtures").resolve()


def synthetic_dir() -> Path:
    return Path(os.environ.get("TRIAGESAR_SYNTHETIC_DIR") or REPO_ROOT / ".cache" / "synthetic").resolve()


def include_synthetic() -> bool:
    return os.environ.get("TRIAGESAR_INCLUDE_SYNTHETIC", "").strip().lower() in {"1", "true", "yes"}


def load_event_definition(path: Path) -> dict[str, Any]:
    definition = json.loads(Path(path).read_text(encoding="utf-8"))
    if not EVENT_ID_RE.match(str(definition.get("id", ""))):
        raise ValueError(f"Event definition {path} has an invalid id")
    return definition


def list_events(base: Path | None = None) -> list[EventEntry]:
    """Events from ``demo_manifest.json`` (real data only) plus, when explicitly enabled, the synthetic test event."""
    base = base or data_dir()
    entries: list[EventEntry] = []
    registry = base / "demo_manifest.json"
    if registry.is_file():
        for item in json.loads(registry.read_text(encoding="utf-8")).get("events", []):
            event_id = str(item["id"])
            if not EVENT_ID_RE.match(event_id):
                raise ValueError(f"Invalid event id in {registry}: {event_id!r}")
            definition = load_event_definition(REPO_ROOT / item["event_config"])
            entries.append(
                EventEntry(event_id, definition, base / item["nisar_dir"], base / item["infrastructure_dir"], "nasa_nisar_gunw")
            )
    if include_synthetic():
        root = synthetic_dir()
        entries.append(
            EventEntry(
                SYNTHETIC_EVENT_ID,
                {
                    "id": SYNTHETIC_EVENT_ID,
                    "title": "SYNTHETIC TEST EVENT (not real)",
                    "summary": "TEST ONLY - synthetic values, not NASA observations. Used for automated tests and UI development.",
                },
                root / "nisar" / SYNTHETIC_EVENT_ID,
                root / "infrastructure" / SYNTHETIC_EVENT_ID,
                "synthetic_test",
            )
        )
    return entries


def get_event(event_id: str, base: Path | None = None) -> EventEntry | None:
    if not EVENT_ID_RE.match(event_id):
        return None
    return next((e for e in list_events(base) if e.id == event_id), None)

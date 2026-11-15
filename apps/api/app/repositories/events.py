"""Read-only access to event definitions, fixtures and cached infrastructure extracts.

Event ids are validated against the registry; no request parameter is ever used to build a file path.
"""

from __future__ import annotations

import json
from typing import Any

from app.models.errors import EventNotFound
from triagesar.events import EventEntry, data_dir, get_event, list_events


def all_events() -> list[EventEntry]:
    return list_events()


def require_event(event_id: str) -> EventEntry:
    entry = get_event(event_id)
    if entry is None:
        raise EventNotFound(f"No event with id {event_id!r}.")
    return entry


def read_geojson(entry: EventEntry, which: str) -> dict[str, Any]:
    path = entry.roads_path if which == "roads" else entry.places_path
    if not path.is_file():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def read_osm_manifest(entry: EventEntry) -> dict[str, Any] | None:
    path = entry.infrastructure_dir / "osm_manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def read_auto_ingest_state() -> dict[str, Any] | None:
    """State written by scripts/auto_ingest.py, or None if it has never run against this data directory."""
    path = data_dir() / "auto_ingest_state.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except ValueError:
        return None

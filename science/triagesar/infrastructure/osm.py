"""OpenStreetMap road extraction through the Overpass API, with a file cache.

The public demo never calls Overpass: it reads the cached GeoJSON extract in
``data/fixtures/infrastructure``. OSM data are (c) OpenStreetMap contributors,
licensed under the ODbL 1.0.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import LineString

from ..processing.georeference import validate_bbox_wgs84

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "TriageSAR/0.1 (open-source NASA Space Apps 2026 research prototype)"
OSM_ATTRIBUTION = "© OpenStreetMap contributors, ODbL 1.0"
OSM_LICENCE_URL = "https://www.openstreetmap.org/copyright"
_MIN_INTERVAL_S = 5.0
_last_request_at = 0.0


class InfrastructureType(StrEnum):
    """Typed abstraction for future asset classes. The MVP ranks roads only."""

    ROAD = "road"
    BRIDGE = "bridge"
    HOSPITAL = "hospital"
    SCHOOL = "school"
    UTILITY = "utility"
    OTHER = "other"


class OverpassError(RuntimeError):
    """Overpass could not be reached or returned an unusable response."""


@dataclass(frozen=True)
class Road:
    osm_id: int
    highway: str
    name: str | None
    ref: str | None
    bridge: bool
    tunnel: bool
    geometry: LineString  # WGS84 lon/lat

    @property
    def base_class(self) -> str:
        return self.highway.removesuffix("_link")


def build_query(bbox_wgs84: tuple[float, float, float, float], highway_classes: tuple[str, ...], timeout_s: int) -> str:
    w, s, e, n = validate_bbox_wgs84(bbox_wgs84)
    for cls in highway_classes:
        if not cls.replace("_", "").isalpha():
            raise ValueError(f"Invalid highway class: {cls!r}")
    classes = "|".join(sorted({*highway_classes, *(f"{c}_link" for c in highway_classes)}))
    bbox = f"{s:.6f},{w:.6f},{n:.6f},{e:.6f}"
    return (
        f"[out:json][timeout:{int(timeout_s)}];\n"
        f"(\n"
        f'  way["highway"~"^({classes})$"]({bbox});\n'
        f'  node["place"~"^(city|town)$"]({bbox});\n'
        f");\n"
        f"out geom tags;"
    )


def fetch_overpass(
    query: str,
    cache_dir: Path,
    url: str | None = None,
    timeout_s: int = 180,
    use_cache: bool = True,
) -> dict[str, Any]:
    """POST a query to Overpass with caching, a timeout, a polite rate limit and clear errors."""
    global _last_request_at
    endpoint = url or os.environ.get("TRIAGESAR_OVERPASS_URL", DEFAULT_OVERPASS_URL)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((endpoint + "\n" + query).encode()).hexdigest()[:24]
    cache_file = cache_dir / f"overpass_{key}.json"
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    wait = _MIN_INTERVAL_S - (time.monotonic() - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = requests.post(
            endpoint, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=(15, timeout_s + 30)
        )
    except requests.RequestException as exc:
        raise OverpassError(f"Could not reach Overpass at {endpoint}: {type(exc).__name__}") from exc
    finally:
        _last_request_at = time.monotonic()
    if resp.status_code in (429, 504):
        raise OverpassError(f"Overpass is busy (HTTP {resp.status_code}); wait a minute and retry")
    if resp.status_code != 200:
        raise OverpassError(f"Overpass returned HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise OverpassError("Overpass returned a non-JSON response") from exc
    if "elements" not in payload:
        raise OverpassError("Overpass response has no 'elements'")
    if payload.get("remark"):
        raise OverpassError(f"Overpass reported a problem: {payload['remark']}")
    cache_file.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def overpass_to_geojson(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert an Overpass response to (roads FeatureCollection, places FeatureCollection)."""
    roads: list[dict[str, Any]] = []
    places: list[dict[str, Any]] = []
    for el in payload.get("elements", []):
        tags = el.get("tags", {})
        if el.get("type") == "way" and "highway" in tags and len(el.get("geometry", [])) >= 2:
            coords = [[round(pt["lon"], 6), round(pt["lat"], 6)] for pt in el["geometry"]]
            props = {
                "osm_id": el["id"],
                "highway": tags["highway"],
                "name": tags.get("name"),
                "ref": tags.get("ref"),
                "bridge": tags.get("bridge") not in (None, "no"),
                "tunnel": tags.get("tunnel") not in (None, "no"),
            }
            roads.append({"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}})
        elif el.get("type") == "node" and "place" in tags and tags.get("name"):
            props = {"osm_id": el["id"], "place": tags["place"], "name": tags["name"]}
            places.append(
                {
                    "type": "Feature",
                    "properties": props,
                    "geometry": {"type": "Point", "coordinates": [round(el["lon"], 6), round(el["lat"], 6)]},
                }
            )
    roads.sort(key=lambda f: f["properties"]["osm_id"])
    places.sort(key=lambda f: f["properties"]["osm_id"])
    return ({"type": "FeatureCollection", "features": roads}, {"type": "FeatureCollection", "features": places})


def load_roads(path: Path, highway_classes: tuple[str, ...] | None = None) -> list[Road]:
    """Load roads from a cached GeoJSON extract."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    allowed = None if highway_classes is None else set(highway_classes)
    roads: list[Road] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        if geom.get("type") != "LineString" or len(geom.get("coordinates", [])) < 2:
            continue
        highway = str(props.get("highway", ""))
        if allowed is not None and highway.removesuffix("_link") not in allowed:
            continue
        roads.append(
            Road(
                osm_id=int(props.get("osm_id", 0)),
                highway=highway,
                name=(props.get("name") or None),
                ref=(props.get("ref") or None),
                bridge=bool(props.get("bridge")),
                tunnel=bool(props.get("tunnel")),
                geometry=LineString(geom["coordinates"]),
            )
        )
    return roads

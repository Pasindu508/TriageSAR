"""Find new earthquakes that NISAR has imaged before and after, so they can be added as case studies.

Two public catalogues are combined, both without credentials:

* the USGS earthquake catalogue (FDSN event service) for significant shallow earthquakes;
* the ASF Search API for NISAR L2 GUNW products whose reference acquisition is before the earthquake and
  whose secondary acquisition is after it, over the epicentre.

Nothing here downloads NISAR data or writes files; ``scripts/auto_ingest.py`` does that.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import requests
from shapely import wkt as shapely_wkt
from shapely.geometry import Point, box

from .nisar.discovery import ASF_SEARCH_URL, USER_AGENT, DiscoveryError

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
NISAR_PUBLIC_DATA_START = dt.date(2026, 6, 17)  # first PROVISIONAL acquisitions released by ASF
_NAME = re.compile(r"_(\d{8}T\d{6})_\d{8}T\d{6}_(\d{8}T\d{6})_\d{8}T\d{6}_")
#: preference order for collections (validated first, urgent-response products last)
COLLECTION_RANK = {"NISAR_L2_GUNW_V1": 0, "NISAR_L2_GUNW_PROVISIONAL_V1": 1}


class AutoDiscoveryError(RuntimeError):
    """A catalogue could not be queried."""


@dataclass(frozen=True)
class Quake:
    usgs_id: str
    magnitude: float
    magnitude_type: str
    place: str
    time: dt.datetime
    lon: float
    lat: float
    depth_km: float
    url: str

    @property
    def date(self) -> dt.date:
        return self.time.date()


@dataclass(frozen=True)
class Candidate:
    quake: Quake
    granule_id: str
    file_name: str
    download_url: str
    collection: str
    concept_id: str | None
    track: int | None
    frame: int | None
    flight_direction: str | None
    footprint_wkt: str
    pge_version: str | None
    reference: dt.date
    secondary: dt.date
    aoi_bbox: tuple[float, float, float, float]
    aoi_coverage: float  # share of the requested study area inside the granule footprint
    reasons: list[str] = field(default_factory=list)

    @property
    def baseline_days(self) -> int:
        return (self.secondary - self.reference).days


def _get_json(url: str, params: dict[str, Any], timeout: float = 90.0) -> Any:
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    except requests.RequestException as exc:
        raise AutoDiscoveryError(f"Could not reach {url}: {type(exc).__name__}") from exc
    if resp.status_code != 200:
        raise AutoDiscoveryError(f"{url} returned HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise AutoDiscoveryError(f"{url} returned a non-JSON response") from exc


def find_quakes(start: dt.date, end: dt.date, min_magnitude: float = 6.0, max_depth_km: float = 40.0) -> list[Quake]:
    """Significant shallow earthquakes in [start, end] from the USGS catalogue, largest first."""
    if end < start:
        raise ValueError("end must not be before start")
    payload = _get_json(
        USGS_URL,
        {
            "format": "geojson",
            "starttime": start.isoformat(),
            "endtime": (end + dt.timedelta(days=1)).isoformat(),
            "minmagnitude": min_magnitude,
            "maxdepth": max_depth_km,
            "eventtype": "earthquake",
            "orderby": "magnitude",
        },
    )
    quakes: list[Quake] = []
    for feat in payload.get("features", []):
        p, g = feat.get("properties") or {}, feat.get("geometry") or {}
        coords = g.get("coordinates") or []
        if len(coords) < 3 or p.get("mag") is None or p.get("time") is None:
            continue
        quakes.append(
            Quake(
                usgs_id=str(feat.get("id")),
                magnitude=float(p["mag"]),
                magnitude_type=str(p.get("magType") or ""),
                place=str(p.get("place") or "unknown location"),
                time=dt.datetime.fromtimestamp(p["time"] / 1000, dt.UTC),
                lon=float(coords[0]),
                lat=float(coords[1]),
                depth_km=float(coords[2]),
                url=str(p.get("url") or f"https://earthquake.usgs.gov/earthquakes/eventpage/{feat.get('id')}"),
            )
        )
    return quakes


def study_area(lon: float, lat: float, half_width: float = 0.575, half_height: float = 0.325) -> tuple[float, float, float, float]:
    """Default study area around an epicentre: about 120 km × 70 km (the size of the original case study)."""
    return (
        round(max(-180.0, lon - half_width), 3),
        round(max(-90.0, lat - half_height), 3),
        round(min(180.0, lon + half_width), 3),
        round(min(90.0, lat + half_height), 3),
    )


def _parse_times(name: str) -> tuple[dt.datetime, dt.datetime] | None:
    """Reference and secondary start times encoded in a GUNW granule name (UTC)."""
    m = _NAME.search(name)
    if not m:
        return None
    fmt = "%Y%m%dT%H%M%S"
    return (
        dt.datetime.strptime(m.group(1), fmt).replace(tzinfo=dt.UTC),
        dt.datetime.strptime(m.group(2), fmt).replace(tzinfo=dt.UTC),
    )


def rank_key(c: Candidate) -> tuple[int, float, int, str]:
    """Best first: validated collection, most of the study area covered, shortest pair, then name."""
    return (COLLECTION_RANK.get(c.collection, 9), -round(c.aoi_coverage, 2), c.baseline_days, c.granule_id)


def find_coseismic_granules(
    quake: Quake, max_baseline_days: int = 48, min_coverage: float = 0.5
) -> list[Candidate]:
    """NISAR GUNW products over the epicentre whose two acquisitions bracket the earthquake, best first."""
    aoi = study_area(quake.lon, quake.lat)
    try:
        payload = _get_json(
            ASF_SEARCH_URL,
            {
                "dataset": "NISAR",
                "processingLevel": "GUNW",
                "intersectsWith": f"POINT({quake.lon} {quake.lat})",
                "start": (quake.time - dt.timedelta(days=max_baseline_days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": quake.time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "output": "jsonlite",
                "maxResults": "500",
            },
        )
    except AutoDiscoveryError as exc:
        raise DiscoveryError(str(exc)) from exc
    aoi_box = box(*aoi)
    epicentre = Point(quake.lon, quake.lat)
    out: list[Candidate] = []
    for item in payload.get("results", []):
        name = str(item.get("granuleName") or "")
        collection = str(item.get("collectionName") or "")
        if not str(item.get("fileName", "")).endswith(".h5") or collection not in COLLECTION_RANK:
            continue  # skips urgent-response (NISAR_UR_*) duplicates and sidecar files
        times = _parse_times(name)
        if times is None:
            continue
        ref_t, sec_t = times
        # The reference must be acquired before the earthquake and the secondary after it.
        if not (ref_t < quake.time < sec_t) or (sec_t - ref_t).days > max_baseline_days:
            continue
        ref, sec = ref_t.date(), sec_t.date()
        try:
            footprint = shapely_wkt.loads(item["wkt"])
        except (KeyError, ValueError, TypeError):
            continue
        if not footprint.contains(epicentre):
            continue
        coverage = footprint.intersection(aoi_box).area / aoi_box.area
        if coverage < min_coverage:
            continue
        clipped = tuple(round(v, 3) for v in footprint.intersection(aoi_box).bounds)
        out.append(
            Candidate(
                quake=quake,
                granule_id=name,
                file_name=str(item["fileName"]),
                download_url=str(item.get("downloadUrl") or ""),
                collection=collection,
                concept_id=item.get("conceptID"),
                track=item.get("path"),
                frame=item.get("frame"),
                flight_direction=item.get("flightDirection"),
                footprint_wkt=str(item["wkt"]),
                pge_version=item.get("pgeVersion"),
                reference=ref,
                secondary=sec,
                aoi_bbox=clipped,  # type: ignore[arg-type]
                aoi_coverage=coverage,
            )
        )
    out.sort(key=rank_key)
    return out


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def region_name(place: str) -> str:
    """'66 km NNW of Ende, Indonesia' -> 'Ende, Indonesia'; 'The 2026 Kumamoto Region, Japan Earthquake' stays readable."""
    text = place.strip()
    if " of " in text:
        text = text.split(" of ", 1)[1]
    text = re.sub(r"(?i)\b(the \d{4} | earthquake)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip(" ,") or "Unknown location"


def event_id_for(quake: Quake, existing: set[str]) -> str:
    """A stable, readable id such as 'indonesia-2026-08-14', made unique against ``existing``."""
    region = region_name(quake.place)
    country = region.split(",")[-1].strip() or region
    base = f"{slugify(country)[:40] or 'event'}-{quake.date.isoformat()}"
    if base not in existing:
        return base
    for suffix in (slugify(region.split(",")[0])[:20], quake.usgs_id.lower()):
        candidate = f"{slugify(country)[:30]}-{suffix}-{quake.date.isoformat()}"
        if suffix and candidate not in existing:
            return candidate[:63]
    raise ValueError(f"Cannot make a unique id for {quake.usgs_id}")


def event_title(quake: Quake) -> str:
    day = f"{quake.date.day} {quake.date.strftime('%B %Y')}"
    return f"{region_name(quake.place)} earthquake, {day}"


def event_definition(c: Candidate, event_id: str, discovered_on: dt.date, size_bytes: int | None) -> dict[str, Any]:
    """Event JSON in the same shape as the hand-written ones, marked as added automatically."""
    q = c.quake
    iso = q.time.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "id": event_id,
        "title": event_title(q),
        "summary": (
            f"Co-event NISAR L-band interferogram ({c.reference.isoformat()} to {c.secondary.isoformat()}) over "
            f"{region_name(q.place)}, spanning the M {q.magnitude:g} earthquake. Added automatically."
        ),
        "event_time_utc": iso,
        "event_source_name": f"USGS Earthquake Hazards Program, event {q.usgs_id} (M {q.magnitude:g} {q.magnitude_type}, {q.place})",
        "event_source_url": q.url,
        "notes": [
            f"Epicentre of {q.usgs_id} (USGS): {abs(q.lat):.4f} {'N' if q.lat >= 0 else 'S'}, "
            f"{abs(q.lon):.4f} {'E' if q.lon >= 0 else 'W'}, depth {q.depth_km:g} km. Catalogue values retrieved "
            f"{discovered_on.isoformat()} and may be revised by USGS.",
            "This case study was added by scripts/auto_ingest.py without manual review; the study area is the default "
            "120 km x 70 km box around the epicentre, clipped to the NISAR frame.",
        ],
        "epicentres": [
            {
                "usgs_id": q.usgs_id,
                "magnitude": q.magnitude,
                "magnitude_type": q.magnitude_type,
                "lon": q.lon,
                "lat": q.lat,
                "time_utc": iso,
                "place": q.place,
            }
        ],
        "aoi_bbox_wgs84": list(c.aoi_bbox),
        "granule": {
            "granule_id": c.granule_id,
            "file_name": c.file_name,
            "collection": c.collection,
            "concept_id": c.concept_id,
            "provider": "NASA Alaska Satellite Facility DAAC (ASF)",
            "download_url": c.download_url,
            "flight_direction": c.flight_direction,
            "frame": c.frame,
            "track": c.track,
            "pge_version": c.pge_version,
            "footprint_wkt": c.footprint_wkt,
            "source_size_bytes": size_bytes,
            "discovered_with": "python scripts/auto_ingest.py",
            "discovered_on": discovered_on.isoformat(),
        },
        "added_by": "auto_ingest",
        "added_on": discovered_on.isoformat(),
    }

"""Genuine NISAR catalogue discovery through the Alaska Satellite Facility (ASF) Search API.

Search needs no credentials. Nothing here returns mocked results: if ASF cannot
be reached a ``DiscoveryError`` is raised.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import asdict, dataclass
from typing import Any

import requests

from ..processing.georeference import validate_bbox_wgs84

ASF_SEARCH_URL = "https://api.daac.asf.alaska.edu/services/search/param"
USER_AGENT = "TriageSAR/0.1 (open-source NASA Space Apps 2026 research prototype)"
ALLOWED_PRODUCTS = ("GUNW", "GCOV", "GSLC", "GOFF", "RUNW", "RIFG", "ROFF", "RSLC")
_NAME_DATES = re.compile(r"_(\d{8}T\d{6})_(\d{8}T\d{6})_(\d{8}T\d{6})_(\d{8}T\d{6})_")


class DiscoveryError(RuntimeError):
    """ASF search failed or returned an unusable response."""


@dataclass(frozen=True)
class GranuleRecord:
    granule_id: str
    file_name: str | None
    processing_level: str | None
    collection: str | None
    concept_id: str | None
    reference_start_utc: str | None
    reference_end_utc: str | None
    secondary_start_utc: str | None
    secondary_end_utc: str | None
    flight_direction: str | None
    track: int | None
    frame: int | None
    polarisation: str | None
    footprint_wkt: str | None
    size_mb: float | None
    download_url: str | None
    pge_version: str | None
    additional_urls: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Dates must be YYYY-MM-DD, got {value!r}") from exc


def _stamp(compact: str) -> str:
    return dt.datetime.strptime(compact, "%Y%m%dT%H%M%S").replace(tzinfo=dt.UTC).isoformat().replace("+00:00", "Z")


def dates_from_granule_name(name: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Reference start/end and secondary start/end encoded in an interferometric granule name."""
    m = _NAME_DATES.search(name)
    if not m:
        return (None, None, None, None)
    a, b, c, d = (_stamp(g) for g in m.groups())
    return (a, b, c, d)


def build_params(bbox: tuple[float, float, float, float], start: str, end: str, product: str, max_results: int) -> dict[str, str]:
    w, s, e, n = validate_bbox_wgs84(bbox)
    d0, d1 = _parse_date(start), _parse_date(end)
    if d1 < d0:
        raise ValueError("end date must not be before start date")
    if product.upper() not in ALLOWED_PRODUCTS:
        raise ValueError(f"product must be one of {', '.join(ALLOWED_PRODUCTS)}")
    if not 1 <= max_results <= 2000:
        raise ValueError("max_results must be between 1 and 2000")
    return {
        "dataset": "NISAR",
        "processingLevel": product.upper(),
        "bbox": f"{w},{s},{e},{n}",
        "start": f"{d0.isoformat()}T00:00:00Z",
        "end": f"{d1.isoformat()}T23:59:59Z",
        "output": "jsonlite",
        "maxResults": str(max_results),
    }


def parse_results(payload: dict[str, Any]) -> list[GranuleRecord]:
    if "results" not in payload or not isinstance(payload["results"], list):
        raise DiscoveryError("ASF response has no 'results' list")
    records: list[GranuleRecord] = []
    for item in payload["results"]:
        file_name = item.get("fileName")
        if file_name and not str(file_name).endswith(".h5"):
            continue
        name = item.get("granuleName") or item.get("productID") or file_name
        if not name:
            continue
        ref0, ref1, sec0, sec1 = dates_from_granule_name(str(name))
        nisar = item.get("nisar") or {}
        size = item.get("sizeMB")
        records.append(
            GranuleRecord(
                granule_id=str(name),
                file_name=file_name,
                processing_level=item.get("productType") or item.get("productTypeDisplay"),
                collection=item.get("collectionName"),
                concept_id=item.get("conceptID"),
                reference_start_utc=ref0 or item.get("startTime"),
                reference_end_utc=ref1 or item.get("stopTime"),
                secondary_start_utc=sec0,
                secondary_end_utc=sec1,
                flight_direction=item.get("flightDirection"),
                track=item.get("track") or item.get("path"),
                frame=item.get("frame"),
                polarisation=item.get("polarization"),
                footprint_wkt=item.get("wkt"),
                size_mb=float(size) if size not in (None, "") else None,
                download_url=item.get("downloadUrl"),
                pge_version=item.get("pgeVersion"),
                additional_urls=tuple(nisar.get("additionalUrls") or ()),
            )
        )
    records.sort(key=lambda r: (r.reference_start_utc or "", r.granule_id))
    return records


def search_granules(
    bbox: tuple[float, float, float, float],
    start: str,
    end: str,
    product: str = "GUNW",
    max_results: int = 250,
    timeout_s: float = 60.0,
) -> list[GranuleRecord]:
    """Query ASF for NISAR granules intersecting ``bbox`` whose acquisition falls in the date range."""
    params = build_params(bbox, start, end, product, max_results)
    try:
        resp = requests.get(ASF_SEARCH_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout_s)
    except requests.RequestException as exc:
        raise DiscoveryError(f"Could not reach the ASF Search API: {type(exc).__name__}") from exc
    if resp.status_code != 200:
        raise DiscoveryError(f"ASF Search API returned HTTP {resp.status_code}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise DiscoveryError("ASF Search API returned a non-JSON response") from exc
    return parse_results(payload)


def remote_file_size(url: str, timeout_s: float = 60.0) -> int | None:
    """Size in bytes from an unauthenticated HEAD request, when the server provides it."""
    try:
        resp = requests.head(url, allow_redirects=True, headers={"User-Agent": USER_AGENT}, timeout=timeout_s)
    except requests.RequestException:
        return None
    length = resp.headers.get("content-length")
    return int(length) if resp.status_code == 200 and length and length.isdigit() and int(length) > 0 else None

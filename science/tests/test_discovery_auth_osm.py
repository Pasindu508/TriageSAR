"""Discovery, authentication and Overpass client tests. Network calls are mocked, except the
tests marked ``integration`` which are skipped unless TRIAGESAR_RUN_INTEGRATION=1."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import requests

from triagesar.infrastructure import osm
from triagesar.nisar import authentication as auth
from triagesar.nisar import discovery as disc

# Trimmed copy of a real ASF Search API record (retrieved 14 Nov 2026), used only to test parsing.
GRANULE = (
    "NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_"
    "20260625T100655_20260625T100730_P05023_N_F_J_001"
)
ASF_SAMPLE = {
    "results": [
        {
            "granuleName": GRANULE,
            "fileName": GRANULE + ".h5",
            "collectionName": "NISAR_L2_GUNW_PROVISIONAL_V1",
            "conceptID": "C2854335566-ASF",
            "productType": "GUNW",
            "flightDirection": "ASCENDING",
            "frame": 7,
            "path": 162,
            "pgeVersion": "R05.02.3",
            "sizeMB": None,
            "startTime": "2026-06-13T10:06:56Z",
            "wkt": "POLYGON ((-66.84927 10.06663, -67.34953 12.21377, -69.60483 11.68027, -69.08281 9.5437, -66.84927 10.06663))",
            "downloadUrl": f"https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GUNW_PROVISIONAL_V1/{GRANULE}/{GRANULE}.h5",
            "nisar": {"additionalUrls": ["https://example.invalid/x.iso.xml"]},
        },
        {"granuleName": GRANULE, "fileName": GRANULE + ".iso.xml"},
    ]
}


class FakeResponse:
    def __init__(self, status: int = 200, payload: Any = None, headers: dict[str, str] | None = None) -> None:
        self.status_code, self._payload, self.headers = status, payload, headers or {}

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_build_params_validates_inputs() -> None:
    p = disc.build_params((-68.5, 9.5, -65.5, 11.5), "2026-06-10", "2026-07-05", "gunw", 50)
    assert p["dataset"] == "NISAR" and p["processingLevel"] == "GUNW" and p["bbox"] == "-68.5,9.5,-65.5,11.5"
    assert p["start"] == "2026-06-10T00:00:00Z" and p["end"] == "2026-07-05T23:59:59Z"
    for bad in [
        ((-65.0, 9.5, -68.0, 11.5), "2026-06-10", "2026-07-05", "GUNW", 50),
        ((-68.5, 9.5, -65.5, 11.5), "10/06/2026", "2026-07-05", "GUNW", 50),
        ((-68.5, 9.5, -65.5, 11.5), "2026-07-05", "2026-06-10", "GUNW", 50),
        ((-68.5, 9.5, -65.5, 11.5), "2026-06-10", "2026-07-05", "GUNW; rm -rf", 50),
        ((-68.5, 9.5, -65.5, 11.5), "2026-06-10", "2026-07-05", "GUNW", 0),
    ]:
        with pytest.raises(ValueError):
            disc.build_params(*bad)  # type: ignore[arg-type]


def test_parse_results_extracts_dates_from_granule_name() -> None:
    (rec,) = disc.parse_results(ASF_SAMPLE)
    assert rec.granule_id == GRANULE and rec.processing_level == "GUNW" and rec.frame == 7 and rec.track == 162
    assert rec.reference_start_utc == "2026-06-13T10:06:56Z" and rec.secondary_start_utc == "2026-06-25T10:06:55Z"
    assert rec.size_mb is None and rec.pge_version == "R05.02.3" and rec.download_url.endswith(".h5")  # type: ignore[union-attr]
    with pytest.raises(disc.DiscoveryError):
        disc.parse_results({"unexpected": 1})


def test_search_reports_failures_instead_of_inventing_results(monkeypatch: pytest.MonkeyPatch) -> None:
    args = ((-68.5, 9.5, -65.5, 11.5), "2026-06-10", "2026-07-05")

    def boom(*a: Any, **k: Any) -> Any:
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(disc.requests, "get", boom)
    with pytest.raises(disc.DiscoveryError, match="Could not reach"):
        disc.search_granules(*args)
    monkeypatch.setattr(disc.requests, "get", lambda *a, **k: FakeResponse(503))
    with pytest.raises(disc.DiscoveryError, match="HTTP 503"):
        disc.search_granules(*args)
    monkeypatch.setattr(disc.requests, "get", lambda *a, **k: FakeResponse(200, ASF_SAMPLE))
    assert [r.granule_id for r in disc.search_granules(*args)] == [GRANULE]


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("TRIAGESAR_RUN_INTEGRATION") != "1", reason="set TRIAGESAR_RUN_INTEGRATION=1 to query ASF")
def test_live_asf_search_finds_the_demo_granule() -> None:
    records = disc.search_granules((-68.5, 9.5, -65.5, 11.5), "2026-06-10", "2026-07-05", "GUNW")
    assert GRANULE in {r.granule_id for r in records}


def test_credentials_resolution_order_and_secrecy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("EARTHDATA_TOKEN", "EARTHDATA_USERNAME", "EARTHDATA_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    empty_netrc = tmp_path / "netrc"
    empty_netrc.write_text("")
    none = auth.resolve_credentials(tmp_path / "missing.env", empty_netrc)
    assert not none.available and none.source == "none"
    with pytest.raises(auth.AuthenticationError, match="urs.earthdata.nasa.gov"):
        auth.bearer_token(none)

    dotenv = tmp_path / ".env"
    dotenv.write_text("# comment\nEARTHDATA_USERNAME=someone\nEARTHDATA_PASSWORD='s3cret-value'\n")
    from_file = auth.resolve_credentials(dotenv, empty_netrc)
    assert from_file.available and from_file.source == ".env" and from_file.username == "someone"
    assert "s3cret-value" not in repr(from_file) and "someone" not in repr(from_file)

    monkeypatch.setenv("EARTHDATA_TOKEN", "tok-123")
    from_env = auth.resolve_credentials(dotenv, empty_netrc)
    assert from_env.source == "environment" and auth.bearer_token(from_env) == "tok-123"
    assert "tok-123" not in repr(from_env) and "tok-123" not in str(from_env)

    monkeypatch.delenv("EARTHDATA_TOKEN")
    netrc_file = tmp_path / "netrc2"
    netrc_file.write_text("machine urs.earthdata.nasa.gov login nuser password npass\n")
    netrc_file.chmod(0o600)
    assert auth.resolve_credentials(tmp_path / "missing.env", netrc_file).source == "netrc"


def test_password_is_exchanged_for_token_and_errors_do_not_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    creds = auth.EarthdataCredentials(username="u", password="p-secret", source="environment")
    monkeypatch.setattr(auth.requests, "post", lambda *a, **k: FakeResponse(200, {"access_token": "abc"}))
    assert auth.bearer_token(creds) == "abc"
    monkeypatch.setattr(auth.requests, "post", lambda *a, **k: FakeResponse(401))
    with pytest.raises(auth.AuthenticationError) as err:
        auth.bearer_token(creds)
    assert "p-secret" not in str(err.value)


def test_overpass_query_conversion_cache_and_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    query = osm.build_query((-68.1, 10.05, -66.95, 10.7), ("motorway", "primary"), 60)
    assert "10.050000,-68.100000,10.700000,-66.950000" in query and "motorway_link" in query and "[timeout:60]" in query
    with pytest.raises(ValueError):
        osm.build_query((-68.1, 10.05, -66.95, 10.7), ('primary"];evil', ), 60)

    payload = {
        "osm3s": {"timestamp_osm_base": "2026-11-14T00:00:00Z"},
        "elements": [
            {"type": "way", "id": 2, "tags": {"highway": "primary", "name": "B", "bridge": "yes"},
             "geometry": [{"lat": 10.1, "lon": -67.5}, {"lat": 10.2, "lon": -67.4}]},
            {"type": "way", "id": 1, "tags": {"highway": "motorway_link"}, "geometry": [{"lat": 10.1, "lon": -67.5}, {"lat": 10.1, "lon": -67.4}]},
            {"type": "way", "id": 3, "tags": {"highway": "primary"}, "geometry": [{"lat": 10.1, "lon": -67.5}]},
            {"type": "node", "id": 9, "lat": 10.25, "lon": -67.6, "tags": {"place": "city", "name": "Maracay"}},
        ],
    }
    roads, places = osm.overpass_to_geojson(payload)
    assert [f["properties"]["osm_id"] for f in roads["features"]] == [1, 2]  # sorted; 1-point way dropped
    assert roads["features"][1]["properties"]["bridge"] is True and places["features"][0]["properties"]["name"] == "Maracay"

    calls = {"n": 0}

    def fake_post(*a: Any, **k: Any) -> FakeResponse:
        calls["n"] += 1
        assert k["headers"]["User-Agent"].startswith("TriageSAR/") and k["timeout"]
        return FakeResponse(200, payload)

    monkeypatch.setattr(osm, "_MIN_INTERVAL_S", 0.0)
    monkeypatch.setattr(osm.requests, "post", fake_post)
    first = osm.fetch_overpass(query, tmp_path, url="https://overpass.invalid/api")
    second = osm.fetch_overpass(query, tmp_path, url="https://overpass.invalid/api")
    assert first == second and calls["n"] == 1  # second call served from the file cache

    monkeypatch.setattr(osm.requests, "post", lambda *a, **k: FakeResponse(429))
    with pytest.raises(osm.OverpassError, match="busy"):
        osm.fetch_overpass(query + " ", tmp_path, url="https://overpass.invalid/api")
    monkeypatch.setattr(osm.requests, "post", lambda *a, **k: FakeResponse(200, ValueError("html")))
    with pytest.raises(osm.OverpassError, match="non-JSON"):
        osm.fetch_overpass(query + "  ", tmp_path, url="https://overpass.invalid/api")


def test_load_roads_filters_by_configured_classes(tmp_path: Path) -> None:
    import json

    payload = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"osm_id": 1, "highway": "primary_link", "name": "", "ref": "T1"},
         "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}},
        {"type": "Feature", "properties": {"osm_id": 2, "highway": "residential"},
         "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}},
    ]}
    path = tmp_path / "roads.geojson"
    path.write_text(json.dumps(payload))
    (road,) = osm.load_roads(path, ("primary",))
    assert road.base_class == "primary" and road.name is None and road.ref == "T1"
    assert len(osm.load_roads(path)) == 2

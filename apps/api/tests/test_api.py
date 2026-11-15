"""Endpoint tests. No test here touches the network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SYN = "synthetic-test-event"
REAL = "venezuela-2026-06-24"


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["events_total"] == 2 and body["events_ready"] == 1
    assert body["schema_version"] == "1.0" and body["app_version"]


def test_events_list_shows_unbuilt_real_fixture_honestly(client: TestClient) -> None:
    events = {e["id"]: e for e in client.get("/api/v1/events").json()["events"]}
    real, syn = events[REAL], events[SYN]
    assert real["status"] == "fixture_not_built" and real["data_kind"] == "nasa_nisar_gunw"
    assert real["build_command"] == f"python scripts/build_demo_fixture.py --event {REAL}"
    assert real["granule_id"].startswith("NISAR_L2_PR_GUNW_") and real["acquisitions"] == []
    assert "usgs.gov" in real["event_source_url"]
    assert syn["status"] == "ready" and syn["data_kind"] == "synthetic_test"
    assert "SYNTHETIC" in syn["data_label"] and "not NASA" in syn["data_label"]


def test_synthetic_event_is_hidden_unless_explicitly_enabled(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRIAGESAR_INCLUDE_SYNTHETIC")
    assert [e["id"] for e in client.get("/api/v1/events").json()["events"]] == [REAL]
    assert client.get(f"/api/v1/events/{SYN}").status_code == 404


def test_event_detail(client: TestClient) -> None:
    body = client.get(f"/api/v1/events/{SYN}").json()
    assert body["event"]["id"] == SYN and body["zone_count"] == 2 and body["queue_length"] >= 3
    assert body["radar"]["derivation"] == "center_frequency" and body["radar"]["wavelength_m"] > 0
    assert sum(body["quality"]["counts"].values()) == body["quality"]["total_pixels"]
    assert "not a damage assessment" in body["disclaimer"]
    assert body["corrections"]["applied"] == []
    p = body["provenance_summary"]
    assert p["granule_id"] and p["reference_start_utc"] and p["fixture_command"] and p["application_version"]
    assert [a["role"] for a in body["event"]["acquisitions"]] == ["reference", "secondary"]


def test_unknown_and_malformed_event_ids(client: TestClient) -> None:
    r = client.get("/api/v1/events/no-such-event")
    assert r.status_code == 404 and r.json()["error"]["code"] == "event_not_found"
    assert client.get("/api/v1/events/..%2F..%2Fetc%2Fpasswd").status_code in (404, 422)
    assert client.get("/api/v1/events/UPPER_case").status_code == 422
    assert client.get("/api/v1/nope").json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("suffix", ["", "/raster/metadata", "/raster/displacement.png", "/hotspots", "/inspection-queue", "/ablation"])
def test_missing_fixture_gives_409_with_build_hint_never_placeholder_data(client: TestClient, suffix: str) -> None:
    r = client.get(f"/api/v1/events/{REAL}{suffix}")
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "fixture_not_built" and "build_demo_fixture.py" in err["hint"]


def test_raster_metadata_and_images(client: TestClient) -> None:
    meta = client.get(f"/api/v1/events/{SYN}/raster/metadata").json()
    assert len(meta["coordinates"]) == 4 and meta["colour_limit_m"] > 0
    assert {e["key"] for e in meta["legend"]} == {"away", "towards", "caution", "excluded", "zone"}
    assert all(e["encoding"] for e in meta["legend"])  # never colour alone
    for url in (meta["displacement_url"], meta["quality_url"]):
        img = client.get(url)
        assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content[:4] == b"\x89PNG"
        assert "max-age" in img.headers["cache-control"]
    local = client.get(meta["local_url"])
    assert local.status_code == 200 and local.content[:4] == b"\x89PNG"
    assert 0 < meta["local_colour_limit_m"] < meta["colour_limit_m"] and "plane" in meta["local_note"]
    assert client.get(f"/api/v1/events/{SYN}/raster/secret.png").status_code == 422


def test_hotspots_geojson(client: TestClient) -> None:
    body = client.get(f"/api/v1/events/{SYN}/hotspots").json()
    assert body["type"] == "FeatureCollection" and len(body["features"]) == 2
    feat = body["features"][0]
    assert feat["id"] == "Z01" and feat["geometry"]["type"] in {"Polygon", "MultiPolygon"}
    for key in ("area_km2", "median_los_m", "max_abs_los_m", "iqr_los_m", "valid_fraction", "median_coherence", "bbox_wgs84",
                "scene_median_los_m", "nearest_road_name", "nearest_road_distance_m"):
        assert key in feat["properties"]


def test_inspection_queue_and_paging(client: TestClient) -> None:
    body = client.get(f"/api/v1/events/{SYN}/inspection-queue").json()
    assert body["score_label"] == "Inspection priority score" and body["total"] == len(body["items"])
    assert [i["rank"] for i in body["items"]] == list(range(1, body["total"] + 1))
    assert abs(sum(body["weights"].values()) - 1.0) < 1e-3 and body["sensitivity"]["runs"] == 212
    first = body["items"][0]
    assert len(first["components"]) == 6 and first["explanation"]["why_ranked"] and first["corridor"]["pixel_count"] > 0
    page = client.get(f"/api/v1/events/{SYN}/inspection-queue", params={"limit": 1, "offset": 1}).json()
    assert len(page["items"]) == 1 and page["items"][0]["rank"] == 2
    assert client.get(f"/api/v1/events/{SYN}/inspection-queue", params={"limit": 0}).status_code == 422
    assert client.get(f"/api/v1/events/{SYN}/inspection-queue", params={"limit": 9999}).status_code == 422


def test_inspection_detail(client: TestClient) -> None:
    first = client.get(f"/api/v1/events/{SYN}/inspection-queue").json()["items"][0]
    body = client.get(f"/api/v1/inspection/{first['id']}").json()
    assert body["item"] == first and body["zone"]["zone_id"] == first["zone_id"]
    assert body["provenance_summary"]["granule_id"]
    for bad in (f"{SYN}--z99-r001", "no-such-event--z01-r001"):
        r = client.get(f"/api/v1/inspection/{bad}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "inspection_not_found"
    assert client.get("/api/v1/inspection/not-an-id").status_code == 422


def test_roads_and_ablation(client: TestClient) -> None:
    roads = client.get(f"/api/v1/events/{SYN}/roads").json()
    assert roads["roads"]["type"] == "FeatureCollection" and len(roads["roads"]["features"]) >= 5
    assert "TEST ONLY" in roads["attribution"]
    real = client.get(f"/api/v1/events/{REAL}/roads").json()  # roads are cached even before the fixture exists
    assert "OpenStreetMap" in real["attribution"]
    ab = client.get(f"/api/v1/events/{SYN}/ablation").json()["ablation"]
    assert ab["without_masking"]["usable_pixels"] > ab["with_masking"]["usable_pixels"]


def test_provenance(client: TestClient) -> None:
    body = client.get("/api/v1/provenance").json()
    events = {e["event_id"]: e for e in body["events"]}
    assert body["application"]["licence"] == "Apache-2.0"
    assert events[REAL]["fixture_manifest"] is None and events[REAL]["checksum_problems"] is None
    assert events[REAL]["event_definition"]["granule"]["download_url"].startswith("https://nisar.asf.earthdatacloud.nasa.gov/")
    syn = events[SYN]
    assert syn["checksum_problems"] == [] and syn["fixture_manifest"]["build"]["command"]
    assert all(len(layer["sha256"]) == 64 for layer in syn["fixture_manifest"]["layers"].values())


def test_methodology(client: TestClient) -> None:
    body = client.get("/api/v1/methodology").json()
    assert "4 * pi" in body["equation"] and "away from the satellite" in body["sign_convention"]
    assert len(body["score_components"]) == 6 and len(body["pipeline"]) == 7
    assert any("does not detect structural damage" in s for s in body["not_claimed"])
    assert {s["state"] for s in body["quality_states"]} == {"VALID", "CAUTION", "EXCLUDED"}


def test_bad_config_is_reported_not_hidden(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("[quality]\ncoherence_exclude_below = 2.5\n", encoding="utf-8")
    monkeypatch.setenv("TRIAGESAR_CONFIG", str(bad))
    for url in ("/api/v1/methodology", f"/api/v1/events/{SYN}"):
        r = client.get(url)
        assert r.status_code == 500 and r.json()["error"]["code"] == "configuration_invalid"


def test_corrupt_fixture_is_reported(client: TestClient, synthetic_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import shutil

    broken = tmp_path / "broken-synthetic"
    shutil.copytree(synthetic_dir, broken)
    (broken / "nisar" / SYN / "coherence.tif").unlink()
    monkeypatch.setenv("TRIAGESAR_SYNTHETIC_DIR", str(broken))
    r = client.get(f"/api/v1/events/{SYN}")
    assert r.status_code == 500 and r.json()["error"]["code"] == "fixture_invalid"


def test_api_works_without_any_earthdata_credentials_and_exposes_none(client: TestClient) -> None:
    text = client.get("/api/v1/provenance").text + client.get("/openapi.json").text
    assert "EARTHDATA" not in text and "Bearer" not in text
    assert client.get("/docs").status_code == 200


def test_only_get_is_allowed(client: TestClient) -> None:
    assert client.post("/api/v1/events").status_code == 405
    assert client.delete(f"/api/v1/events/{SYN}").status_code == 405


def test_openapi_schema_is_typed(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert {"/health", "/api/v1/events", "/api/v1/events/{event_id}/inspection-queue", "/api/v1/inspection/{inspection_id}",
            "/api/v1/provenance", "/api/v1/methodology"} <= set(spec["paths"])
    assert "InspectionItem" in spec["components"]["schemas"]


def test_profiles_and_thumbnails_for_zones_and_items(client: TestClient) -> None:
    first = client.get(f"/api/v1/events/{SYN}/inspection-queue").json()["items"][0]
    for target, kind in ((first["id"], "road"), ("Z01", "transect")):
        body = client.get(f"/api/v1/events/{SYN}/profile/{target}").json()
        assert body["kind"] == kind and body["length_km"] > 0
        n = len(body["distance_km"])
        assert n > 5 and len(body["local_m"]) == len(body["scene_m"]) == len(body["state"]) == n
        assert any(v is not None for v in body["local_m"]) and "unobserved" in body["description"]
        img = client.get(f"/api/v1/events/{SYN}/thumbnail/{target}.png")
        assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    assert client.get(f"/api/v1/events/{SYN}/profile/Z99").status_code == 404
    assert client.get(f"/api/v1/events/{SYN}/profile/..%2Fx").status_code in (404, 422)
    assert client.get(f"/api/v1/events/{REAL}/profile/Z01").status_code == 409


def test_event_summary_carries_acquisition_dates_and_place(client: TestClient) -> None:
    real = next(e for e in client.get("/api/v1/events").json()["events"] if e["id"] == REAL)
    assert real["place"] and real["magnitude"] == 7.5
    used = [a for a in real["acquisition_dates"] if a["used"]]
    assert [a["date"] for a in used] == ["2026-06-13", "2026-06-25"] and "ASF" in real["acquisition_dates_source"]


def test_auto_ingest_status_and_markers(client: TestClient, data_dir: Path) -> None:
    body = client.get("/api/v1/events").json()
    assert body["auto_ingest"]["enabled"] is False and body["auto_ingest"]["last_checked_utc"] is None
    assert {e["id"]: e["added_by"] for e in body["events"]} == {REAL: "manual", SYN: "test"}
    state = {
        "last_checked_utc": "2026-11-15T06:00:00Z",
        "checked_until": "2026-11-15",
        "processed": {"us1": {"status": "added"}, "us2": {"status": "waiting"}, "us3": {"status": "skipped"}},
        "runs": [],
    }
    (data_dir / "auto_ingest_state.json").write_text(json.dumps(state), encoding="utf-8")
    status = client.get("/api/v1/events").json()["auto_ingest"]
    assert status == {**status, "enabled": True, "last_checked_utc": "2026-11-15T06:00:00Z", "added_total": 1, "waiting": 1}

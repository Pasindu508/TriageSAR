"""Automatic discovery and ingestion of new case studies. All network access is mocked."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from triagesar import autodiscover as ad
from triagesar.config import REPO_ROOT
from triagesar.provenance.manifest import EventInfo

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import auto_ingest  # noqa: E402

QUAKE_TIME = dt.datetime(2026, 7, 28, 7, 27, tzinfo=dt.UTC)
QUAKE = ad.Quake("us000test", 6.8, "mww", "10 km NNE of Testtown, Japan", QUAKE_TIME, 130.66, 32.62, 8.0,
                 "https://earthquake.usgs.gov/earthquakes/eventpage/us000test")
FOOTPRINT = "POLYGON ((129.5 31.8, 131.8 31.8, 131.8 33.5, 129.5 33.5, 129.5 31.8))"
SMALL_FOOTPRINT = "POLYGON ((130.6 32.6, 130.7 32.6, 130.7 32.7, 130.6 32.7, 130.6 32.6))"
FAR_FOOTPRINT = "POLYGON ((120 10, 121 10, 121 11, 120 11, 120 10))"


def name(ref: str, sec: str, kind: str = "N_F") -> str:
    return f"NISAR_L2_PR_GUNW_026_024_A_018_028_4000_SH_{ref}_{ref}_{sec}_{sec}_P05023_{kind}_J_001"


def asf_item(granule: str, collection: str = "NISAR_L2_GUNW_PROVISIONAL_V1", wkt: str = FOOTPRINT) -> dict[str, Any]:
    return {"granuleName": granule, "fileName": granule + ".h5", "collectionName": collection, "wkt": wkt,
            "downloadUrl": f"https://nisar.asf.earthdatacloud.nasa.gov/x/{granule}.h5", "path": 24, "frame": 18,
            "flightDirection": "ASCENDING", "conceptID": "C1-ASF", "pgeVersion": "R05.02.3"}


class FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self.payload, self.status_code = payload, status

    def json(self) -> Any:
        return self.payload


def test_find_quakes_parses_the_usgs_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"features": [
        {"id": "us1", "properties": {"mag": 7.5, "magType": "mww", "place": "20 km W of A, B", "time": 1782338704053,
                                     "url": "https://e/us1"}, "geometry": {"coordinates": [-67.2, 10.6, 10]}},
        {"id": "broken", "properties": {"mag": None}, "geometry": {"coordinates": [0, 0, 0]}},
    ]}
    seen: dict[str, Any] = {}

    def fake_get(url: str, params: dict[str, Any], **_: Any) -> FakeResponse:
        seen.update(params)
        return FakeResponse(payload)

    monkeypatch.setattr(ad.requests, "get", fake_get)
    (q,) = ad.find_quakes(dt.date(2026, 6, 17), dt.date(2026, 11, 15), 6.0, 40)
    assert q.usgs_id == "us1" and q.magnitude == 7.5 and q.lat == 10.6 and q.time.tzinfo is not None
    assert seen["minmagnitude"] == 6.0 and seen["maxdepth"] == 40 and seen["endtime"] == "2026-11-16"
    with pytest.raises(ValueError):
        ad.find_quakes(dt.date(2026, 7, 2), dt.date(2026, 7, 1))
    monkeypatch.setattr(ad.requests, "get", lambda *a, **k: FakeResponse({}, 503))
    with pytest.raises(ad.AutoDiscoveryError, match="503"):
        ad.find_quakes(dt.date(2026, 6, 17), dt.date(2026, 6, 18))


def test_only_pairs_that_bracket_the_quake_and_cover_the_area_are_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    good_long = name("20260721T202900", "20260814T202858")
    good_short = name("20260727T202900", "20260808T202858")
    validated = name("20260727T202900", "20260808T202858", "N_P")
    results = [
        asf_item(good_long),
        asf_item(good_short),
        asf_item(validated, "NISAR_L2_GUNW_V1"),
        asf_item(name("20260727T202900", "20260808T202858", "F_F"), "NISAR_UR_L2"),  # urgent response: ignored
        asf_item(name("20260728T120000", "20260809T120000")),  # reference after the quake (same day, later)
        asf_item(name("20260716T000000", "20260726T000000")),  # both before the quake
        asf_item(name("20260601T000000", "20260814T000000")),  # pair longer than 48 days
        asf_item(name("20260721T000001", "20260814T000001"), wkt=SMALL_FOOTPRINT),  # covers too little
        asf_item(name("20260721T000002", "20260814T000002"), wkt=FAR_FOOTPRINT),  # epicentre outside
        {"granuleName": good_long, "fileName": good_long + ".iso.xml", "collectionName": "NISAR_L2_GUNW_PROVISIONAL_V1"},
    ]
    monkeypatch.setattr(ad.requests, "get", lambda *a, **k: FakeResponse({"results": results}))
    cands = ad.find_coseismic_granules(QUAKE)
    assert [c.granule_id for c in cands] == [validated, good_short, good_long]  # validated, then shorter pair
    best = cands[0]
    assert best.reference == dt.date(2026, 7, 27) and best.secondary == dt.date(2026, 8, 8) and best.baseline_days == 12
    assert best.aoi_coverage == pytest.approx(1.0) and best.aoi_bbox == ad.study_area(QUAKE.lon, QUAKE.lat)


def test_ids_titles_and_definitions() -> None:
    assert ad.region_name("66 km NNW of Ende, Indonesia") == "Ende, Indonesia"
    assert ad.region_name("The 2026 Kumamoto Region, Japan Earthquake") == "Kumamoto Region, Japan"
    assert ad.slugify("Río Grande, Panamá") == "rio-grande-panama"
    assert ad.event_id_for(QUAKE, set()) == "japan-2026-07-28"
    assert ad.event_id_for(QUAKE, {"japan-2026-07-28"}) == "japan-testtown-2026-07-28"
    assert ad.event_title(QUAKE) == "Testtown, Japan earthquake, 28 July 2026"

    cand = ad.Candidate(QUAKE, name("20260727T202900", "20260808T202858"), "f.h5", "https://x/f.h5",
                        "NISAR_L2_GUNW_PROVISIONAL_V1", "C1", 24, 18, "ASCENDING", FOOTPRINT, "R1",
                        dt.date(2026, 7, 27), dt.date(2026, 8, 8), (130.1, 32.3, 131.2, 32.9), 1.0)
    d = ad.event_definition(cand, "japan-2026-07-28", dt.date(2026, 11, 15), 123)
    assert d["added_by"] == "auto_ingest" and d["added_on"] == "2026-11-15"
    assert d["granule"]["granule_id"] == cand.granule_id and d["granule"]["source_size_bytes"] == 123
    assert d["epicentres"][0]["usgs_id"] == "us000test" and "Added automatically" in d["summary"]
    EventInfo(id=d["id"], title=d["title"], summary=d["summary"], event_time_utc=d["event_time_utc"])  # valid schema


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository-shaped temporary directory with one existing case study."""
    (tmp_path / "config" / "events").mkdir(parents=True)
    data = tmp_path / "data"
    data.mkdir()
    existing = {"id": "venezuela-2026-06-24", "title": "x", "summary": "x",
                "epicentres": [{"usgs_id": "us6000t7zp"}], "granule": {"granule_id": "EXISTING_GRANULE"}}
    (tmp_path / "config" / "events" / "venezuela-2026-06-24.json").write_text(json.dumps(existing))
    (data / "demo_manifest.json").write_text(json.dumps({"events": [{
        "id": "venezuela-2026-06-24", "event_config": "config/events/venezuela-2026-06-24.json",
        "nisar_dir": "nisar/venezuela-2026-06-24", "infrastructure_dir": "infrastructure/venezuela-2026-06-24"}]}))
    monkeypatch.setattr(auto_ingest, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("TRIAGESAR_DATA_DIR", str(data))
    monkeypatch.setenv("EARTHDATA_TOKEN", "test-token")
    monkeypatch.setattr(auto_ingest, "remote_file_size", lambda url: 1000)
    return tmp_path


def _candidate(granule: str = "NEW_GRANULE") -> ad.Candidate:
    return ad.Candidate(QUAKE, granule, f"{granule}.h5", f"https://x/{granule}.h5", "NISAR_L2_GUNW_PROVISIONAL_V1",
                        "C1", 24, 18, "ASCENDING", FOOTPRINT, "R1", dt.date(2026, 7, 27), dt.date(2026, 8, 8),
                        (130.1, 32.3, 131.2, 32.9), 1.0)


def _run(monkeypatch: pytest.MonkeyPatch, argv: list[str], quakes: list[ad.Quake], cands: list[ad.Candidate],
         roads: int = 100, fail_on: str | None = None) -> list[str]:
    calls: list[str] = []

    def fake_step(script: str, *args: str) -> tuple[bool, str]:
        calls.append(script)
        if script == "fetch_osm_roads.py":
            out = Path(auto_ingest.data_dir()) / "infrastructure" / args[1]
            out.mkdir(parents=True, exist_ok=True)
            (out / "roads.geojson").write_text(json.dumps({"features": [{}] * roads}))
        if script == "build_demo_fixture.py":
            (Path(auto_ingest.data_dir()) / "nisar" / args[1]).mkdir(parents=True, exist_ok=True)
        return (script != fail_on), f"{script} output"

    monkeypatch.setattr(auto_ingest, "run_step", fake_step)
    monkeypatch.setattr(auto_ingest, "find_quakes", lambda *a, **k: quakes)
    monkeypatch.setattr(auto_ingest, "find_coseismic_granules", lambda q: cands)
    monkeypatch.setattr(sys, "argv", ["auto_ingest.py", "--until", "2026-11-15", *argv])
    auto_ingest.main()
    return calls


def _registry(root: Path) -> list[str]:
    return [e["id"] for e in json.loads((root / "data" / "demo_manifest.json").read_text())["events"]]


def test_dry_run_writes_nothing(sandbox: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls = _run(monkeypatch, ["--dry-run"], [QUAKE], [_candidate()])
    assert calls == [] and _registry(sandbox) == ["venezuela-2026-06-24"]
    assert not (sandbox / "data" / auto_ingest.STATE_NAME).exists()
    assert "japan-2026-07-28" in capsys.readouterr().out


def test_successful_ingest_registers_the_event_and_records_state(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _run(monkeypatch, [], [QUAKE], [_candidate()])
    assert calls == ["fetch_osm_roads.py", "build_demo_fixture.py", "fetch_acquisitions.py", "verify_fixture_hashes.py"]
    assert _registry(sandbox) == ["venezuela-2026-06-24", "japan-2026-07-28"]
    definition = json.loads((sandbox / "config" / "events" / "japan-2026-07-28.json").read_text())
    assert definition["added_by"] == "auto_ingest" and definition["granule"]["granule_id"] == "NEW_GRANULE"
    state = json.loads((sandbox / "data" / auto_ingest.STATE_NAME).read_text())
    assert state["processed"]["us000test"]["status"] == "added" and state["checked_until"] == "2026-11-15"
    assert state["runs"][0]["added"] == ["japan-2026-07-28"]
    # A second run does nothing: the earthquake is already covered.
    assert _run(monkeypatch, [], [QUAKE], [_candidate()]) == []


def test_failures_roll_back_and_offshore_areas_are_skipped(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run(monkeypatch, [], [QUAKE], [_candidate()], fail_on="build_demo_fixture.py")
    assert _registry(sandbox) == ["venezuela-2026-06-24"]
    assert not (sandbox / "config" / "events" / "japan-2026-07-28.json").exists()
    assert not (sandbox / "data" / "infrastructure" / "japan-2026-07-28").exists()
    state = json.loads((sandbox / "data" / auto_ingest.STATE_NAME).read_text())
    assert state["processed"]["us000test"]["status"] == "retry"

    _run(monkeypatch, [], [QUAKE], [_candidate()], roads=3)
    state = json.loads((sandbox / "data" / auto_ingest.STATE_NAME).read_text())
    assert state["processed"]["us000test"]["status"] == "skipped" and "likely offshore" in state["processed"]["us000test"]["reason"]
    assert _registry(sandbox) == ["venezuela-2026-06-24"]


def test_unpublished_products_wait_and_reused_interferograms_are_skipped(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _run(monkeypatch, ["--wait-days", "200"], [QUAKE], [])
    state = json.loads((sandbox / "data" / auto_ingest.STATE_NAME).read_text())
    assert state["processed"]["us000test"]["status"] == "waiting"  # re-checked on the next run
    _run(monkeypatch, ["--wait-days", "30"], [QUAKE], [])
    state = json.loads((sandbox / "data" / auto_ingest.STATE_NAME).read_text())
    assert state["processed"]["us000test"]["status"] == "skipped"  # gave up after the waiting period

    aftershock = ad.Quake("us000after", 6.1, "mww", "near Testtown, Japan", QUAKE_TIME, 130.6, 32.6, 9.0, "u")
    calls = _run(monkeypatch, [], [aftershock], [_candidate("EXISTING_GRANULE")])
    state = json.loads((sandbox / "data" / auto_ingest.STATE_NAME).read_text())
    assert calls == [] and "same NISAR interferogram as case study venezuela-2026-06-24" in state["processed"]["us000after"]["reason"]


def test_at_most_max_new_events_per_run(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    quakes = [ad.Quake(f"us{i}", 6.5, "mww", f"near Place{i}, Japan", QUAKE_TIME + dt.timedelta(days=i), 130.66, 32.62, 8.0, "u")
              for i in range(3)]
    grans = iter([_candidate(f"G{i}") for i in range(3)])
    monkeypatch.setattr(auto_ingest, "find_coseismic_granules", lambda q: [next(grans)])
    calls: list[str] = []

    def fake_step(script: str, *args: str) -> tuple[bool, str]:
        calls.append(script)
        if script == "fetch_osm_roads.py":
            out = Path(auto_ingest.data_dir()) / "infrastructure" / args[1]
            out.mkdir(parents=True, exist_ok=True)
            (out / "roads.geojson").write_text(json.dumps({"features": [{}] * 50}))
        return True, "ok"

    monkeypatch.setattr(auto_ingest, "run_step", fake_step)
    monkeypatch.setattr(auto_ingest, "find_quakes", lambda *a, **k: quakes)
    monkeypatch.setattr(sys, "argv", ["auto_ingest.py", "--until", "2026-11-15", "--max-new", "2"])
    auto_ingest.main()
    assert len(_registry(sandbox)) == 3 and calls.count("build_demo_fixture.py") == 2


def test_refuses_to_run_without_credentials_unless_dry_run(sandbox: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EARTHDATA_TOKEN")
    monkeypatch.setattr(auto_ingest, "resolve_credentials", lambda *_: type("C", (), {"available": False})())
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, [], [QUAKE], [_candidate()])
    assert exc.value.code == 2

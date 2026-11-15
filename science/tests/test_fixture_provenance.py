import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from tests.support import synthetic as syn
from triagesar.fixture import Fixture, build_fixture, load_fixture
from triagesar.provenance.manifest import EventInfo, FixtureManifest, read_manifest, verify_checksums

FIXTURE_REL = Path("nisar") / syn.SYNTHETIC_EVENT_ID


def test_crop_preserves_values_bit_for_bit(synthetic_root: Path, fixture: Fixture) -> None:
    aoi = fixture.manifest.aoi
    rows, cols = slice(aoi.row_start, aoi.row_stop), slice(aoi.col_start, aoi.col_stop)
    with h5py.File(synthetic_root / "source" / "TEST_ONLY_SYNTHETIC_GUNW.h5") as h5:
        for name, info in fixture.manifest.layers.items():
            source = h5[info.hdf5_path][rows, cols]
            assert fixture.arrays[name].dtype == source.dtype
            np.testing.assert_array_equal(fixture.arrays[name], source)  # NaN == NaN here


def test_manifest_records_provenance(fixture: Fixture) -> None:
    m = fixture.manifest
    assert m.data_kind == "synthetic_test" and "TEST ONLY" in m.event.summary
    assert m.source.granule_id == "TEST_ONLY_SYNTHETIC_GUNW_NOT_A_NASA_PRODUCT"
    assert m.acquisition.reference_start_utc.startswith("2000-01-01")  # type: ignore[union-attr]
    assert m.acquisition.secondary_start_utc.startswith("2000-01-13")  # type: ignore[union-attr]
    assert m.radar.derivation == "center_frequency" and m.radar.source_hdf5_path.endswith("centerFrequency")
    assert m.aoi.bbox_wgs84_requested == syn.SYNTHETIC_BBOX
    assert m.corrections.applied == [] and len(m.corrections.available_layers) == 3
    assert any("Cropped to rows" in t for t in m.transformations)
    assert m.build.command and m.build.app_version and "h5py" in m.build.tool_versions
    assert all(len(layer.sha256) == 64 for layer in m.layers.values())
    assert m.grid.epsg == syn.EPSG and (m.grid.height, m.grid.width) == fixture.grid.shape


def test_checksums_detect_tampering(synthetic_root: Path, tmp_path: Path) -> None:
    src = synthetic_root / FIXTURE_REL
    assert verify_checksums(src) == []
    copy = tmp_path / "copy"
    copy.mkdir()
    for f in src.iterdir():
        (copy / f.name).write_bytes(f.read_bytes())
    with (copy / "coherence.tif").open("r+b") as fh:
        fh.seek(-1, 2)
        last = fh.read(1)
        fh.seek(-1, 2)
        fh.write(bytes([last[0] ^ 0xFF]))
    problems = verify_checksums(copy)
    assert len(problems) == 1 and "coherence" in problems[0]
    (copy / "mask.tif").unlink()
    assert any("missing" in p for p in verify_checksums(copy))


def test_south_up_source_is_flipped_losslessly(tmp_path: Path) -> None:
    h5_path = syn.write_synthetic_gunw(tmp_path / "south_up.h5")
    with h5py.File(h5_path, "r+") as h5:
        y = h5[f"{syn.GROUP}/yCoordinates"]
        y[...] = y[()][::-1]
        parent = syn.GROUP.rsplit("/", 1)[0]
        paths = [f"{syn.GROUP}/{n}" for n in ("unwrappedPhase", "coherenceMagnitude", "connectedComponents", "ionospherePhaseScreen")]
        for path in [*paths, f"{parent}/mask"]:
            ds = h5[path]
            ds[...] = ds[()][::-1, :]
    event = EventInfo(id="flip-test", title="t", summary="TEST ONLY")
    manifest = build_fixture(str(h5_path), tmp_path / "flip", syn.SYNTHETIC_BBOX, event, "test", data_kind="synthetic_test")
    assert any("north-up" in t for t in manifest.transformations)
    flipped = load_fixture(tmp_path / "flip")
    reference = syn.synthetic_layers()["coherenceMagnitude"]
    aoi = manifest.aoi
    expected = reference[syn.HEIGHT - aoi.row_stop : syn.HEIGHT - aoi.row_start, aoi.col_start : aoi.col_stop]
    np.testing.assert_array_equal(flipped.arrays["coherence"], expected)


def test_missing_or_broken_fixture_raises_clear_errors(tmp_path: Path, synthetic_root: Path) -> None:
    with pytest.raises(FileNotFoundError, match="manifest"):
        load_fixture(tmp_path)
    broken = tmp_path / "broken"
    broken.mkdir()
    manifest = json.loads((synthetic_root / FIXTURE_REL / "manifest.json").read_text())
    (broken / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(FileNotFoundError, match="layer file missing"):
        load_fixture(broken)
    manifest["unknown_field"] = 1
    (broken / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        read_manifest(broken)


def test_aoi_outside_product_and_oversize_are_rejected(synthetic_h5: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    event = EventInfo(id="x-test", title="t", summary="TEST ONLY")
    with pytest.raises(ValueError, match="does not overlap"):
        build_fixture(str(synthetic_h5), tmp_path / "a", (20.0, 20.0, 21.0, 21.0), event, "test", data_kind="synthetic_test")
    monkeypatch.setattr("triagesar.fixture.MAX_FIXTURE_PIXELS", 100)
    with pytest.raises(ValueError, match="fixture limit"):
        build_fixture(str(synthetic_h5), tmp_path / "b", syn.SYNTHETIC_BBOX, event, "test", data_kind="synthetic_test")


def test_manifest_schema_round_trip(fixture: Fixture) -> None:
    again = FixtureManifest.model_validate_json(fixture.manifest.model_dump_json())
    assert again == fixture.manifest

"""Reader tests on a tiny TEST ONLY synthetic HDF5 file."""

from pathlib import Path

import h5py
import numpy as np
import pytest
from pyproj import CRS

from tests.support import synthetic as syn
from triagesar.nisar import hdf5_reader as rd
from triagesar.nisar.metadata import read_metadata
from triagesar.nisar.schema import SPEED_OF_LIGHT_M_S, SchemaError
from triagesar.processing.georeference import window_for_bbox


def _copy(src: Path, dst: Path) -> Path:
    dst.write_bytes(src.read_bytes())
    return dst


def test_discovers_canonical_layers(synthetic_h5: Path) -> None:
    with h5py.File(synthetic_h5) as h5:
        layers = rd.discover_layers(h5)
    assert layers.layer_group == syn.GROUP
    assert set(layers.layers) == {"unwrapped_phase", "coherence", "connected_components", "mask", "ionosphere_phase_screen"}
    assert layers.frequency == "A" and layers.polarisation == "HH"
    assert layers.grid.epsg == syn.EPSG and (layers.grid.height, layers.grid.width) == (syn.HEIGHT, syn.WIDTH)
    assert layers.layers["unwrapped_phase"].hdf5_path.endswith("/HH/unwrappedPhase")
    assert layers.layers["mask"].hdf5_path.endswith("/unwrappedInterferogram/mask")  # shared, one level up


def test_attribute_parsing(synthetic_h5: Path) -> None:
    with h5py.File(synthetic_h5) as h5:
        layers = rd.discover_layers(h5)
        meta = read_metadata(h5)
    assert layers.layers["unwrapped_phase"].units == "radians"
    assert layers.layers["connected_components"].fill_value == 65535
    assert layers.layers["mask"].fill_value == 255
    assert meta.get("reference_start_time").startswith("2000-01-01")
    assert meta.get("secondary_start_time").startswith("2000-01-13")
    assert meta.get("track_number") == 1 and meta.get("orbit_pass_direction") == "Ascending"
    assert meta.software_version == "0.0-TEST"


def test_wavelength_comes_from_metadata_not_a_constant(synthetic_h5: Path, tmp_path: Path) -> None:
    with h5py.File(synthetic_h5) as h5:
        wl = rd.discover_layers(h5).wavelength
    assert wl.derivation == "center_frequency" and wl.source_path.endswith("/centerFrequency")
    assert wl.wavelength_m == pytest.approx(SPEED_OF_LIGHT_M_S / syn.TEST_CENTER_FREQUENCY_HZ)
    other = _copy(synthetic_h5, tmp_path / "other.h5")
    with h5py.File(other, "r+") as h5:
        h5["/science/LSAR/GUNW/grids/frequencyA/centerFrequency"][()] = 5.0e9
    with h5py.File(other) as h5:
        assert rd.discover_layers(h5).wavelength.wavelength_m == pytest.approx(SPEED_OF_LIGHT_M_S / 5.0e9)


def test_refuses_to_assume_wavelength(synthetic_h5: Path, tmp_path: Path) -> None:
    broken = _copy(synthetic_h5, tmp_path / "nofreq.h5")
    with h5py.File(broken, "r+") as h5:
        del h5["/science/LSAR/GUNW/grids/frequencyA/centerFrequency"]
    with h5py.File(broken) as h5, pytest.raises(SchemaError, match="refusing to assume"):
        rd.discover_layers(h5)


def test_missing_optional_datasets_are_tolerated(synthetic_h5: Path, tmp_path: Path) -> None:
    trimmed = _copy(synthetic_h5, tmp_path / "trimmed.h5")
    with h5py.File(trimmed, "r+") as h5:
        for name in ("connectedComponents", "ionospherePhaseScreen"):
            del h5[f"{syn.GROUP}/{name}"]
        del h5[f"{syn.GROUP.rsplit('/', 1)[0]}/mask"]
    with h5py.File(trimmed) as h5:
        layers = rd.discover_layers(h5)
    assert set(layers.layers) == {"unwrapped_phase", "coherence"}


def test_unexpected_extra_datasets_are_ignored(synthetic_h5: Path) -> None:
    with h5py.File(synthetic_h5) as h5:
        assert "/science/LSAR/GUNW/grids/frequencyA/unexpectedFutureLayer" in h5
        layers = rd.discover_layers(h5)
    assert all("unexpected" not in ref.hdf5_path for ref in layers.layers.values())
    assert any(p.endswith("wetTroposphericPhaseScreen") for p in layers.available_correction_layers)


def test_alternative_layout_is_recognised(tmp_path: Path) -> None:
    """A differently organised file (other group names, wavelength given directly) still works."""
    path = tmp_path / "alt.h5"
    with h5py.File(path, "w") as h5:
        g = h5.require_group("/data/grids/frequencyB/interferogram/unwrapped/VV")
        g.create_dataset("unwrappedPhase", data=np.zeros((4, 5), dtype=np.float32))
        g.create_dataset("coherenceMagnitude", data=np.ones((4, 5), dtype=np.float32))
        h5.create_dataset("/data/grids/frequencyB/xCoordinates", data=np.arange(5) * 10.0)
        h5.create_dataset("/data/grids/frequencyB/yCoordinates", data=100.0 - np.arange(4) * 10.0)
        proj = h5.create_dataset("/data/grids/frequencyB/projection", data=np.uint32(32619))
        proj.attrs["epsg_code"] = 32619
        h5.create_dataset("/data/wavelength", data=0.2)
    with h5py.File(path) as h5:
        layers = rd.discover_layers(h5)
    assert layers.frequency == "B" and layers.polarisation == "VV"
    assert layers.wavelength.derivation == "wavelength" and layers.wavelength.wavelength_m == 0.2


@pytest.mark.parametrize("what", ["coherence_shape", "x_length", "phase_3d", "no_crs", "no_phase"])
def test_invalid_files_raise_schema_error(synthetic_h5: Path, tmp_path: Path, what: str) -> None:
    bad = _copy(synthetic_h5, tmp_path / f"{what}.h5")
    with h5py.File(bad, "r+") as h5:
        if what == "coherence_shape":
            del h5[f"{syn.GROUP}/coherenceMagnitude"]
            h5.create_dataset(f"{syn.GROUP}/coherenceMagnitude", data=np.zeros((3, 3), dtype=np.float32))
        elif what == "x_length":
            del h5[f"{syn.GROUP}/xCoordinates"]
            h5.create_dataset(f"{syn.GROUP}/xCoordinates", data=np.arange(7.0))
        elif what == "phase_3d":
            del h5[f"{syn.GROUP}/unwrappedPhase"]
            h5.create_dataset(f"{syn.GROUP}/unwrappedPhase", data=np.zeros((2, 3, 3), dtype=np.float32))
        elif what == "no_crs":
            del h5[f"{syn.GROUP}/projection"]
        elif what == "no_phase":
            del h5[f"{syn.GROUP}/unwrappedPhase"]
    with h5py.File(bad) as h5, pytest.raises(SchemaError):
        rd.discover_layers(h5)


def test_coordinate_window_and_transform(synthetic_h5: Path) -> None:
    with h5py.File(synthetic_h5) as h5:
        layers = rd.discover_layers(h5)
        x, y = rd.read_coordinates(h5, layers.grid)
        rows, cols = window_for_bbox(x, y, CRS.from_epsg(syn.EPSG), syn.SYNTHETIC_BBOX)
        window = rd.read_window(h5, layers.layers["coherence"], rows, cols)
        full = h5[layers.layers["coherence"].hdf5_path][()]
    assert 0 < rows.stop - rows.start <= syn.HEIGHT and 0 < cols.stop - cols.start <= syn.WIDTH
    np.testing.assert_array_equal(window, full[rows, cols])
    with pytest.raises(ValueError, match="does not overlap"):
        window_for_bbox(x, y, CRS.from_epsg(syn.EPSG), (10.0, 10.0, 11.0, 11.0))


def test_requested_polarisation_must_exist(synthetic_h5: Path) -> None:
    with h5py.File(synthetic_h5) as h5, pytest.raises(SchemaError, match="polarisation"):
        rd.discover_layers(h5, polarisation="VV")


def test_describe_tree_lists_shapes_units_and_crs(synthetic_h5: Path) -> None:
    with h5py.File(synthetic_h5) as h5:
        text = "\n".join(rd.describe_tree(h5))
    assert "unwrappedPhase" in text and "units=radians" in text and f"EPSG:{syn.EPSG}" in text
    assert f"shape=({syn.HEIGHT}, {syn.WIDTH})" in text

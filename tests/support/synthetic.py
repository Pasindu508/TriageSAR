"""TEST ONLY synthetic data. Nothing produced here is a NASA observation.

Generates a tiny HDF5 file that mimics the *layout* of a NISAR GUNW product, and
a made-up road network, so the reader, fixture builder, pipeline, API and UI can
be tested without network access. The location is deliberately in open ocean
near 0 N, 0 E so it cannot be mistaken for a real study area.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import h5py
import numpy as np

from triagesar.fixture import build_fixture
from triagesar.provenance.manifest import EventInfo, FixtureManifest

TEST_ONLY_NOTE = "TEST ONLY - synthetic values, not NASA observations"
SYNTHETIC_EVENT_ID = "synthetic-test-event"
SYNTHETIC_BBOX = (0.02, 0.02, 0.33, 0.25)
TEST_CENTER_FREQUENCY_HZ = 1.25e9  # arbitrary test value
EPSG = 32631
X0, Y0, DX, DY = 168_000.0, 30_000.0, 80.0, -80.0
HEIGHT, WIDTH = 340, 460
GROUP = "/science/LSAR/GUNW/grids/frequencyA/unwrappedInterferogram/HH"


def synthetic_layers(seed: int = 7) -> dict[str, np.ndarray]:
    """Deterministic synthetic layers on the full synthetic grid."""
    rng = np.random.default_rng(seed)
    rows, cols = np.mgrid[0:HEIGHT, 0:WIDTH]

    def bump(r0: float, c0: float, sr: float, sc: float, amp: float) -> np.ndarray:
        return amp * np.exp(-(((rows - r0) / sr) ** 2 + ((cols - c0) / sc) ** 2) / 2.0)

    # Three local features on top of a broad "regional" field, as in a real co-seismic interferogram
    # where the whole study area moved. The regional field must not produce zones on its own.
    phase = bump(120, 150, 9, 12, 9.0) + bump(220, 330, 8, 8, -6.5) + bump(70, 380, 10, 10, 1.5)
    phase += 30.0 * np.exp(-((rows / 200.0) ** 2)) + 0.004 * (cols - WIDTH / 2)
    phase += rng.normal(0.0, 0.15, size=phase.shape) + 31.0
    coherence = np.clip(0.82 + rng.normal(0.0, 0.05, size=phase.shape), 0.0, 1.0)
    coherence[195:250, 335:400] = np.clip(rng.normal(0.18, 0.04, size=(55, 65)), 0.0, 1.0)  # decorrelated patch
    coherence[92:122, 120:235] = np.clip(rng.normal(0.42, 0.03, size=(30, 115)), 0.0, 1.0)  # moderate patch
    components = np.ones(phase.shape, dtype=np.uint16)
    components[coherence < 0.25] = 0
    components[55:85, 365:395] = 2  # small isolated region
    phase[55:85, 365:395] += 2 * math.pi * 3  # with its own arbitrary phase offset
    mask = np.full(phase.shape, 11, dtype=np.uint32)  # sub-swath 1 in both acquisitions
    mask[300:, :120] = 111  # water
    mask[:8, :] = 255  # fill
    mask[150:160, 300:310] |= 1 << 8  # anomaly bit: reported, not excluded
    phase = phase.astype(np.float32)
    phase[:8, :] = np.nan
    iono = (0.02 * np.sin(cols / 60.0)).astype(np.float32)
    return {
        "unwrappedPhase": phase,
        "coherenceMagnitude": coherence.astype(np.float32),
        "connectedComponents": components,
        "mask": mask,
        "ionospherePhaseScreen": iono,
    }


def write_synthetic_gunw(path: Path, seed: int = 7, extra_datasets: bool = True) -> Path:
    """Write a TEST ONLY HDF5 file with a NISAR-GUNW-like layout."""
    layers = synthetic_layers(seed)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as h5:
        h5.attrs["TEST_ONLY"] = TEST_ONLY_NOTE
        grp = h5.require_group(GROUP)
        specs = {
            "unwrappedPhase": ("radians", np.nan),
            "coherenceMagnitude": ("1", np.nan),
            "connectedComponents": ("1", 65535),
            "mask": ("1", 255),
            "ionospherePhaseScreen": ("radians", np.nan),
        }
        shared = h5[GROUP.rsplit("/", 1)[0]]  # the product stores ``mask`` one level above the polarisation
        for name, (units, fill) in specs.items():
            target = shared if name == "mask" else grp
            ds = target.create_dataset(name, data=layers[name], compression="gzip", chunks=(64, 64))
            ds.attrs["units"] = np.bytes_(units)
            ds.attrs["_FillValue"] = fill
            ds.attrs["description"] = np.bytes_(f"{TEST_ONLY_NOTE}: {name}")
        x = grp.create_dataset("xCoordinates", data=X0 + DX * np.arange(WIDTH))
        y = grp.create_dataset("yCoordinates", data=Y0 + DY * np.arange(HEIGHT))
        x.attrs["units"] = np.bytes_("meters")
        y.attrs["units"] = np.bytes_("meters")
        proj = grp.create_dataset("projection", data=np.uint32(EPSG))
        proj.attrs["epsg_code"] = EPSG
        freq = h5.create_dataset("/science/LSAR/GUNW/grids/frequencyA/centerFrequency", data=TEST_CENTER_FREQUENCY_HZ)
        freq.attrs["units"] = np.bytes_("Hz")
        ident = h5.require_group("/science/LSAR/identification")
        for key, value in {
            "referenceZeroDopplerStartTime": "2000-01-01T00:00:00.000000000",
            "referenceZeroDopplerEndTime": "2000-01-01T00:00:30.000000000",
            "secondaryZeroDopplerStartTime": "2000-01-13T00:00:00.000000000",
            "secondaryZeroDopplerEndTime": "2000-01-13T00:00:30.000000000",
            "orbitPassDirection": "Ascending",
            "lookDirection": "Left",
            "productVersion": "0.0-TEST",
            "productType": "GUNW",
            "granuleId": "TEST_ONLY_SYNTHETIC_GUNW_NOT_A_NASA_PRODUCT",
            "processingDateTime": "2000-01-14T00:00:00",
        }.items():
            ident.create_dataset(key, data=np.bytes_(value))
        ident.create_dataset("trackNumber", data=np.uint32(1))
        ident.create_dataset("frameNumber", data=np.uint16(1))
        if extra_datasets:
            rg = h5.require_group("/science/LSAR/GUNW/metadata/radarGrid")
            rg.create_dataset("wetTroposphericPhaseScreen", data=np.zeros((2, 4, 4), dtype=np.float32))
            rg.create_dataset("slantRangeSolidEarthTidesPhase", data=np.zeros((2, 4, 4), dtype=np.float32))
            h5.create_dataset("/science/LSAR/GUNW/metadata/processingInformation/algorithms/softwareVersion", data=np.bytes_("0.0-TEST"))
            h5.create_dataset("/science/LSAR/GUNW/grids/frequencyA/unexpectedFutureLayer", data=np.zeros((3, 3)))
    return path


def synthetic_roads_geojson() -> dict[str, object]:
    """Made-up TEST ONLY roads (lon/lat) crossing the synthetic deformation bumps."""

    def feat(osm_id: int, highway: str, name: str | None, ref: str | None, coords: list[list[float]], bridge: bool = False) -> dict[str, object]:
        props = {"osm_id": osm_id, "highway": highway, "name": name, "ref": ref, "bridge": bridge, "tunnel": False}
        return {"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}}

    return {
        "type": "FeatureCollection",
        "test_only": TEST_ONLY_NOTE,
        "features": [
            feat(900001, "primary", "TEST Road Alpha", "T1", [[0.03, 0.18], [0.10, 0.185], [0.14, 0.19]]),
            feat(900002, "primary", "TEST Road Alpha", "T1", [[0.14, 0.19], [0.20, 0.20], [0.31, 0.215]], bridge=True),
            feat(900003, "secondary", "TEST Road Bravo", None, [[0.22, 0.03], [0.25, 0.10], [0.258, 0.115], [0.30, 0.24]]),
            feat(900004, "tertiary", None, None, [[0.05, 0.05], [0.12, 0.08], [0.17, 0.06]]),
            feat(900005, "motorway", None, "T9", [[0.03, 0.23], [0.15, 0.245], [0.32, 0.245]]),
            feat(900007, "trunk", "TEST Road Charlie", "T2", [[0.21, 0.108], [0.26, 0.112], [0.325, 0.11]]),
            feat(900008, "tertiary", None, None, [[0.23, 0.100], [0.262, 0.100]]),
            feat(900006, "residential", "TEST Lane (not ranked)", None, [[0.10, 0.17], [0.11, 0.18]]),
        ],
    }


def synthetic_places_geojson() -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "test_only": TEST_ONLY_NOTE,
        "features": [
            {"type": "Feature", "properties": {"osm_id": 910001, "place": "town", "name": "Testville (synthetic)"},
             "geometry": {"type": "Point", "coordinates": [0.09, 0.17]}},
        ],
    }


def build_synthetic_event(root: Path) -> tuple[Path, Path, FixtureManifest]:
    """Create HDF5 -> fixture -> roads under ``root``. Returns (fixture_dir, infrastructure_dir, manifest)."""
    root = Path(root)
    h5_path = write_synthetic_gunw(root / "source" / "TEST_ONLY_SYNTHETIC_GUNW.h5")
    fixture_dir = root / "nisar" / SYNTHETIC_EVENT_ID
    infra_dir = root / "infrastructure" / SYNTHETIC_EVENT_ID
    event = EventInfo(
        id=SYNTHETIC_EVENT_ID,
        title="SYNTHETIC TEST EVENT (not real)",
        summary=f"{TEST_ONLY_NOTE}. Used only for automated tests and UI development.",
        notes=[TEST_ONLY_NOTE],
    )
    manifest = build_fixture(
        str(h5_path), fixture_dir, SYNTHETIC_BBOX, event, command="tests.support.synthetic.build_synthetic_event", data_kind="synthetic_test"
    )
    infra_dir.mkdir(parents=True, exist_ok=True)
    (infra_dir / "roads.geojson").write_text(json.dumps(synthetic_roads_geojson()), encoding="utf-8")
    (infra_dir / "places.geojson").write_text(json.dumps(synthetic_places_geojson()), encoding="utf-8")
    return fixture_dir, infra_dir, manifest

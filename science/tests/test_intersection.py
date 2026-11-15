import numpy as np
import pytest
from affine import Affine
from pyproj import CRS
from shapely.geometry import LineString, box

from triagesar.config import InfrastructureConfig
from triagesar.infrastructure.intersection import find_road_candidates, road_observation_coverage
from triagesar.infrastructure.osm import Road
from triagesar.processing.clustering import Hotspot
from triagesar.processing.georeference import WGS84, GridGeometry, reproject_geometry

UTM = CRS.from_epsg(32619)
GRID = GridGeometry(UTM, Affine(100.0, 0, 700_000.0, 0, -100.0, 1_200_000.0), 100, 100)
CFG = InfrastructureConfig(corridor_buffer_m=150.0, proximity_limit_m=1000.0)


def _road(osm_id: int, coords: list[tuple[float, float]], **kw: object) -> Road:
    line = reproject_geometry(LineString(coords), UTM, WGS84)
    defaults = {"highway": "primary", "name": None, "ref": None, "bridge": False, "tunnel": False}
    return Road(osm_id=osm_id, geometry=line, **{**defaults, **kw})  # type: ignore[arg-type]


def _zone() -> Hotspot:
    poly = box(702_000.0, 1_195_000.0, 704_000.0, 1_197_000.0)  # 2 km x 2 km
    return Hotspot("Z01", 1, 400, 400, 4.0, 0.2, 0.2, 0.2, 0.0, 1.0, 0.0, 0.0, 0.8, None, (1,), poly)


def _rasters() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rel = np.zeros(GRID.shape)
    rel[30:50, 20:40] = 0.2
    quality = np.full(GRID.shape, 2, dtype=np.uint8)
    quality[30:50, 30:40] = 0  # east half of the zone is excluded
    rel[quality == 0] = np.nan
    return rel, quality, np.full(GRID.shape, 0.7)


def test_synthetic_intersection_is_exact() -> None:
    rel, quality, coh = _rasters()
    roads = [
        _road(1, [(700_000.0, 1_196_000.0), (706_000.0, 1_196_000.0)], name="Crossing Road", ref="R1"),
        _road(2, [(700_000.0, 1_197_500.0), (706_000.0, 1_197_500.0)], highway="secondary"),  # 500 m north
        _road(3, [(700_000.0, 1_199_500.0), (706_000.0, 1_199_500.0)], name="Far Road"),  # 2.5 km north
        _road(4, [(703_000.0, 1_196_000.0), (703_000.0, 1_196_400.0)], name="Crossing Road", bridge=True),
    ]
    cands = find_road_candidates([_zone()], roads, GRID, rel, quality, coh, CFG)
    by_name = {c.asset_name: c for c in cands}
    assert set(by_name) == {"Crossing Road (R1)", "Unnamed secondary road (OSM way 2)"}  # far road not listed

    crossing = by_name["Crossing Road (R1)"]
    assert crossing.relation == "overlaps" and crossing.distance_m == 0.0
    assert crossing.overlap_length_m == pytest.approx(2000.0 + 400.0, abs=1.0)  # both OSM ways, same name
    assert crossing.osm_way_ids == (1, 4) and crossing.name_source == "osm:name"
    assert crossing.bridge_tagged_length_m == pytest.approx(400.0, abs=1.0)
    ev = crossing.evidence
    assert ev.pixel_count == ev.valid_pixels + ev.caution_pixels + ev.excluded_pixels
    assert 0.3 < (ev.valid_fraction or 0) < 0.8 and ev.excluded_pixels > 0
    assert ev.p90_abs_los_m == pytest.approx(0.2)

    near = by_name["Unnamed secondary road (OSM way 2)"]
    assert near.relation == "near" and near.overlap_length_m == 0.0
    assert near.distance_m == pytest.approx(500.0, abs=1.0) and near.name_source == "unnamed"


def test_output_is_deterministic_and_handles_empty_inputs() -> None:
    rel, quality, coh = _rasters()
    roads = [_road(i, [(700_000.0, 1_196_000.0 + 10 * i), (706_000.0, 1_196_000.0 + 10 * i)]) for i in range(1, 6)]
    a = find_road_candidates([_zone()], roads, GRID, rel, quality, coh, CFG)
    b = find_road_candidates([_zone()], list(reversed(roads)), GRID, rel, quality, coh, CFG)
    assert [c.osm_way_ids for c in a] == [c.osm_way_ids for c in b]
    assert find_road_candidates([], roads, GRID, rel, quality, coh, CFG) == []
    assert find_road_candidates([_zone()], [], GRID, rel, quality, coh, CFG) == []


def test_road_coverage_counts_unobserved_pixels() -> None:
    _, quality, _ = _rasters()
    road = _road(1, [(700_050.0, 1_196_050.0), (709_950.0, 1_196_050.0)])  # along one pixel row
    cov = road_observation_coverage([road], GRID, quality)
    assert cov["road_pixels"] == 100 and cov["EXCLUDED"] == 10 and cov["VALID"] == 90

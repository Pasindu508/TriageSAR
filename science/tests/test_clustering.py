import numpy as np
import pytest
from affine import Affine
from pyproj import CRS

from triagesar.config import HotspotConfig
from triagesar.processing.clustering import (
    extract_hotspots,
    reference_to_component_median,
    reference_to_local_plane,
    screening_threshold,
)
from triagesar.processing.georeference import GridGeometry

GRID = GridGeometry(CRS.from_epsg(32619), Affine(100.0, 0, 700_000.0, 0, -100.0, 1_200_000.0), 60, 40)
CFG = HotspotConfig(threshold_floor_m=0.03, robust_sigma_multiplier=3.0, min_area_km2=0.05, connectivity=8)


def _scene() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rel = np.zeros(GRID.shape)
    rel[5:15, 5:25] = 0.20  # 200 px = 2.0 km2
    rel[30:32, 40:42] = -0.50  # 4 px = 0.04 km2 -> rejected by the minimum-area rule
    rel[20:26, 50:56] = -0.10  # 36 px = 0.36 km2
    quality = np.full(GRID.shape, 2, dtype=np.uint8)
    quality[8:10, 10:12] = 0  # excluded hole inside the first zone
    rel[8:10, 10:12] = np.nan
    coh = np.full(GRID.shape, 0.8)
    return rel, quality, coh


def test_reference_subtracts_component_median_and_never_interpolates() -> None:
    rc = np.array([[1.0, 1.2, 5.0, 5.4], [1.1, np.nan, 5.2, 9.0]])
    usable = np.array([[True, True, True, True], [True, False, True, False]])
    cc = np.array([[1, 1, 2, 2], [1, 1, 2, 2]])
    rel, info = reference_to_component_median(rc, usable, cc)
    assert info.component_reference_m == {1: pytest.approx(1.1), 2: pytest.approx(5.2)}
    np.testing.assert_allclose(rel[0], [-0.1, 0.1, -0.2, 0.2], atol=1e-12)
    assert np.isnan(rel[1, 1]) and np.isnan(rel[1, 3])  # unusable pixels stay empty


def test_screening_threshold_floor_and_robust_rule() -> None:
    quiet = screening_threshold(np.random.default_rng(0).normal(0, 0.002, 5000), CFG)
    assert quiet.binding == "floor" and quiet.threshold_m == 0.03
    noisy = screening_threshold(np.random.default_rng(0).normal(0, 0.05, 5000), CFG)
    assert noisy.binding == "robust_sigma" and noisy.threshold_m == pytest.approx(0.15, rel=0.1)
    assert "MAD" in noisy.rule


def test_zones_area_stats_and_polygonisation() -> None:
    rel, quality, coh = _scene()
    thr = screening_threshold(rel, CFG)
    zones, labels = extract_hotspots(rel, quality, coh, GRID, CFG, thr)
    assert [z.zone_id for z in zones] == ["Z01", "Z02"]  # ordered by largest |LOS|; tiny blob rejected
    big, small = zones
    assert big.pixel_count == 196 and big.area_km2 == pytest.approx(1.96)
    assert big.polygon.area == pytest.approx(1.96e6)  # polygon area equals pixel area
    assert big.footprint_pixel_count == 200 and big.excluded_fraction == pytest.approx(4 / 200)
    assert big.median_los_m == pytest.approx(0.20) and big.max_abs_los_m == pytest.approx(0.20)
    assert small.median_los_m == pytest.approx(-0.10) and small.area_km2 == pytest.approx(0.36)
    assert set(np.unique(labels)) == {0, 1, 2}
    minx, miny, maxx, maxy = big.polygon.bounds
    assert (minx, maxy) == (700_500.0, 1_199_500.0) and (maxx, miny) == (702_500.0, 1_198_500.0)


def test_excluded_pixels_cannot_form_zones() -> None:
    rel, quality, coh = _scene()
    quality[:] = 0
    zones, _ = extract_hotspots(rel, quality, coh, GRID, CFG, screening_threshold(rel, CFG))
    assert zones == []


def test_connectivity_setting() -> None:
    rel = np.zeros(GRID.shape)
    rel[0:8, 0:8] = 0.2
    rel[8:16, 8:16] = 0.2  # touches the first block only diagonally
    quality = np.full(GRID.shape, 2, dtype=np.uint8)
    coh = np.ones(GRID.shape)
    thr = screening_threshold(rel, CFG)
    eight, _ = extract_hotspots(rel, quality, coh, GRID, CFG, thr)
    four, _ = extract_hotspots(rel, quality, coh, GRID, CFG.model_copy(update={"connectivity": 4}), thr)
    assert len(eight) == 1 and len(four) == 2


def test_local_plane_removes_trends_and_keeps_local_features() -> None:
    rng = np.random.default_rng(0)
    y, x = np.mgrid[0:200, 0:300].astype(float)
    trend = 0.3 + 0.002 * x - 0.001 * y  # a 60 cm tilt across the scene
    usable = rng.uniform(size=trend.shape) > 0.4
    usable[:, 140:170] = False  # a gap, so many windows are lopsided
    flat, info = reference_to_local_plane(trend, usable, None, 51, 0.25)
    assert info.method == "local_plane" and info.window_px == 51
    assert np.nanmax(np.abs(flat)) < 1e-9  # a linear trend is removed exactly, even beside the gap
    assert np.isnan(flat[~usable]).all()  # nothing is interpolated into unusable pixels
    assert info.unreferenced_pixels == int(np.count_nonzero(usable & ~np.isfinite(flat)))

    bump = 0.2 * np.exp(-(((y - 100) / 6) ** 2 + ((x - 70) / 6) ** 2) / 2)
    local, _ = reference_to_local_plane(trend + bump, usable, None, 51, 0.25)
    assert 0.17 < np.nanmax(local) < 0.2  # the local feature survives almost intact
    assert np.nanmax(np.abs(local[:, 200:])) < 1e-9  # and nothing appears far away from it


def test_local_plane_keeps_unwrapped_regions_apart() -> None:
    y, x = np.mgrid[0:120, 0:160].astype(float)
    cc = np.ones(x.shape, dtype=int)
    cc[:, 80:] = 2
    field = 0.001 * x + np.where(cc == 2, 5.0, 0.0)  # region 2 carries an arbitrary 5 m offset
    usable = np.ones(x.shape, dtype=bool)
    separate, _ = reference_to_local_plane(field, usable, cc, 31, 0.25)
    assert np.nanmax(np.abs(separate)) < 1e-9  # the offset between regions never leaks into the result
    merged, _ = reference_to_local_plane(field, usable, None, 31, 0.25)
    assert np.nanmax(np.abs(merged)) > 1.0  # ...which is what would happen if regions were mixed


def test_local_plane_needs_enough_neighbours_and_a_valid_window() -> None:
    field = np.zeros((60, 60))
    usable = np.zeros(field.shape, dtype=bool)
    usable[30, 5:55] = True  # a single row: collinear, no plane can be fitted
    usable[10:13, 10:13] = True  # a tiny isolated patch: too few neighbours
    out, info = reference_to_local_plane(field, usable, None, 21, 0.25)
    assert np.isnan(out).all() and info.unreferenced_pixels == int(usable.sum())
    for bad in (2, 20):
        with pytest.raises(ValueError):
            reference_to_local_plane(field, usable, None, bad, 0.25)

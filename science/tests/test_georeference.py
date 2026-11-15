import numpy as np
import pytest
from affine import Affine
from pyproj import CRS
from shapely.geometry import Point

from triagesar.processing import georeference as geo


def test_grid_from_coordinates_uses_pixel_centres() -> None:
    x = 500_000.0 + 80.0 * np.arange(10)
    y = 1_000_000.0 - 80.0 * np.arange(5)
    grid = geo.grid_from_coordinates(x, y, CRS.from_epsg(32619))
    assert grid.transform == Affine(80.0, 0.0, 499_960.0, 0.0, -80.0, 1_000_040.0)
    assert grid.bounds == (499_960.0, 999_640.0, 500_760.0, 1_000_040.0)
    assert grid.pixel_area_m2() == pytest.approx(6400.0)
    assert grid.metric_crs() == CRS.from_epsg(32619)
    with pytest.raises(ValueError, match="descending"):
        geo.grid_from_coordinates(x, y[::-1], CRS.from_epsg(32619))


def test_geographic_grid_gets_metric_crs_and_area() -> None:
    grid = geo.GridGeometry(CRS.from_epsg(4326), Affine(0.001, 0, -67.5, 0, -0.001, 10.5), 100, 100)
    assert grid.metric_crs() == CRS.from_epsg(32619)
    # ~110.6 m x ~109.5 m at 10.45 N
    assert grid.pixel_area_m2() == pytest.approx(110.6 * 109.5, rel=0.01)


def test_utm_zone_selection() -> None:
    assert geo.utm_crs_for(-67.2, 10.6).to_epsg() == 32619
    assert geo.utm_crs_for(151.2, -33.9).to_epsg() == 32756


def test_reprojection_round_trip() -> None:
    utm = CRS.from_epsg(32619)
    pt = geo.reproject_geometry(Point(-67.22, 10.60), geo.WGS84, utm)
    back = geo.reproject_geometry(pt, utm, geo.WGS84)
    assert back.x == pytest.approx(-67.22, abs=1e-8) and back.y == pytest.approx(10.60, abs=1e-8)
    assert 600_000 < pt.x < 800_000 and 1_100_000 < pt.y < 1_200_000


@pytest.mark.parametrize("bbox", [(1, 0, 0, 1), (0, 1, 1, 0), (-200, 0, 1, 1), (0, 0, 1, 95), (0, 0, float("nan"), 1)])
def test_bbox_validation(bbox: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError):
        geo.validate_bbox_wgs84(bbox)


def test_transform_bounds_encloses_corners() -> None:
    w, s, e, n = geo.transform_bounds(geo.WGS84, CRS.from_epsg(32619), (-68.0, 10.0, -67.0, 10.7))
    tr = geo.transformer(geo.WGS84, CRS.from_epsg(32619))
    for lon, lat in [(-68.0, 10.0), (-67.0, 10.0), (-68.0, 10.7), (-67.0, 10.7)]:
        x, y = tr.transform(lon, lat)
        assert w <= x <= e and s <= y <= n

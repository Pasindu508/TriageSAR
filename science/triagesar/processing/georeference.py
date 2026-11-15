"""Grid geometry, CRS handling and bbox <-> pixel-window conversion."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import shapely
from affine import Affine
from pyproj import CRS, Transformer
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

WGS84 = CRS.from_epsg(4326)


@dataclass(frozen=True)
class GridGeometry:
    """A north-up regular grid. ``transform`` maps pixel *corners* to CRS coordinates."""

    crs: CRS
    transform: Affine
    width: int
    height: int

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) in the grid CRS."""
        x0, y0 = self.transform @ (0, 0)
        x1, y1 = self.transform @ (self.width, self.height)
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def bounds_wgs84(self) -> tuple[float, float, float, float]:
        return transform_bounds(self.crs, WGS84, self.bounds)

    def pixel_area_m2(self) -> float:
        """Ground area of one pixel. Exact for projected metre grids; for geographic
        grids it is evaluated at the grid centre latitude (documented approximation)."""
        dx, dy = abs(self.transform.a), abs(self.transform.e)
        if self.crs.is_geographic:
            w, s, e, n = self.bounds
            lat = math.radians((s + n) / 2.0)
            a, f = 6_378_137.0, 1 / 298.257223563
            e2 = f * (2 - f)
            den = 1 - e2 * math.sin(lat) ** 2
            m_per_deg_lat = math.pi / 180 * a * (1 - e2) / den**1.5
            m_per_deg_lon = math.pi / 180 * a * math.cos(lat) / math.sqrt(den)
            return dx * m_per_deg_lon * dy * m_per_deg_lat
        factor = self.crs.axis_info[0].unit_conversion_factor or 1.0
        return dx * factor * dy * factor

    def metric_crs(self) -> CRS:
        """CRS in metres used for lengths, buffers and distances."""
        if self.crs.is_projected and abs((self.crs.axis_info[0].unit_conversion_factor or 1.0) - 1.0) < 1e-9:
            return self.crs
        w, s, e, n = self.bounds_wgs84()
        return utm_crs_for(lon=(w + e) / 2.0, lat=(s + n) / 2.0)


def utm_crs_for(lon: float, lat: float) -> CRS:
    zone = int(math.floor((lon + 180.0) / 6.0)) % 60 + 1
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def grid_from_coordinates(x: np.ndarray, y: np.ndarray, crs: CRS) -> GridGeometry:
    """Build grid geometry from pixel-centre coordinate vectors (y must be descending)."""
    dx = float(x[1] - x[0])
    dy = float(y[1] - y[0])
    if dy > 0:
        raise ValueError("y coordinates must be descending (north-up); flip rows first")
    transform = Affine(dx, 0.0, float(x[0]) - dx / 2.0, 0.0, dy, float(y[0]) - dy / 2.0)
    return GridGeometry(crs=crs, transform=transform, width=int(x.size), height=int(y.size))


@lru_cache(maxsize=32)
def _cached_transformer(src_wkt: str, dst_wkt: str) -> Transformer:
    return Transformer.from_crs(CRS.from_wkt(src_wkt), CRS.from_wkt(dst_wkt), always_xy=True)


def transformer(src: CRS, dst: CRS) -> Transformer:
    """A (cached) transformer between two CRSs, always in x/y (lon/lat) order."""
    return _cached_transformer(src.to_wkt(), dst.to_wkt())


def transform_bounds(
    src: CRS, dst: CRS, bounds: tuple[float, float, float, float], densify: int = 21
) -> tuple[float, float, float, float]:
    """Transform a bounding box, densifying edges so curved edges are enclosed."""
    w, s, e, n = bounds
    if src == dst:
        return bounds
    xs = np.linspace(w, e, densify)
    ys = np.linspace(s, n, densify)
    edge_x = np.concatenate([xs, xs, np.full(densify, w), np.full(densify, e)])
    edge_y = np.concatenate([np.full(densify, s), np.full(densify, n), ys, ys])
    tx, ty = transformer(src, dst).transform(edge_x, edge_y)
    tx, ty = np.asarray(tx), np.asarray(ty)
    if not (np.all(np.isfinite(tx)) and np.all(np.isfinite(ty))):
        raise ValueError("Bounding box cannot be transformed to the target CRS")
    return (float(tx.min()), float(ty.min()), float(tx.max()), float(ty.max()))


def validate_bbox_wgs84(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    w, s, e, n = (float(v) for v in bbox)
    if not all(math.isfinite(v) for v in (w, s, e, n)):
        raise ValueError("bbox values must be finite")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("bbox must be WEST SOUTH EAST NORTH with west < east, south < north, in degrees")
    return (w, s, e, n)


def window_for_bbox(
    x: np.ndarray, y: np.ndarray, crs: CRS, bbox_wgs84: tuple[float, float, float, float]
) -> tuple[slice, slice]:
    """Row/column slices (in file order) of pixels whose centres fall inside the bbox."""
    w, s, e, n = transform_bounds(WGS84, crs, validate_bbox_wgs84(bbox_wgs84))
    cols = np.flatnonzero((x >= w) & (x <= e))
    rows = np.flatnonzero((y >= s) & (y <= n))
    if cols.size == 0 or rows.size == 0:
        raise ValueError("Requested AOI does not overlap the product grid")
    return slice(int(rows.min()), int(rows.max()) + 1), slice(int(cols.min()), int(cols.max()) + 1)


def reproject_geometry(geom: BaseGeometry, src: CRS, dst: CRS) -> BaseGeometry:
    if src == dst:
        return geom
    tr = transformer(src, dst)
    return shapely.transform(geom, lambda x, y: tr.transform(x, y), interleaved=False)


def bbox_polygon(bounds: tuple[float, float, float, float]) -> BaseGeometry:
    return box(*bounds)

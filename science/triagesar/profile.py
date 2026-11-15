"""Line-of-sight profiles and small evidence thumbnails, sampled from the analysis grids.

Both are views of values already computed by the pipeline; nothing is interpolated into excluded pixels.
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass

import numpy as np
from affine import Affine
from PIL import Image
from rasterio import features
from shapely.geometry import LineString, MultiLineString, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge

from .processing.georeference import WGS84, GridGeometry, reproject_geometry
from .processing.quality import QualityState
from .render import CAUTION_RGB, EXCLUDED_RGB, NEGATIVE_RGB, NEUTRAL_RGB, POSITIVE_RGB


@dataclass(frozen=True)
class Profile:
    distance_km: list[float]
    local_m: list[float | None]
    scene_m: list[float | None]
    state: list[str]
    kind: str  # "road" (along the road) or "transect" (west-east line through a zone)
    length_km: float


def _longest_line(geom: BaseGeometry) -> LineString | None:
    if isinstance(geom, LineString):
        return geom
    if isinstance(geom, MultiLineString):
        merged = linemerge(geom)
        lines = [merged] if isinstance(merged, LineString) else list(merged.geoms)
        return max(lines, key=lambda g: g.length) if lines else None
    return None


def zone_transect(zone_wgs84: BaseGeometry, grid: GridGeometry, extend_m: float = 2000.0) -> LineString:
    """A straight line through the zone's representative point along its longer bounding-box axis."""
    metric = grid.metric_crs()
    z = reproject_geometry(zone_wgs84, WGS84, metric)
    minx, miny, maxx, maxy = z.bounds
    c = z.representative_point()
    if (maxx - minx) >= (maxy - miny):
        line = LineString([(minx - extend_m, c.y), (maxx + extend_m, c.y)])
    else:
        line = LineString([(c.x, maxy + extend_m), (c.x, miny - extend_m)])
    return reproject_geometry(line, metric, WGS84)  # type: ignore[return-value]


def sample_profile(
    line_wgs84: BaseGeometry,
    grid: GridGeometry,
    local_m: np.ndarray,
    scene_m: np.ndarray,
    quality_state: np.ndarray,
    kind: str,
    max_points: int = 400,
) -> Profile | None:
    """Sample the grids along a line at about one-pixel spacing (nearest pixel, no interpolation)."""
    line = _longest_line(line_wgs84)
    if line is None or line.length == 0:
        return None
    metric = grid.metric_crs()
    line_m = reproject_geometry(line, WGS84, metric)
    pixel = math.sqrt(grid.pixel_area_m2())
    n = int(min(max_points, max(2, line_m.length // pixel + 1)))
    dists = np.linspace(0.0, line_m.length, n)
    pts_m = [line_m.interpolate(d) for d in dists]
    pts_grid = reproject_geometry(LineString(pts_m), metric, grid.crs)
    inv = ~grid.transform
    names = {int(s): s.name for s in QualityState}
    local: list[float | None] = []
    scene: list[float | None] = []
    state: list[str] = []
    for x, y in pts_grid.coords:
        col, row = inv @ (x, y)
        r, c = int(math.floor(row)), int(math.floor(col))
        if not (0 <= r < grid.height and 0 <= c < grid.width):
            local.append(None)
            scene.append(None)
            state.append("OUTSIDE")
            continue
        lv, sv = local_m[r, c], scene_m[r, c]
        local.append(float(lv) if np.isfinite(lv) else None)
        scene.append(float(sv) if np.isfinite(sv) else None)
        state.append(names.get(int(quality_state[r, c]), "EXCLUDED"))
    return Profile(
        distance_km=[round(float(d) / 1000, 4) for d in dists],
        local_m=local,
        scene_m=scene,
        state=state,
        kind=kind,
        length_km=round(line_m.length / 1000, 3),
    )


def thumbnail_png(
    target_wgs84: BaseGeometry,
    grid: GridGeometry,
    local_m: np.ndarray,
    quality_state: np.ndarray,
    colour_limit_m: float,
    margin_m: float = 1500.0,
    size: tuple[int, int] = (240, 160),
) -> bytes | None:
    """Small picture of the local-motion field and quality around a zone or road (native grid, upscaled)."""
    target = reproject_geometry(target_wgs84, WGS84, grid.crs)
    minx, miny, maxx, maxy = target.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    half_w = max(maxx - minx, (maxy - miny) * size[0] / size[1]) / 2 + margin_m
    half_h = half_w * size[1] / size[0]
    inv = ~grid.transform
    c0, r0 = inv @ (cx - half_w, cy + half_h)
    c1, r1 = inv @ (cx + half_w, cy - half_h)
    c0, c1 = sorted((int(math.floor(c0)), int(math.ceil(c1))))
    r0, r1 = sorted((int(math.floor(r0)), int(math.ceil(r1))))
    if c1 <= 0 or r1 <= 0 or c0 >= grid.width or r0 >= grid.height:
        return None
    h, w = r1 - r0, c1 - c0
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[...] = (16, 26, 44, 255)
    rs, cs = slice(max(r0, 0), min(r1, grid.height)), slice(max(c0, 0), min(c1, grid.width))
    dr, dc = rs.start - r0, cs.start - c0
    vals = local_m[rs, cs]
    st = quality_state[rs, cs]
    t = np.clip(np.nan_to_num(vals / colour_limit_m), -1, 1)
    mag = np.abs(t)[..., None]
    end = np.where((t >= 0)[..., None], np.array(POSITIVE_RGB, float), np.array(NEGATIVE_RGB, float))
    rgb = np.array(NEUTRAL_RGB, float) * 0.35 * (1 - mag) + end * mag
    block = rgba[dr : dr + vals.shape[0], dc : dc + vals.shape[1]]
    ok = np.isfinite(vals)
    block[ok, :3] = rgb[ok].astype(np.uint8)
    rr, cc = np.indices(vals.shape)
    excluded = st == int(QualityState.EXCLUDED)
    block[excluded, :3] = np.where((((rr + cc) % 4) < 1)[excluded][:, None], EXCLUDED_RGB, (40, 52, 74))
    caution = (st == int(QualityState.CAUTION)) & ((rr % 3 == 0) & (cc % 3 == 0))
    block[caution, :3] = CAUTION_RGB
    img = Image.fromarray(rgba, "RGBA").resize(size, Image.Resampling.NEAREST)
    # Draw the outline at output resolution so it stays a thin line however small the zone is.
    out_transform = grid.transform @ Affine.translation(c0, r0) @ Affine.scale(w / size[0], h / size[1])
    clip = target.intersection(box(cx - half_w, cy - half_h, cx + half_w, cy + half_h))
    outline = clip.exterior if clip.geom_type == "Polygon" else clip
    if clip.geom_type == "MultiPolygon":
        outline = MultiLineString([poly.exterior for poly in clip.geoms])
    if not outline.is_empty:
        mask = features.rasterize([(outline, 1)], out_shape=(size[1], size[0]), transform=out_transform, all_touched=True)
        arr = np.array(img)
        arr[mask == 1, :3] = (255, 255, 255)
        img = Image.fromarray(arr, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()

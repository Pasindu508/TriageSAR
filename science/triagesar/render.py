"""Display-only raster overlays (PNG, Web Mercator). Analysis never uses these resampled images."""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image
from pyproj import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject

from .processing.georeference import WGS84, GridGeometry, transformer
from .processing.quality import QualityState

WEB_MERCATOR = CRS.from_epsg(3857)
NEGATIVE_RGB = (86, 180, 233)  # sky blue: range decrease (towards the satellite)
POSITIVE_RGB = (230, 159, 0)  # orange: range increase (away from the satellite)
NEUTRAL_RGB = (232, 236, 241)
EXCLUDED_RGB = (148, 163, 184)
CAUTION_RGB = (250, 204, 21)


@dataclass(frozen=True)
class Overlays:
    displacement_png: bytes
    quality_png: bytes
    #: MapLibre image-source corners: top-left, top-right, bottom-right, bottom-left (lon, lat)
    coordinates: list[list[float]]
    width: int
    height: int
    colour_limit_m: float | None
    #: motion relative to the local surroundings (the field used for zones); None when it equals the scene field
    local_png: bytes | None = None
    local_colour_limit_m: float | None = None


def _warp(array: np.ndarray, grid: GridGeometry, nodata: float) -> tuple[np.ndarray, list[list[float]]]:
    dst_transform, width, height = calculate_default_transform(
        grid.crs.to_wkt(), WEB_MERCATOR.to_wkt(), grid.width, grid.height, *grid.bounds
    )
    out = np.full((height, width), nodata, dtype=array.dtype)
    reproject(
        source=array,
        destination=out,
        src_transform=grid.transform,
        src_crs=grid.crs.to_wkt(),
        dst_transform=dst_transform,
        dst_crs=WEB_MERCATOR.to_wkt(),
        resampling=Resampling.nearest,
        src_nodata=nodata,
        dst_nodata=nodata,
    )
    to_wgs = transformer(WEB_MERCATOR, WGS84)
    corners = [dst_transform @ (0, 0), dst_transform @ (width, 0), dst_transform @ (width, height), dst_transform @ (0, height)]
    coords = [[round(v, 7) for v in to_wgs.transform(x, y)] for x, y in corners]
    return out, coords


def _png(rgba: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def colour_limit(relative_m: np.ndarray) -> float | None:
    """Symmetric colour-scale limit: 98th percentile of |relative LOS| over usable pixels."""
    vals = np.abs(relative_m[np.isfinite(relative_m)])
    if not vals.size:
        return None
    limit = float(np.percentile(vals, 98))
    return limit if limit > 0 else None


def _motion_png(
    grid: GridGeometry, field_m: np.ndarray, limit: float | None = None
) -> tuple[bytes, list[list[float]], float | None]:
    sentinel = -9999.0
    field = np.where(np.isfinite(field_m), field_m, sentinel).astype(np.float32)
    warped, coords = _warp(field, grid, sentinel)
    limit = limit if limit is not None else colour_limit(field_m)
    rgba = np.zeros((*warped.shape, 4), dtype=np.uint8)
    has = warped != sentinel
    if limit is not None and has.any():
        t = np.clip(warped / limit, -1.0, 1.0)
        mag = np.abs(t)[..., None]
        end = np.where((t >= 0)[..., None], np.array(POSITIVE_RGB, dtype=np.float32), np.array(NEGATIVE_RGB, dtype=np.float32))
        rgb = np.array(NEUTRAL_RGB, dtype=np.float32) * (1 - mag) + end * mag
        rgba[..., :3] = np.where(has[..., None], rgb, 0).astype(np.uint8)
        rgba[..., 3] = np.where(has, (70 + 170 * np.abs(t)).astype(np.uint8), 0)
    return _png(rgba), coords, limit


def render_overlays(
    grid: GridGeometry,
    relative_m: np.ndarray,
    quality_state: np.ndarray,
    local_m: np.ndarray | None = None,
    local_limit_m: float | None = None,
) -> Overlays:
    """Render the scene-relative motion, the quality states and, optionally, the local-motion field.

    ``local_limit_m`` fixes the colour limit of the local layer; the pipeline passes the screening
    threshold, so full colour means "at or above the level that can form a zone" and ordinary
    scatter stays faint.
    """
    disp_png, coords, limit = _motion_png(grid, relative_m)
    state_w, _ = _warp(quality_state.astype(np.uint8), grid, 255)
    h, w = state_w.shape
    rr, cc = np.indices((h, w))
    qual = np.zeros((h, w, 4), dtype=np.uint8)
    excluded = state_w == int(QualityState.EXCLUDED)
    caution = state_w == int(QualityState.CAUTION)
    # Redundant, non-colour encoding: excluded = diagonal hatch "/", caution = dots.
    hatch = ((rr + cc) % 10) < 3
    dots = ((rr % 6) < 2) & ((cc % 6) < 2)
    qual[excluded] = (*EXCLUDED_RGB, 70)
    qual[excluded & hatch] = (*EXCLUDED_RGB, 200)
    qual[caution & dots] = (*CAUTION_RGB, 230)
    local_png, local_limit = None, None
    if local_m is not None:
        local_png, _, local_limit = _motion_png(grid, local_m, local_limit_m)
    return Overlays(disp_png, _png(qual), coords, w, h, limit, local_png, local_limit)

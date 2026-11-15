"""Relative referencing, screening threshold and contiguous deformation-zone extraction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from rasterio import features
from scipy import ndimage
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from ..config import HotspotConfig
from . import statistics as st
from .georeference import GridGeometry
from .quality import QualityState


@dataclass(frozen=True)
class ReferenceInfo:
    method: str
    #: connected-component id -> median LOS range change (m) subtracted from that component
    component_reference_m: dict[int, float]
    #: side of the local reference window in pixels (local_plane only)
    window_px: int | None = None
    #: usable pixels that could not be given a local reference (too few usable neighbours)
    unreferenced_pixels: int = 0


@dataclass(frozen=True)
class ThresholdInfo:
    threshold_m: float
    floor_m: float
    robust_sigma_m: float | None
    mad_m: float | None
    multiplier: float
    rule: str
    binding: str  # "floor" or "robust_sigma"


@dataclass(frozen=True)
class Hotspot:
    zone_id: str
    label: int
    pixel_count: int
    footprint_pixel_count: int
    area_km2: float
    median_los_m: float
    max_abs_los_m: float
    p90_abs_los_m: float
    iqr_los_m: float
    valid_fraction: float
    caution_fraction: float
    excluded_fraction: float
    median_coherence: float | None
    coherence_summary: dict[str, float] | None
    component_ids: tuple[int, ...]
    polygon: BaseGeometry  # in the grid CRS


def reference_to_component_median(
    range_change_m: np.ndarray,
    usable: np.ndarray,
    connected_components: np.ndarray | None,
) -> tuple[np.ndarray, ReferenceInfo]:
    """Subtract, per unwrapped connected component, the median of its usable pixels.

    Unwrapped phase carries an arbitrary constant per connected component, so only
    differences *within* a component are meaningful. Pixels that are not usable
    become NaN in the result; nothing is interpolated.
    """
    relative = np.full(range_change_m.shape, np.nan, dtype=np.float64)
    refs: dict[int, float] = {}
    if connected_components is None:
        if np.any(usable):
            ref = float(np.median(range_change_m[usable]))
            refs[1] = ref
            relative[usable] = range_change_m[usable] - ref
        return relative, ReferenceInfo("aoi_median_no_components", refs)
    for comp_id in np.unique(connected_components[usable]):
        sel = usable & (connected_components == comp_id)
        ref = float(np.median(range_change_m[sel]))
        refs[int(comp_id)] = ref
        relative[sel] = range_change_m[sel] - ref
    return relative, ReferenceInfo("component_median", refs)


def reference_to_local_plane(
    range_change_m: np.ndarray,
    usable: np.ndarray,
    connected_components: np.ndarray | None,
    window_px: int,
    min_fraction: float,
) -> tuple[np.ndarray, ReferenceInfo]:
    """Subtract, at every pixel, a plane fitted to its usable neighbours of the same unwrapped region.

    The plane ``a + b*u + c*v`` is fitted by least squares to the usable pixels inside a square
    ``window_px`` window centred on the pixel (``u``, ``v`` are offsets from the centre), and the
    result is ``value - a``. A locally linear trend is removed exactly, even when the usable pixels
    are unevenly spread around the centre, so only motion that *differs from the surroundings*
    remains. Pixels with fewer than ``min_fraction`` of the window usable, or whose neighbours are
    too nearly collinear to define a plane, get NaN. Nothing is interpolated.
    """
    if window_px < 3 or window_px % 2 == 0:
        raise ValueError("window_px must be an odd number >= 3")
    out = np.full(range_change_m.shape, np.nan, dtype=np.float64)
    comp_ids: list[int | None] = [None]
    if connected_components is not None:
        comp_ids = [int(c) for c in np.unique(connected_components[usable])]
    pad = window_px // 2
    variance_floor = 1e-3 * (window_px * window_px / 12.0) ** 2  # rejects near-collinear footprints

    def box(a: np.ndarray) -> np.ndarray:
        return ndimage.uniform_filter(a, size=window_px, mode="constant", cval=0.0)

    for comp in comp_ids:
        member = usable if comp is None else usable & (connected_components == comp)
        rows, cols = np.flatnonzero(member.any(axis=1)), np.flatnonzero(member.any(axis=0))
        if rows.size == 0:
            continue
        sl = (
            slice(max(0, rows[0] - pad), min(member.shape[0], rows[-1] + pad + 1)),
            slice(max(0, cols[0] - pad), min(member.shape[1], cols[-1] + pad + 1)),
        )
        m = member[sl]
        w = m.astype(np.float64)
        d = np.where(m, range_change_m[sl], 0.0)
        y, x = np.mgrid[0 : m.shape[0], 0 : m.shape[1]].astype(np.float64)
        s0, sx, sy = box(w), box(w * x), box(w * y)
        sxx, sxy, syy = box(w * x * x), box(w * x * y), box(w * y * y)
        sd, sxd, syd = box(d), box(d * x), box(d * y)
        # Moments about each window centre.
        u, v = sx - x * s0, sy - y * s0
        uu = sxx - 2 * x * sx + x * x * s0
        uv = sxy - x * sy - y * sx + x * y * s0
        vv = syy - 2 * y * sy + y * y * s0
        ud, vd = sxd - x * sd, syd - y * sd
        minor = uu * vv - uv * uv
        det = s0 * minor - u * (u * vv - uv * v) + v * (u * uv - uu * v)
        det_a = sd * minor - u * (ud * vv - uv * vd) + v * (ud * uv - uu * vd)
        ok = m & (s0 >= min_fraction) & (det > variance_floor * s0**3)
        intercept = np.divide(det_a, det, out=np.zeros_like(det), where=ok)
        block = out[sl]
        block[ok] = range_change_m[sl][ok] - intercept[ok]
    unreferenced = int(np.count_nonzero(usable & ~np.isfinite(out)))
    return out, ReferenceInfo("local_plane", {}, window_px=window_px, unreferenced_pixels=unreferenced)


def screening_threshold(relative_m: np.ndarray, cfg: HotspotConfig, quantity: str = "relative LOS range change") -> ThresholdInfo:
    """max(floor, k * 1.4826 * MAD) on |referenced LOS range change|. A screening rule."""
    mad = st.mad(relative_m)
    sigma = None if mad is None else st.MAD_TO_SIGMA * mad
    robust = None if sigma is None else cfg.robust_sigma_multiplier * sigma
    if robust is not None and robust > cfg.threshold_floor_m:
        threshold, binding = robust, "robust_sigma"
    else:
        threshold, binding = cfg.threshold_floor_m, "floor"
    rule = (
        f"|{quantity}| >= max({cfg.threshold_floor_m:g} m, "
        f"{cfg.robust_sigma_multiplier:g} x 1.4826 x MAD)"
    )
    return ThresholdInfo(threshold, cfg.threshold_floor_m, sigma, mad, cfg.robust_sigma_multiplier, rule, binding)


def _polygonise(mask: np.ndarray, grid: GridGeometry) -> BaseGeometry:
    geoms = [
        shape(geom)
        for geom, value in features.shapes(mask.astype(np.uint8), mask=mask, transform=grid.transform)
        if value == 1
    ]
    return unary_union(geoms)


def extract_hotspots(
    relative_m: np.ndarray,
    quality_state: np.ndarray,
    coherence: np.ndarray,
    grid: GridGeometry,
    cfg: HotspotConfig,
    threshold: ThresholdInfo,
    connected_components: np.ndarray | None = None,
) -> tuple[list[Hotspot], np.ndarray]:
    """Label contiguous regions of above-threshold, quality-approved pixels.

    Returns the zones (ordered by largest |LOS| first, deterministic) and an
    int32 label raster whose values match ``Hotspot.label`` (0 = no zone).
    """
    allowed = quality_state == int(QualityState.VALID)
    if cfg.include_caution_pixels:
        allowed |= quality_state == int(QualityState.CAUTION)
    with np.errstate(invalid="ignore"):
        candidate = allowed & np.isfinite(relative_m) & (np.abs(relative_m) >= threshold.threshold_m)

    structure = np.ones((3, 3), dtype=bool) if cfg.connectivity == 8 else ndimage.generate_binary_structure(2, 1)
    labels, n_labels = ndimage.label(candidate, structure=structure)
    pixel_area_km2 = grid.pixel_area_m2() / 1e6
    out_labels = np.zeros(labels.shape, dtype=np.int32)
    raw: list[Hotspot] = []
    slices = ndimage.find_objects(labels)
    for label in range(1, n_labels + 1):
        sl = slices[label - 1]
        if sl is None:
            continue
        region = labels[sl] == label
        count = int(region.sum())
        area = count * pixel_area_km2
        if area < cfg.min_area_km2:
            continue
        footprint = ndimage.binary_fill_holes(region)
        fp_count = int(footprint.sum())
        q = quality_state[sl][footprint]
        vals = relative_m[sl][region]
        coh = coherence[sl][region]
        comp_ids: tuple[int, ...] = ()
        if connected_components is not None:
            comp_ids = tuple(int(c) for c in np.unique(connected_components[sl][region]))
        full_mask = np.zeros(labels.shape, dtype=bool)
        full_mask[sl] = region
        raw.append(
            Hotspot(
                zone_id="",
                label=label,
                pixel_count=count,
                footprint_pixel_count=fp_count,
                area_km2=float(area),
                median_los_m=float(np.median(vals)),
                max_abs_los_m=float(np.max(np.abs(vals))),
                p90_abs_los_m=float(np.percentile(np.abs(vals), 90)),
                iqr_los_m=float(st.iqr(vals) or 0.0),
                valid_fraction=float(np.count_nonzero(q == int(QualityState.VALID)) / fp_count),
                caution_fraction=float(np.count_nonzero(q == int(QualityState.CAUTION)) / fp_count),
                excluded_fraction=float(np.count_nonzero(q == int(QualityState.EXCLUDED)) / fp_count),
                median_coherence=st.median(coh),
                coherence_summary=st.five_number_summary(coh),
                component_ids=comp_ids,
                polygon=_polygonise(full_mask, grid),
            )
        )
    raw.sort(key=lambda h: (-h.max_abs_los_m, -h.area_km2, h.label))
    zones: list[Hotspot] = []
    for index, h in enumerate(raw, start=1):
        zone = Hotspot(**{**h.__dict__, "zone_id": f"Z{index:02d}", "label": index})
        out_labels[labels == h.label] = index
        zones.append(zone)
    return zones, out_labels

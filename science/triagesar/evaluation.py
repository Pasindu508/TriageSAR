"""Reference-product consistency evaluation. This is NOT ground-truth validation.

Both TriageSAR and the reference product are derived from the same radar acquisitions, so
these metrics measure agreement between two processing chains, nothing more.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from scipy import ndimage

from .config import AnalysisConfig
from .pipeline import AnalysisArtifacts, referenced_field
from .processing import statistics as st
from .processing.clustering import screening_threshold
from .processing.georeference import GridGeometry

NOTE = (
    "Reference-product consistency evaluation, not ground-truth validation. The reference was resampled "
    "(bilinear) onto the fixture grid; it may come from a different processing version, may have had "
    "ionosphere and ramp corrections applied, and both products are relative to different reference levels, "
    "so each is re-referenced to its own median over the common pixels before the pixel comparison. For the "
    "zone comparison the reference field is passed through the same referencing, screening threshold and "
    "minimum-area rule as TriageSAR's own field."
)


def load_reference_on_grid(path: Path, grid: GridGeometry) -> np.ndarray:
    """Read band 1 of a GeoTIFF and resample it onto the analysis grid (NaN where there is no data)."""
    out = np.full(grid.shape, np.nan, dtype=np.float64)
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float64)
        if src.nodata is not None and np.isfinite(src.nodata):
            data[data == src.nodata] = np.nan
        reproject(
            source=data,
            destination=out,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=grid.transform,
            dst_crs=grid.crs.to_wkt(),
            resampling=Resampling.bilinear,
            src_nodata=np.nan,
            dst_nodata=np.nan,
        )
    return out


def compare_with_reference(art: AnalysisArtifacts, reference_m: np.ndarray, config: AnalysisConfig) -> dict[str, Any]:
    """Compare our scene-relative LOS range change with a reference in the same sign convention and units."""
    cfg = config.hotspot
    ours = art.relative_m
    common = np.isfinite(ours) & np.isfinite(reference_m)
    n = int(common.sum())
    report: dict[str, Any] = {"note": NOTE, "common_pixels": n, "fixture_pixels": int(ours.size)}
    if n < 100:
        report["status"] = "not computed: fewer than 100 common pixels"
        return report
    a = ours[common] - np.median(ours[common])
    b = reference_m[common] - np.median(reference_m[common])
    diff = a - b
    report.update(
        {
            "status": "computed",
            "pearson_r": float(np.corrcoef(a, b)[0, 1]),
            "difference_median_m": st.median(diff),
            "difference_mad_m": st.mad(diff),
            "difference_p95_abs_m": st.percentile(np.abs(diff), 95),
            "rmse_m": float(np.sqrt(np.mean(diff**2))),
        }
    )
    # Zone geometry agreement: pass the reference through the same referencing and screening rule.
    # The reference is partitioned with TriageSAR's unwrapped regions so both fields are referenced alike.
    ref = referenced_field(
        np.where(common, reference_m, np.nan), common, art.connected_components, art.grid, config
    )
    ref_field = ref.field
    finite = np.isfinite(ref_field)
    threshold = screening_threshold(ref_field[finite], cfg, ref.quantity)
    ours_zone = (art.zone_labels > 0) & common
    structure = np.ones((3, 3), dtype=bool) if cfg.connectivity == 8 else None
    with np.errstate(invalid="ignore"):
        candidate = finite & (np.abs(ref_field) >= threshold.threshold_m)
    labels, count = ndimage.label(candidate, structure=structure)
    min_pixels = cfg.min_area_km2 * 1e6 / art.grid.pixel_area_m2()
    sizes = ndimage.sum_labels(np.ones(labels.shape), labels, index=np.arange(1, count + 1)) if count else np.array([])
    keep = np.flatnonzero(sizes >= min_pixels) + 1
    ref_zone = np.isin(labels, keep)
    inter, union = int((ours_zone & ref_zone).sum()), int((ours_zone | ref_zone).sum())
    report["reference_method"] = ref.info.method
    report["reference_threshold_m"] = threshold.threshold_m
    report["zone_pixels_ours"] = int(ours_zone.sum())
    report["zone_pixels_reference"] = int(ref_zone.sum())
    report["zone_iou"] = (inter / union) if union else None
    if ours_zone.any() and ref_zone.any():
        ca, cb = ndimage.center_of_mass(ours_zone), ndimage.center_of_mass(ref_zone)
        px = float(np.hypot(ca[0] - cb[0], ca[1] - cb[1]))
        report["zone_centroid_distance_m"] = px * float(np.sqrt(art.grid.pixel_area_m2()))
    else:
        report["zone_centroid_distance_m"] = None
    return report

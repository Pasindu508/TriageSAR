from pathlib import Path

import numpy as np
import pytest
import rasterio

from triagesar.config import AnalysisConfig
from triagesar.evaluation import compare_with_reference, load_reference_on_grid
from triagesar.fixture import Fixture
from triagesar.infrastructure.osm import Road
from triagesar.pipeline import run_analysis


def _write(path: Path, data: np.ndarray, art) -> Path:  # type: ignore[no-untyped-def]
    with rasterio.open(path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1], count=1, dtype="float32",
                       crs=art.grid.crs.to_wkt(), transform=art.grid.transform, nodata=-9999.0) as dst:
        dst.write(np.where(np.isfinite(data), data, -9999.0).astype("float32"), 1)
    return path


def test_identical_reference_agrees_and_shifted_reference_does_not(
    tmp_path: Path, fixture: Fixture, roads: list[Road], config: AnalysisConfig
) -> None:
    art = run_analysis(fixture, roads, config)
    same = load_reference_on_grid(_write(tmp_path / "same.tif", art.relative_m + 0.5, art), art.grid)
    report = compare_with_reference(art, same, config)
    assert report["status"] == "computed" and "not ground-truth" in report["note"]
    assert report["pearson_r"] == pytest.approx(1.0, abs=1e-4)
    assert report["rmse_m"] < 1e-4 and report["zone_iou"] > 0.9 and report["reference_method"] == "local_plane"
    assert report["zone_centroid_distance_m"] < 100

    shifted = np.roll(art.relative_m, 60, axis=1)
    moved = load_reference_on_grid(_write(tmp_path / "moved.tif", shifted, art), art.grid)
    worse = compare_with_reference(art, moved, config)
    assert worse["zone_iou"] < 0.3 and worse["pearson_r"] < report["pearson_r"] and worse["zone_centroid_distance_m"] > 1000


def test_too_little_overlap_is_reported_as_not_computed(fixture: Fixture, roads: list[Road], config: AnalysisConfig) -> None:
    art = run_analysis(fixture, roads, config)
    report = compare_with_reference(art, np.full(art.grid.shape, np.nan), config)
    assert report["status"].startswith("not computed") and "pearson_r" not in report

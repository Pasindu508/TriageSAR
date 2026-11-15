"""Small, explicit summary statistics. Empty inputs give ``None``, never a made-up value."""

from __future__ import annotations

import numpy as np

MAD_TO_SIGMA = 1.4826  # scale factor making the MAD consistent with a Gaussian sigma


def _finite(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64).ravel()
    return arr[np.isfinite(arr)]


def median(values: np.ndarray) -> float | None:
    arr = _finite(values)
    return float(np.median(arr)) if arr.size else None


def mad(values: np.ndarray) -> float | None:
    """Median absolute deviation about the median."""
    arr = _finite(values)
    if not arr.size:
        return None
    return float(np.median(np.abs(arr - np.median(arr))))


def percentile(values: np.ndarray, q: float) -> float | None:
    arr = _finite(values)
    return float(np.percentile(arr, q)) if arr.size else None


def iqr(values: np.ndarray) -> float | None:
    arr = _finite(values)
    if not arr.size:
        return None
    p25, p75 = np.percentile(arr, [25, 75])
    return float(p75 - p25)


def max_abs(values: np.ndarray) -> float | None:
    arr = _finite(values)
    return float(np.max(np.abs(arr))) if arr.size else None


def five_number_summary(values: np.ndarray) -> dict[str, float] | None:
    arr = _finite(values)
    if not arr.size:
        return None
    mn, p25, med, p75, mx = np.percentile(arr, [0, 25, 50, 75, 100])
    return {"min": float(mn), "p25": float(p25), "median": float(med), "p75": float(p75), "max": float(mx)}

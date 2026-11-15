"""Interpretation of the GUNW ``mask`` layer.

Encoding (NISAR GUNW product specification JPL D-102272 Rev E, and the layer's own
``description`` attribute written by ISCE3):

* the fill value (255) marks pixels with no data;
* the low byte is a three-digit decimal number ``100 * water + 10 * ref + sec`` where
  ``water`` is 1 over water, and ``ref`` / ``sec`` are the sub-swath numbers of the pixel
  in the reference and secondary acquisitions (0 = invalid sample in that acquisition);
* newer products store the layer as uint32 and add anomaly flags for the secondary
  (bits 8-15) and reference (bits 16-23) acquisitions, and bit 24 for pixels whose
  ionosphere phase screen was interpolated.

TriageSAR flags (and therefore EXCLUDES) fill, water and invalid-sub-swath pixels. Anomaly
and ionosphere-interpolation bits are counted and reported but do not exclude a pixel,
because their individual meanings are not something this prototype interprets.
"""

from __future__ import annotations

import numpy as np


def decode_product_mask(mask: np.ndarray, fill_value: float | None) -> tuple[np.ndarray, str]:
    """Return (boolean array of flagged pixels, human-readable note on what was used)."""
    if mask.dtype.kind not in "iu":
        return np.zeros(mask.shape, dtype=bool), "mask layer is not an integer layer; ignored"
    values = mask.astype(np.int64)
    is_fill = np.zeros(mask.shape, dtype=bool)
    if fill_value is not None and np.isfinite(fill_value):
        is_fill = values == int(fill_value)
    low = values & 0xFF
    water = ~is_fill & (low // 100 == 1)
    invalid_sample = ~is_fill & (((low // 10) % 10 == 0) | (low % 10 == 0))
    anomaly = ~is_fill & (((values >> 8) & 0xFFFF) != 0)
    iono_interpolated = ~is_fill & (((values >> 24) & 1) == 1)
    flagged = is_fill | water | invalid_sample
    note = (
        f"product mask decoded as water flag / reference sub-swath / secondary sub-swath: "
        f"{int(is_fill.sum())} fill, {int(water.sum())} water and {int(invalid_sample.sum())} invalid-sample pixels "
        f"are flagged; {int(anomaly.sum())} pixels carry acquisition anomaly bits and "
        f"{int(iono_interpolated.sum())} carry the ionosphere-interpolation bit (reported, not excluded)"
    )
    return flagged, note

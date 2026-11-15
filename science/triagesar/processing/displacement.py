"""Unwrapped interferometric phase -> line-of-sight (LOS) range change.

Equation
--------
A repeat-pass interferogram measures the *two-way* path difference between the
two acquisitions, so a phase of 2*pi radians corresponds to half a wavelength
of one-way range change::

    delta_r [m] = PHASE_SIGN * wavelength [m] * phi [rad] / (4 * pi)

Sign convention
---------------
NISAR GUNW interferograms are formed as ``reference * conj(secondary)`` with the
ISCE3 SLC phase convention ``exp(-j * 4*pi * r / wavelength)``, so::

    phi = (4*pi / wavelength) * (r_secondary - r_reference)

A **positive** unwrapped phase therefore means the radar-to-ground distance
**increased** between the reference (earlier) and secondary (later) acquisition:
the ground moved *away from* the satellite along the line of sight.
``PHASE_SIGN = +1`` encodes that. TriageSAR reports "LOS range change" with
positive = away from the satellite, and ranks on its magnitude only, so the
inspection ranking does not depend on the sign.

The result is a one-dimensional projection of the true 3-D ground motion onto
the radar line of sight, and it is relative (an arbitrary constant per
unwrapped region). It is not a vertical or horizontal displacement.
"""

from __future__ import annotations

import math

import numpy as np

#: +1: positive phase = range increase (motion away from the satellite).
PHASE_SIGN = 1.0
SIGN_CONVENTION_TEXT = (
    "Positive LOS range change = ground moved away from the satellite along the radar "
    "line of sight between the reference (earlier) and secondary (later) acquisition."
)
EQUATION_TEXT = "delta_r [m] = wavelength [m] * unwrapped_phase [rad] / (4 * pi)"


def phase_to_los_range_change(phase_rad: np.ndarray, wavelength_m: float) -> np.ndarray:
    """Convert unwrapped phase in radians to LOS range change in metres.

    NaNs are preserved. ``wavelength_m`` must come from product metadata.
    """
    if not (isinstance(wavelength_m, (int, float)) and math.isfinite(wavelength_m) and wavelength_m > 0):
        raise ValueError(f"wavelength_m must be a positive finite number, got {wavelength_m!r}")
    phase = np.asarray(phase_rad, dtype=np.float64)
    return PHASE_SIGN * wavelength_m * phase / (4.0 * math.pi)


def metres_per_fringe(wavelength_m: float) -> float:
    """LOS range change corresponding to one full 2*pi phase cycle (half a wavelength)."""
    return wavelength_m / 2.0

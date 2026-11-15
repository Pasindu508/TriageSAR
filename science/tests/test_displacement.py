import math

import numpy as np
import pytest

from triagesar.nisar.schema import SPEED_OF_LIGHT_M_S
from triagesar.processing.displacement import PHASE_SIGN, metres_per_fringe, phase_to_los_range_change


def test_one_fringe_is_half_a_wavelength() -> None:
    wavelength = 0.24
    out = phase_to_los_range_change(np.array([2 * math.pi]), wavelength)
    assert out[0] == pytest.approx(wavelength / 2)
    assert metres_per_fringe(wavelength) == pytest.approx(0.12)


@pytest.mark.parametrize(
    ("phase", "wavelength", "expected"),
    [(0.0, 0.24, 0.0), (4 * math.pi, 0.24, 0.24), (math.pi, 0.2, 0.05), (-2 * math.pi, 0.1, -0.05)],
)
def test_analytic_cases(phase: float, wavelength: float, expected: float) -> None:
    assert phase_to_los_range_change(np.array([phase]), wavelength)[0] == pytest.approx(expected, abs=1e-12)


def test_sign_convention_positive_phase_is_range_increase() -> None:
    # phi = (4 pi / lambda) * (r_secondary - r_reference): the ground moved 3 cm away from the radar.
    wavelength, r_ref, r_sec = 0.24, 850_000.0, 850_000.03
    phi = 4 * math.pi / wavelength * (r_sec - r_ref)
    assert phi > 0 and PHASE_SIGN == 1.0
    assert phase_to_los_range_change(np.array([phi]), wavelength)[0] == pytest.approx(0.03, abs=1e-6)


def test_units_are_metres_for_frequency_derived_wavelength() -> None:
    wavelength = SPEED_OF_LIGHT_M_S / 1.25e9
    assert wavelength == pytest.approx(0.2398339664)
    assert phase_to_los_range_change(np.array([2 * math.pi]), wavelength)[0] == pytest.approx(0.1199169832)


def test_nan_and_shape_preserved() -> None:
    phase = np.array([[0.0, np.nan], [1.0, -1.0]], dtype=np.float32)
    out = phase_to_los_range_change(phase, 0.24)
    assert out.shape == phase.shape and out.dtype == np.float64
    assert np.isnan(out[0, 1]) and np.isfinite(out[~np.isnan(phase)]).all()


@pytest.mark.parametrize("bad", [0.0, -0.24, float("nan"), float("inf")])
def test_rejects_invalid_wavelength(bad: float) -> None:
    with pytest.raises(ValueError):
        phase_to_los_range_change(np.zeros(2), bad)

import numpy as np
import pytest

from triagesar.config import QualityConfig
from triagesar.processing.product_mask import decode_product_mask
from triagesar.processing.quality import QualityReason, QualityState, classify_quality, unmasked_quality

CFG = QualityConfig(small_component_pixels=3)


def test_states_and_reasons() -> None:
    phase = np.array([[0.1, np.nan, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]], dtype=np.float32)
    coh = np.array([[0.9, 0.9, 0.2, 0.4], [0.9, np.nan, 0.9, 0.9]], dtype=np.float32)
    cc = np.array([[1, 1, 1, 1], [0, 1, 2, 65535]], dtype=np.uint16)
    res = classify_quality(phase, coh, CFG, connected_components=cc, components_fill=65535)
    S, R = QualityState, QualityReason
    assert res.state.tolist() == [
        [S.VALID, S.EXCLUDED, S.EXCLUDED, S.CAUTION],
        [S.EXCLUDED, S.EXCLUDED, S.CAUTION, S.EXCLUDED],
    ]
    assert res.reasons[0, 1] & R.PHASE_MISSING
    assert res.reasons[0, 2] & R.LOW_COHERENCE
    assert res.reasons[0, 3] & R.MODERATE_COHERENCE
    assert res.reasons[1, 0] & R.UNWRAP_COMPONENT_ZERO
    assert res.reasons[1, 1] & R.COHERENCE_MISSING
    assert res.reasons[1, 2] & R.SMALL_COMPONENT
    assert res.reasons[1, 3] & R.UNWRAP_COMPONENT_ZERO
    assert res.counts() == {"EXCLUDED": 5, "CAUTION": 2, "VALID": 1}
    assert res.component_sizes == {1: 5, 2: 1}


def test_thresholds_are_configurable() -> None:
    phase = np.zeros((1, 3), dtype=np.float32)
    coh = np.array([[0.25, 0.45, 0.65]], dtype=np.float32)
    strict = classify_quality(phase, coh, QualityConfig(coherence_exclude_below=0.5, coherence_caution_below=0.7))
    loose = classify_quality(phase, coh, QualityConfig(coherence_exclude_below=0.1, coherence_caution_below=0.2))
    assert strict.state.tolist() == [[0, 0, 1]] and loose.state.tolist() == [[2, 2, 2]]
    with pytest.raises(ValueError):
        QualityConfig(coherence_exclude_below=0.6, coherence_caution_below=0.5)


def test_product_mask_propagates_and_can_be_disabled() -> None:
    phase = np.zeros((1, 2), dtype=np.float32)
    coh = np.ones((1, 2), dtype=np.float32)
    flagged = np.array([[True, False]])
    on = classify_quality(phase, coh, QualityConfig(), product_mask_invalid=flagged)
    off = classify_quality(phase, coh, QualityConfig(use_product_mask=False), product_mask_invalid=flagged)
    assert on.state.tolist() == [[0, 2]] and off.state.tolist() == [[2, 2]]


def test_decode_product_mask() -> None:
    mask = np.array([[11, 111, 255, 10, 1, 22]], dtype=np.uint8)
    flagged, note = decode_product_mask(mask, 255)
    assert flagged.tolist() == [[False, True, True, True, True, False]]
    assert "1 fill, 1 water and 2 invalid-sample" in note
    # uint32 layout: anomaly bits (8-23) and the ionosphere bit (24) are reported, not excluded
    wide = np.array([[11 | (1 << 8), 11 | (1 << 16), 11 | (1 << 24), 111 | (1 << 9), 255]], dtype=np.uint32)
    flagged, note = decode_product_mask(wide, 255)
    assert flagged.tolist() == [[False, False, False, True, True]]
    assert "3 pixels carry acquisition anomaly bits" in note and "1 carry the ionosphere-interpolation bit" in note
    assert not decode_product_mask(np.ones((1, 2), dtype=np.float32), None)[0].any()


def test_unmasked_quality_only_excludes_missing_phase() -> None:
    res = unmasked_quality(np.array([[np.nan, 1.0]], dtype=np.float32))
    assert res.state.tolist() == [[0, 2]]


def test_shape_mismatch_rejected() -> None:
    with pytest.raises(ValueError):
        classify_quality(np.zeros((2, 2)), np.zeros((2, 3)), QualityConfig())

"""Transparent per-pixel quality classification.

Every pixel is VALID, CAUTION or EXCLUDED, and carries a bit mask saying *why*.
The rules use only layers shipped with the product (coherence, connected
components, mask) and the thresholds in ``config/triagesar.toml``. Nothing here
is a statistical confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, IntFlag

import numpy as np

from ..config import QualityConfig


class QualityState(IntEnum):
    EXCLUDED = 0
    CAUTION = 1
    VALID = 2


class QualityReason(IntFlag):
    NONE = 0
    PHASE_MISSING = 1
    COHERENCE_MISSING = 2
    LOW_COHERENCE = 4
    UNWRAP_COMPONENT_ZERO = 8
    PRODUCT_MASK = 16
    MODERATE_COHERENCE = 32  # caution
    SMALL_COMPONENT = 64  # caution


EXCLUSION_REASONS = (
    QualityReason.PHASE_MISSING,
    QualityReason.COHERENCE_MISSING,
    QualityReason.LOW_COHERENCE,
    QualityReason.UNWRAP_COMPONENT_ZERO,
    QualityReason.PRODUCT_MASK,
)
CAUTION_REASONS = (QualityReason.MODERATE_COHERENCE, QualityReason.SMALL_COMPONENT)

REASON_TEXT: dict[QualityReason, str] = {
    QualityReason.PHASE_MISSING: "no unwrapped phase value in the product",
    QualityReason.COHERENCE_MISSING: "no coherence value in the product",
    QualityReason.LOW_COHERENCE: "coherence below the exclusion threshold",
    QualityReason.UNWRAP_COMPONENT_ZERO: "not assigned to a reliable unwrapped region (connected component 0)",
    QualityReason.PRODUCT_MASK: "flagged by the product's own mask layer",
    QualityReason.MODERATE_COHERENCE: "coherence between the exclusion and caution thresholds",
    QualityReason.SMALL_COMPONENT: "belongs to a small isolated unwrapped region",
}


@dataclass(frozen=True)
class QualityResult:
    state: np.ndarray  # uint8 of QualityState
    reasons: np.ndarray  # uint8 bit mask of QualityReason
    component_sizes: dict[int, int]

    def counts(self) -> dict[str, int]:
        return {s.name: int(np.count_nonzero(self.state == s)) for s in QualityState}

    def reason_counts(self) -> dict[str, int]:
        return {
            r.name or str(int(r)): int(np.count_nonzero(self.reasons & int(r)))
            for r in (*EXCLUSION_REASONS, *CAUTION_REASONS)
        }


def _is_missing(arr: np.ndarray, fill_value: float | None) -> np.ndarray:
    missing = ~np.isfinite(arr) if arr.dtype.kind == "f" else np.zeros(arr.shape, dtype=bool)
    if fill_value is not None and np.isfinite(fill_value):
        missing |= arr == fill_value
    return missing


def classify_quality(
    phase: np.ndarray,
    coherence: np.ndarray,
    cfg: QualityConfig,
    connected_components: np.ndarray | None = None,
    product_mask_invalid: np.ndarray | None = None,
    phase_fill: float | None = None,
    coherence_fill: float | None = None,
    components_fill: float | None = None,
) -> QualityResult:
    """Classify every pixel. ``product_mask_invalid`` is a boolean array (True = flagged)."""
    if phase.shape != coherence.shape:
        raise ValueError("phase and coherence must have the same shape")
    reasons = np.zeros(phase.shape, dtype=np.uint8)

    reasons[_is_missing(phase, phase_fill)] |= int(QualityReason.PHASE_MISSING)
    coh_missing = _is_missing(coherence, coherence_fill)
    reasons[coh_missing] |= int(QualityReason.COHERENCE_MISSING)
    with np.errstate(invalid="ignore"):
        low = ~coh_missing & (coherence < cfg.coherence_exclude_below)
        moderate = ~coh_missing & ~low & (coherence < cfg.coherence_caution_below)
    reasons[low] |= int(QualityReason.LOW_COHERENCE)
    reasons[moderate] |= int(QualityReason.MODERATE_COHERENCE)

    component_sizes: dict[int, int] = {}
    if connected_components is not None:
        if connected_components.shape != phase.shape:
            raise ValueError("connected_components must match the phase shape")
        cc = connected_components
        cc_missing = _is_missing(cc, components_fill)
        unreliable = cc_missing.copy()
        if cfg.exclude_unwrap_component_zero:
            unreliable |= cc == 0
        reasons[unreliable] |= int(QualityReason.UNWRAP_COMPONENT_ZERO)
        ids, counts = np.unique(cc[~unreliable], return_counts=True)
        component_sizes = {int(i): int(c) for i, c in zip(ids, counts, strict=True)}
        small_ids = [i for i, c in component_sizes.items() if c < cfg.small_component_pixels]
        if small_ids:
            reasons[np.isin(cc, small_ids) & ~unreliable] |= int(QualityReason.SMALL_COMPONENT)

    if product_mask_invalid is not None and cfg.use_product_mask:
        if product_mask_invalid.shape != phase.shape:
            raise ValueError("product mask must match the phase shape")
        reasons[product_mask_invalid.astype(bool)] |= int(QualityReason.PRODUCT_MASK)

    exclusion_bits = sum(int(r) for r in EXCLUSION_REASONS)
    caution_bits = sum(int(r) for r in CAUTION_REASONS)
    state = np.full(phase.shape, int(QualityState.VALID), dtype=np.uint8)
    state[(reasons & caution_bits) != 0] = int(QualityState.CAUTION)
    state[(reasons & exclusion_bits) != 0] = int(QualityState.EXCLUDED)
    return QualityResult(state=state, reasons=reasons, component_sizes=component_sizes)


def unmasked_quality(phase: np.ndarray, phase_fill: float | None = None) -> QualityResult:
    """Ablation helper: treat every pixel that has a phase value as VALID."""
    missing = _is_missing(phase, phase_fill)
    reasons = np.where(missing, int(QualityReason.PHASE_MISSING), 0).astype(np.uint8)
    state = np.where(missing, int(QualityState.EXCLUDED), int(QualityState.VALID)).astype(np.uint8)
    return QualityResult(state=state, reasons=reasons, component_sizes={})

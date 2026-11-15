"""Deterministic, hand-auditable inspection-priority score and weight-sensitivity analysis.

score = 100 * sum_i( weight_i * component_i ),  component_i in [0, 1]

The score ranks the strength of *satellite evidence that the ground moved at a
road*. It is not a probability of damage.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import COMPONENT_NAMES, InfrastructureConfig, PrioritisationConfig, SensitivityConfig
from ..infrastructure.intersection import RoadCandidate

COMPONENT_LABELS = {
    "displacement_magnitude": "Observed LOS motion at the road",
    "overlap_extent": "Length of road inside the zone",
    "valid_fraction": "Share of valid radar pixels",
    "coherence": "Median coherence",
    "proximity": "Closeness to the deformation zone",
    "road_class": "Road class (OSM highway tag)",
}


@dataclass(frozen=True)
class Component:
    name: str
    value: float  # 0..1
    raw_value: float | None
    raw_unit: str
    basis: str


@dataclass(frozen=True)
class SensitivityResult:
    runs: int
    perturbation_fraction: float
    top1_changed_fraction: float | None
    unstable: bool | None
    spearman_min: float | None
    spearman_median: float | None
    rank_min: tuple[int, ...]
    rank_max: tuple[int, ...]


def compute_components(
    candidates: list[RoadCandidate],
    prio: PrioritisationConfig,
    infra: InfrastructureConfig,
    quantity: str = "relative LOS range change",
) -> list[dict[str, Component]]:
    """Turn raw evidence into six [0, 1] components per candidate."""
    mags = [c.evidence.p90_abs_los_m for c in candidates]
    max_mag = max((m for m in mags if m is not None), default=0.0)
    max_overlap = max((c.overlap_length_m for c in candidates), default=0.0)
    out: list[dict[str, Component]] = []
    for cand, mag in zip(candidates, mags, strict=True):
        ev = cand.evidence
        coh = None if ev.coherence_summary is None else ev.coherence_summary["median"]
        proximity = 1.0 if cand.overlap_length_m > 0 else max(0.0, 1.0 - cand.distance_m / infra.proximity_limit_m)
        comps = {
            "displacement_magnitude": Component(
                "displacement_magnitude",
                0.0 if (mag is None or max_mag <= 0) else min(1.0, mag / max_mag),
                mag,
                "m",
                f"90th percentile of |{quantity}| in the road corridor, divided by the largest "
                f"such value among all candidates in this event ({max_mag:.3f} m)",
            ),
            "overlap_extent": Component(
                "overlap_extent",
                0.0 if max_overlap <= 0 else min(1.0, cand.overlap_length_m / max_overlap),
                cand.overlap_length_m,
                "m",
                f"road length inside the zone, divided by the longest such overlap in this event ({max_overlap:.0f} m)",
            ),
            "valid_fraction": Component(
                "valid_fraction",
                0.0 if ev.valid_fraction is None else ev.valid_fraction,
                ev.valid_fraction,
                "fraction",
                "share of corridor pixels classified VALID",
            ),
            "coherence": Component(
                "coherence",
                0.0 if coh is None else float(min(1.0, max(0.0, coh))),
                coh,
                "coherence",
                "median interferometric coherence of corridor pixels",
            ),
            "proximity": Component(
                "proximity",
                proximity,
                cand.distance_m,
                "m",
                f"1 when the road crosses the zone, otherwise 1 - distance / {infra.proximity_limit_m:.0f} m",
            ),
            "road_class": Component(
                "road_class",
                float(prio.road_class_values.get(cand.highway_class, 0.0)),
                None,
                cand.highway_class,
                "configured value for the OSM highway class (network role, not criticality)",
            ),
        }
        out.append(comps)
    return out


def component_matrix(components: list[dict[str, Component]]) -> np.ndarray:
    return np.array([[c[name].value for name in COMPONENT_NAMES] for c in components], dtype=np.float64).reshape(
        len(components), len(COMPONENT_NAMES)
    )


def scores(matrix: np.ndarray, weights: dict[str, float]) -> np.ndarray:
    w = np.array([weights[name] for name in COMPONENT_NAMES], dtype=np.float64)
    w = w / w.sum()
    return 100.0 * matrix @ w


def ranking(score_values: np.ndarray) -> np.ndarray:
    """Indices ordered best-first. Ties are broken by original (deterministic) order."""
    return np.lexsort((np.arange(score_values.size), -np.round(score_values, 9)))


def ranks_from_order(order: np.ndarray) -> np.ndarray:
    ranks = np.empty(order.size, dtype=np.int64)
    ranks[order] = np.arange(1, order.size + 1)
    return ranks


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if a.size < 2:
        return None
    da, db = a - a.mean(), b - b.mean()
    den = float(np.sqrt((da**2).sum() * (db**2).sum()))
    return None if den == 0 else float((da * db).sum() / den)


def perturbed_weight_sets(weights: dict[str, float], cfg: SensitivityConfig) -> list[dict[str, float]]:
    """One-at-a-time +/- perturbations plus seeded random draws. Deterministic."""
    base = np.array([weights[n] for n in COMPONENT_NAMES], dtype=np.float64)
    sets: list[np.ndarray] = []
    if cfg.perturbation_fraction > 0:
        for i in range(base.size):
            for sign in (-1.0, 1.0):
                w = base.copy()
                w[i] *= 1.0 + sign * cfg.perturbation_fraction
                sets.append(w)
        rng = np.random.default_rng(cfg.seed)
        for _ in range(cfg.random_draws):
            sets.append(base * rng.uniform(1 - cfg.perturbation_fraction, 1 + cfg.perturbation_fraction, base.size))
    return [dict(zip(COMPONENT_NAMES, (w / w.sum()).tolist(), strict=True)) for w in sets if w.sum() > 0]


def sensitivity_analysis(matrix: np.ndarray, weights: dict[str, float], cfg: SensitivityConfig) -> SensitivityResult:
    n = matrix.shape[0]
    base_ranks = ranks_from_order(ranking(scores(matrix, weights))) if n else np.array([], dtype=np.int64)
    weight_sets = perturbed_weight_sets(weights, cfg)
    if n == 0 or not weight_sets:
        return SensitivityResult(0, cfg.perturbation_fraction, None, None, None, None, tuple(base_ranks), tuple(base_ranks))
    rank_min, rank_max = base_ranks.copy(), base_ranks.copy()
    top1_changes = 0
    rhos: list[float] = []
    base_top = int(np.argmin(base_ranks))
    for w in weight_sets:
        ranks = ranks_from_order(ranking(scores(matrix, w)))
        rank_min = np.minimum(rank_min, ranks)
        rank_max = np.maximum(rank_max, ranks)
        if int(np.argmin(ranks)) != base_top:
            top1_changes += 1
        rho = _spearman(base_ranks.astype(float), ranks.astype(float))
        if rho is not None:
            rhos.append(rho)
    frac = top1_changes / len(weight_sets)
    return SensitivityResult(
        runs=len(weight_sets),
        perturbation_fraction=cfg.perturbation_fraction,
        top1_changed_fraction=frac,
        unstable=frac > cfg.unstable_top1_change_fraction,
        spearman_min=min(rhos) if rhos else None,
        spearman_median=float(np.median(rhos)) if rhos else None,
        rank_min=tuple(int(r) for r in rank_min),
        rank_max=tuple(int(r) for r in rank_max),
    )

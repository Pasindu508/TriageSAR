"""Static, hand-written methodology text served to the UI. Numbers come from the live configuration."""

from __future__ import annotations

from typing import Any

from triagesar.config import COMPONENT_NAMES, AnalysisConfig
from triagesar.prioritisation.model import COMPONENT_LABELS
from triagesar.processing.displacement import EQUATION_TEXT, SIGN_CONVENTION_TEXT

SIGN_BASIS = (
    "The NISAR GUNW product specification does not state the sign convention in words. TriageSAR derives it "
    "from the ISCE3 processing software, which forms the interferogram as reference x conj(secondary) with the "
    "reference being the earlier acquisition. The inspection ranking uses only the magnitude of the motion, so "
    "it does not depend on the sign. The NASA/JPL displacement maps for this event use the opposite convention "
    "(positive = towards the satellite)."
)
NOT_CLAIMED = [
    "TriageSAR does not detect structural damage.",
    "TriageSAR does not predict casualties or losses.",
    "NISAR observations are not treated as ground truth.",
    "The inspection priority score is not a probability, an accuracy or a statistical confidence.",
]
LIMITATIONS = [
    "One interferogram gives motion along one viewing direction only; horizontal motion parallel to the "
    "satellite track is almost invisible.",
    "Values are relative, never absolute. Zones measure motion that differs from the surrounding 4 km, so motion "
    "that is smooth over many kilometres (such as most of an earthquake's broad deformation field) is deliberately "
    "not reported as a zone, even when it is large.",
    "No atmospheric (ionosphere, troposphere) or solid-Earth-tide correction is applied, so long-wavelength "
    "atmospheric signal can be mistaken for motion.",
    "Phase-unwrapping errors can create or hide jumps of half a wavelength; isolated small unwrapped regions "
    "are flagged CAUTION for this reason.",
    "Vegetated, steep, water-covered or rapidly changing terrain loses coherence and is excluded: it is "
    "unobserved, not safe.",
    "Road geometry and names come from OpenStreetMap and may be incomplete or out of date.",
    "The NISAR product used is a PROVISIONAL (partially validated) release.",
    "All thresholds and weights are screening values chosen for a prototype; they have not been calibrated "
    "against field inspections.",
]


def build_methodology(config: AnalysisConfig) -> dict[str, Any]:
    q, h, infra = config.quality, config.hotspot, config.infrastructure
    weights = config.prioritisation.normalised_weights()
    return {
        "pipeline": [
            {"step": "1. Read", "detail": "Unwrapped phase, coherence, connected components and mask are read from the NISAR GUNW fixture exactly as distributed."},
            {"step": "2. Convert", "detail": "Phase is converted to line-of-sight range change using the wavelength derived from the product's own centre-frequency metadata."},
            {"step": "3. Quality gate", "detail": "Every pixel is classed VALID, CAUTION or EXCLUDED by transparent rules. Excluded pixels are never interpolated."},
            {"step": "4. Reference", "detail": "Unwrapped phase is relative. For zones and ranking, each pixel is compared with a plane fitted to its surroundings in the same unwrapped region, so motion shared by the whole area does not count as a local anomaly. The map's surface-motion layer stays relative to the scene median."},
            {"step": "5. Zones", "detail": "Contiguous groups of quality-approved pixels above a screening threshold become deformation zones; tiny groups are rejected."},
            {"step": "6. Intersect", "detail": "Zones are intersected with OpenStreetMap roads; radar evidence is summarised along each road corridor."},
            {"step": "7. Rank", "detail": "A weighted sum of six visible factors gives the inspection priority score. Weights are perturbed to test ranking stability."},
        ],
        "equation": EQUATION_TEXT,
        "sign_convention": SIGN_CONVENTION_TEXT,
        "sign_convention_basis": SIGN_BASIS,
        "quality_states": [
            {"state": "VALID", "meaning": "Passes every rule. Used in analysis.", "encoding": "no overlay"},
            {"state": "CAUTION", "meaning": "Usable but weaker evidence. Used in analysis and flagged.", "encoding": "yellow dots"},
            {"state": "EXCLUDED", "meaning": "Not used. Unobserved, not unmoved.", "encoding": "grey diagonal hatching"},
        ],
        "quality_rules": [
            {"rule": f"coherence < {q.coherence_exclude_below:g}", "result": "EXCLUDED", "rationale": "Low coherence means the radar signal decorrelated between the two dates; the phase is noise. Screening value."},
            {"rule": f"{q.coherence_exclude_below:g} <= coherence < {q.coherence_caution_below:g}", "result": "CAUTION", "rationale": "Moderate coherence: phase is usable but noisier. Screening value."},
            {"rule": "connected component = 0, or fill value", "result": "EXCLUDED", "rationale": "The product marks these pixels as not reliably unwrapped (NISAR ATBD)."},
            {"rule": f"connected component smaller than {q.small_component_pixels} pixels", "result": "CAUTION", "rationale": "The phase offset of a small isolated region relative to its neighbours is ambiguous. Screening value."},
            {"rule": "product mask: fill, water, or invalid sub-swath", "result": "EXCLUDED", "rationale": "Flags shipped with the product itself (NISAR GUNW specification)."},
            {"rule": "no phase or coherence value", "result": "EXCLUDED", "rationale": "Nothing was observed."},
        ],
        "threshold_rule": (
            f"Each pixel is first compared with a plane fitted to the usable pixels of the same unwrapped region within a "
            f"{config.reference.window_m / 1000:g} km window around it. A pixel is a zone candidate when the absolute "
            f"difference is at least max({h.threshold_floor_m * 100:g} cm, {h.robust_sigma_multiplier:g} x 1.4826 x MAD "
            f"of all such differences). Zones smaller than {h.min_area_km2:g} km2 are rejected. The floor, the multiplier "
            f"and the minimum area were fixed before any real data were inspected; the local reference replaced a "
            f"scene-median reference after the first real run found that the earthquake's broad motion swamped it."
        ),
        "score_formula": "Inspection priority score = 100 x sum(weight x factor), each factor between 0 and 1",
        "score_components": [
            {"name": name, "label": COMPONENT_LABELS[name], "weight": round(weights[name], 4)} for name in COMPONENT_NAMES
        ],
        "sensitivity": (
            f"Every weight is perturbed by up to ±{config.sensitivity.perturbation_fraction * 100:.0f}% "
            f"(12 one-at-a-time runs and {config.sensitivity.random_draws} seeded random draws). If the top item "
            f"changes in more than {config.sensitivity.unstable_top1_change_fraction * 100:.0f}% of runs the ranking is labelled UNSTABLE."
        ),
        "corrections": (
            "The GUNW product ships ionosphere, troposphere and solid-Earth-tide layers but does not remove them "
            "from the unwrapped phase, and neither does TriageSAR. Road corridors are "
            f"{infra.corridor_buffer_m:g} m either side of the road; roads within {infra.proximity_limit_m:g} m of a zone are listed."
        ),
        "limitations": LIMITATIONS,
        "not_claimed": NOT_CLAIMED,
        "config": config.model_dump(mode="json"),
    }

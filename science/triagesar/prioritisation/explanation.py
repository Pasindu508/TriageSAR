"""Deterministic plain-English explanations built from measured fields only (no LLM)."""

from __future__ import annotations

from ..config import COMPONENT_NAMES
from ..infrastructure.intersection import RoadCandidate
from .model import COMPONENT_LABELS, Component

NOT_COMPUTED = "not computed"
DISCLAIMER = (
    "This is not a damage assessment. Satellite-observed ground motion does not show whether a road, "
    "bridge or structure is damaged; the location is prioritised for human field inspection only."
)


def fmt_cm(value_m: float | None) -> str:
    return NOT_COMPUTED if value_m is None else f"{value_m * 100:.1f} cm"


def fmt_pct(fraction: float | None) -> str:
    return NOT_COMPUTED if fraction is None else f"{fraction * 100:.0f}%"


def fmt_length(value_m: float) -> str:
    return f"{value_m / 1000:.1f} km" if value_m >= 1000 else f"{value_m:.0f} m"


def evidence_quality(valid_fraction: float | None, usable_fraction: float | None, valid_min: float, usable_min: float) -> str:
    """Card-level label derived from corridor pixel states by two configured cut-offs."""
    if valid_fraction is None or usable_fraction is None:
        return "INSUFFICIENT"
    if valid_fraction >= valid_min:
        return "VALID"
    if usable_fraction >= usable_min:
        return "CAUTION"
    return "INSUFFICIENT"


def short_reason(cand: RoadCandidate, motion: str = "relative LOS motion") -> str:
    ev = cand.evidence
    where = (
        f"{fmt_length(cand.overlap_length_m)} of road inside deformation zone {cand.zone_id}"
        if cand.relation == "overlaps"
        else f"{fmt_length(cand.distance_m)} from deformation zone {cand.zone_id}"
    )
    return f"{where}; up to {fmt_cm(ev.p90_abs_los_m)} {motion} (90th percentile) along the corridor."


def why_ranked(rank: int, score: float, components: dict[str, Component], weights: dict[str, float]) -> list[str]:
    lines = [
        f"Inspection priority score {score:.1f} / 100 puts this road at rank {rank}. "
        "The score is the weighted sum of six visible factors:"
    ]
    for name in COMPONENT_NAMES:
        comp = components[name]
        lines.append(
            f"{COMPONENT_LABELS[name]}: value {comp.value:.2f} x weight {weights[name]:.2f} "
            f"= {100 * comp.value * weights[name]:.1f} points ({comp.basis})."
        )
    return lines


def plain_summary(cand: RoadCandidate, quality_label: str) -> str:
    ev = cand.evidence
    if cand.relation == "overlaps":
        first = (
            f"Radar-observed surface motion forms a contiguous zone that crosses {fmt_length(cand.overlap_length_m)} "
            f"of this road."
        )
    else:
        first = f"A contiguous zone of radar-observed surface motion lies {fmt_length(cand.distance_m)} from this road."
    if ev.valid_fraction is None:
        second = "No radar pixels were available along the road corridor, so the motion at the road is not computed."
    else:
        second = (
            f"Radar quality is VALID over {fmt_pct(ev.valid_fraction)} of the {ev.buffer_m:.0f} m corridor "
            f"({fmt_pct(1 - (ev.usable_fraction or 0))} excluded); evidence quality: {quality_label}."
        )
    return f"{first} {second} {DISCLAIMER}"


def caveats(cand: RoadCandidate, quality_label: str, multi_component: bool, reference_note: str) -> list[str]:
    notes = [f"Values are line-of-sight range change, a 1-D projection of the true 3-D motion. {reference_note}"]
    if quality_label != "VALID":
        notes.append("Radar quality along this corridor is limited; treat the measured motion with caution.")
    if cand.evidence.excluded_pixels > 0:
        notes.append(
            f"{cand.evidence.excluded_pixels} of {cand.evidence.pixel_count} corridor pixels are excluded; "
            "absence of observed motion there does not mean absence of motion."
        )
    if multi_component:
        notes.append("The zone spans more than one unwrapped region; phase offsets between regions are ambiguous.")
    if cand.bridge_tagged_length_m > 0:
        notes.append(
            f"{fmt_length(cand.bridge_tagged_length_m)} of the overlapping road is tagged as a bridge in OpenStreetMap. "
            "Radar returns from structures can differ from the surrounding ground."
        )
    if cand.name_source == "unnamed":
        notes.append("This road has no name or reference tag in OpenStreetMap.")
    return notes

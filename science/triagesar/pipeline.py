"""End-to-end analysis: fixture + roads + config -> evidence-ranked inspection queue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from shapely.geometry import mapping

from . import __version__
from .config import COMPONENT_NAMES, AnalysisConfig
from .fixture import Fixture
from .infrastructure.intersection import find_road_candidates, nearest_roads, road_observation_coverage
from .infrastructure.osm import Road
from .prioritisation import explanation as ex
from .prioritisation import model as pm
from .processing.clustering import (
    ReferenceInfo,
    extract_hotspots,
    reference_to_component_median,
    reference_to_local_plane,
    screening_threshold,
)
from .processing.displacement import EQUATION_TEXT, SIGN_CONVENTION_TEXT, metres_per_fringe, phase_to_los_range_change
from .processing.georeference import WGS84, GridGeometry, reproject_geometry
from .processing.product_mask import decode_product_mask
from .processing.quality import REASON_TEXT, QualityReason, QualityState, classify_quality, unmasked_quality
from .results import (
    AnalysisResult,
    CorridorSummary,
    Explanation,
    FiveNumber,
    GridSummary,
    InspectionItem,
    QualitySummary,
    RadarSummary,
    RankStability,
    ReferenceSummary,
    RoadCoverage,
    ScoreComponent,
    SensitivitySummary,
    ThresholdSummary,
    Zone,
)

GENERAL_CAVEATS = [
    "Line-of-sight (LOS) range change is a one-dimensional projection of ground motion onto the radar viewing "
    "direction. Full 3-D motion is not recovered from a single interferogram.",
    "All values are relative, never absolute displacements, and they are not ground truth. The map colours "
    "show motion relative to the median of each unwrapped region in the study area; zones and ranking use "
    "the reference described under Methodology.",
    "No ionospheric, tropospheric or solid-Earth-tide correction has been applied by TriageSAR.",
    "Excluded pixels are unobserved, not unmoved. Vegetation, steep terrain, water and rapid surface change "
    "reduce radar coherence.",
    "Ground motion is not infrastructure damage. The queue prioritises human field inspection; it is not a "
    "substitute for engineering assessment.",
]


SCENE_DESCRIPTION = (
    "The motion layer on the map shows LOS range change relative to the median of the same unwrapped "
    "region over the whole study area."
)


@dataclass(frozen=True)
class AnalysisArtifacts:
    result: AnalysisResult
    grid: GridGeometry
    #: scene-relative field (each unwrapped region minus its study-area median); shown on the map
    relative_m: np.ndarray
    #: field used for zones and ranking (equal to ``relative_m`` for the component_median method)
    analysis_m: np.ndarray
    quality_state: np.ndarray
    zone_labels: np.ndarray
    #: the product's unwrapped-region labels (None when the fixture has no such layer)
    connected_components: np.ndarray | None = None


@dataclass(frozen=True)
class Referenced:
    """A LOS field after referencing, with the words used to describe it."""

    field: np.ndarray
    info: ReferenceInfo
    window_m: float | None
    quantity: str
    motion: str
    text: str


def referenced_field(
    range_change_m: np.ndarray,
    usable: np.ndarray,
    components: np.ndarray | None,
    grid: GridGeometry,
    config: AnalysisConfig,
    scene: tuple[np.ndarray, ReferenceInfo] | None = None,
) -> Referenced:
    """Apply the configured reference (local plane, or component median) to a LOS field."""
    if config.reference.method == "local_plane":
        pixel_m = float(np.sqrt(grid.pixel_area_m2()))
        window_px = max(3, int(round(config.reference.window_m / pixel_m)) | 1)  # odd number of pixels
        field, info = reference_to_local_plane(
            range_change_m, usable, components, window_px, config.reference.min_window_fraction
        )
        window = window_px * pixel_m
        text = (
            f"For zones and ranking, each pixel is compared with a plane fitted to the usable pixels of the same "
            f"unwrapped region within a {window / 1000:.1f} km window around it, so the values measure motion "
            f"that differs from the surroundings, not motion shared by the whole area."
        )
        return Referenced(field, info, window, "local LOS range change", "local LOS motion", text)
    field, info = scene if scene is not None else reference_to_component_median(range_change_m, usable, components)
    text = "Each unwrapped connected component is referenced to the median of its non-excluded pixels inside the study area."
    return Referenced(field, info, None, "scene-relative LOS range change", "scene-relative LOS motion", text)


def _median_or_none(values: np.ndarray) -> float | None:
    finite = values[np.isfinite(values)]
    return float(np.median(finite)) if finite.size else None


def _five(summary: dict[str, float] | None) -> FiveNumber | None:
    return None if summary is None else FiveNumber(**summary)


def _round_geom(geom: Any, ndigits: int = 6) -> dict[str, Any]:
    def rnd(obj: Any) -> Any:
        if isinstance(obj, (list, tuple)):
            return [rnd(o) for o in obj]
        return round(float(obj), ndigits)

    gj = mapping(geom)
    return {"type": gj["type"], "coordinates": rnd(gj["coordinates"])}


def _grid_summary(grid: GridGeometry) -> GridSummary:
    projected = grid.crs.is_projected
    return GridSummary(
        crs_name=grid.crs.name,
        epsg=grid.crs.to_epsg(),
        width=grid.width,
        height=grid.height,
        pixel_size_x_m=abs(grid.transform.a) if projected else None,
        pixel_size_y_m=abs(grid.transform.e) if projected else None,
        pixel_area_m2=grid.pixel_area_m2(),
        bounds_wgs84=tuple(round(v, 6) for v in grid.bounds_wgs84()),  # type: ignore[arg-type]
    )


def run_analysis(
    fixture: Fixture,
    roads: list[Road],
    config: AnalysisConfig,
    apply_quality_mask: bool = True,
) -> AnalysisArtifacts:
    """Run the full, deterministic analysis. ``apply_quality_mask=False`` is the ablation run."""
    manifest = fixture.manifest
    grid = fixture.grid
    layers = manifest.layers
    phase = fixture.arrays["unwrapped_phase"]
    coherence = fixture.arrays["coherence"].astype(np.float64)
    components = fixture.layer("connected_components")
    mask = fixture.layer("mask")

    mask_note = "the fixture has no product mask layer"
    mask_invalid = None
    if mask is not None:
        mask_invalid, mask_note = decode_product_mask(mask, layers["mask"].fill_value)
    comp_fill = layers["connected_components"].fill_value if components is not None else None

    if apply_quality_mask:
        quality = classify_quality(
            phase,
            coherence,
            config.quality,
            connected_components=components,
            product_mask_invalid=mask_invalid,
            phase_fill=layers["unwrapped_phase"].fill_value,
            coherence_fill=layers["coherence"].fill_value,
            components_fill=comp_fill,
        )
    else:
        quality = unmasked_quality(phase, layers["unwrapped_phase"].fill_value)
    state = quality.state
    usable = state != int(QualityState.EXCLUDED)

    range_change = phase_to_los_range_change(phase, manifest.radar.wavelength_m)
    relative, scene_info = reference_to_component_median(range_change, usable, components)
    ref = referenced_field(range_change, usable, components, grid, config, scene=(relative, scene_info))
    analysis, ref_info, window_m = ref.field, ref.info, ref.window_m
    quantity, motion, reference_text = ref.quantity, ref.motion, ref.text
    threshold = screening_threshold(analysis[np.isfinite(analysis)], config.hotspot, quantity)
    zones, zone_labels = extract_hotspots(
        analysis, state, coherence, grid, config.hotspot, threshold, connected_components=components
    )

    wanted = tuple(config.infrastructure.highway_classes)
    roads_used = [r for r in roads if r.base_class in wanted]
    candidates = find_road_candidates(
        zones, roads_used, grid, analysis, state, coherence, config.infrastructure, scene_m=relative
    )
    weights = config.prioritisation.normalised_weights()
    comp_sets = pm.compute_components(candidates, config.prioritisation, config.infrastructure, quantity)
    matrix = pm.component_matrix(comp_sets)
    score_values = pm.scores(matrix, weights) if candidates else np.array([])
    order = pm.ranking(score_values) if candidates else np.array([], dtype=np.int64)
    sens = pm.sensitivity_analysis(matrix, weights, config.sensitivity)
    multi_component = {z.zone_id: len(z.component_ids) > 1 for z in zones}

    event_id = manifest.event.id
    queue: list[InspectionItem] = []
    per_zone_counts: dict[str, int] = {}
    for rank, idx in enumerate(order.tolist(), start=1):
        cand, comps, ev = candidates[idx], comp_sets[idx], candidates[idx].evidence
        per_zone_counts[cand.zone_id] = per_zone_counts.get(cand.zone_id, 0) + 1
        label = ex.evidence_quality(
            ev.valid_fraction,
            ev.usable_fraction,
            config.quality.summary_valid_fraction,
            config.quality.summary_usable_fraction,
        )
        point = cand.geometry_wgs84.representative_point()
        stability = None
        if sens.runs:
            lo, hi = sens.rank_min[idx], sens.rank_max[idx]
            stability = RankStability(min_rank=lo, max_rank=hi, stable=(hi - lo) <= 1)
        queue.append(
            InspectionItem(
                id=f"{event_id}--{cand.zone_id.lower()}-r{per_zone_counts[cand.zone_id]:03d}",
                event_id=event_id,
                rank=rank,
                zone_id=cand.zone_id,
                asset_type=cand.asset_type.value,
                asset_name=cand.asset_name,
                name_source=cand.name_source,
                highway_class=cand.highway_class,
                osm_way_ids=list(cand.osm_way_ids),
                relation=cand.relation,  # type: ignore[arg-type]
                overlap_length_m=round(cand.overlap_length_m, 1),
                distance_m=round(cand.distance_m, 1),
                bridge_tagged_length_m=round(cand.bridge_tagged_length_m, 1),
                evidence_quality=label,  # type: ignore[arg-type]
                score=round(float(score_values[idx]), 2),
                components=[
                    ScoreComponent(
                        name=name,
                        label=pm.COMPONENT_LABELS[name],
                        value=round(comps[name].value, 4),
                        weight=round(weights[name], 4),
                        points=round(100 * comps[name].value * weights[name], 2),
                        raw_value=comps[name].raw_value,
                        raw_unit=comps[name].raw_unit,
                        basis=comps[name].basis,
                    )
                    for name in COMPONENT_NAMES
                ],
                corridor=CorridorSummary(
                    buffer_m=ev.buffer_m,
                    pixel_count=ev.pixel_count,
                    valid_pixels=ev.valid_pixels,
                    caution_pixels=ev.caution_pixels,
                    excluded_pixels=ev.excluded_pixels,
                    valid_fraction=ev.valid_fraction,
                    usable_fraction=ev.usable_fraction,
                    median_los_m=ev.median_los_m,
                    p90_abs_los_m=ev.p90_abs_los_m,
                    max_abs_los_m=ev.max_abs_los_m,
                    iqr_los_m=ev.iqr_los_m,
                    scene_median_los_m=ev.scene_median_los_m,
                    coherence_summary=_five(ev.coherence_summary),
                ),
                stability=stability,
                explanation=Explanation(
                    short_reason=ex.short_reason(cand, motion),
                    summary=ex.plain_summary(cand, label),
                    why_ranked=ex.why_ranked(rank, float(score_values[idx]), comps, weights),
                    caveats=ex.caveats(cand, label, multi_component.get(cand.zone_id, False), reference_text),
                    disclaimer=ex.DISCLAIMER,
                ),
                marker_lonlat=(round(point.x, 6), round(point.y, 6)),
                geometry=_round_geom(cand.geometry_wgs84),
            )
        )

    nearest = nearest_roads(zones, roads_used, grid)
    zone_models: list[Zone] = []
    for z in zones:
        poly_wgs = reproject_geometry(z.polygon, grid.crs, WGS84)
        centroid = poly_wgs.representative_point()
        zone_models.append(
            Zone(
                zone_id=z.zone_id,
                area_km2=round(z.area_km2, 3),
                pixel_count=z.pixel_count,
                median_los_m=z.median_los_m,
                max_abs_los_m=z.max_abs_los_m,
                p90_abs_los_m=z.p90_abs_los_m,
                iqr_los_m=z.iqr_los_m,
                scene_median_los_m=_median_or_none(relative[zone_labels == z.label]),
                valid_fraction=z.valid_fraction,
                caution_fraction=z.caution_fraction,
                excluded_fraction=z.excluded_fraction,
                median_coherence=z.median_coherence,
                coherence_summary=_five(z.coherence_summary),
                unwrapped_region_ids=list(z.component_ids),
                centroid_lonlat=(round(centroid.x, 6), round(centroid.y, 6)),
                bbox_wgs84=tuple(round(v, 6) for v in poly_wgs.bounds),  # type: ignore[arg-type]
                geometry=_round_geom(poly_wgs),
                road_candidate_count=per_zone_counts.get(z.zone_id, 0),
                nearest_road_name=nearest[z.zone_id][0] if z.zone_id in nearest else None,
                nearest_road_class=nearest[z.zone_id][1] if z.zone_id in nearest else None,
                nearest_road_distance_m=round(nearest[z.zone_id][2], 1) if z.zone_id in nearest else None,
            )
        )

    counts = quality.counts()
    total = int(state.size)
    coverage = road_observation_coverage(roads_used, grid, state)
    result = AnalysisResult(
        app_version=__version__,
        event_id=event_id,
        data_kind=manifest.data_kind,
        masking_applied=apply_quality_mask,
        grid=_grid_summary(grid),
        radar=RadarSummary(
            wavelength_m=manifest.radar.wavelength_m,
            center_frequency_hz=manifest.radar.center_frequency_hz,
            derivation=manifest.radar.derivation,
            source_hdf5_path=manifest.radar.source_hdf5_path,
            frequency=manifest.radar.frequency,
            polarisation=manifest.radar.polarisation,
            metres_per_fringe=metres_per_fringe(manifest.radar.wavelength_m),
            equation=EQUATION_TEXT,
            sign_convention=SIGN_CONVENTION_TEXT,
        ),
        reference=ReferenceSummary(
            method=ref_info.method,
            quantity=quantity,
            description=reference_text,
            window_m=window_m,
            unreferenced_pixels=ref_info.unreferenced_pixels,
            scene_description=SCENE_DESCRIPTION,
            component_reference_m={str(k): v for k, v in sorted(scene_info.component_reference_m.items())},
        ),
        threshold=ThresholdSummary(
            threshold_m=threshold.threshold_m,
            floor_m=threshold.floor_m,
            robust_sigma_m=threshold.robust_sigma_m,
            mad_m=threshold.mad_m,
            multiplier=threshold.multiplier,
            rule=threshold.rule,
            binding=threshold.binding,
            note=(
                "Screening rule, not a physical truth. The floor and the multiplier were fixed before any real "
                "data were inspected; the local reference was adopted after the first real run (see "
                "docs/UNCERTAINTY.md)."
            ),
        ),
        quality=QualitySummary(
            total_pixels=total,
            counts=counts,
            fractions={k: (v / total if total else 0.0) for k, v in counts.items()},
            reason_counts=quality.reason_counts(),
            reason_text={r.name or "": REASON_TEXT[r] for r in REASON_TEXT if isinstance(r, QualityReason)},
            unwrapped_region_count=len(quality.component_sizes),
            largest_region_pixels=max(quality.component_sizes.values(), default=None),
            masking_applied=apply_quality_mask,
            product_mask_used=bool(mask is not None and config.quality.use_product_mask and apply_quality_mask),
            product_mask_note=mask_note,
        ),
        zones=zone_models,
        queue=queue,
        weights={k: round(v, 4) for k, v in weights.items()},
        sensitivity=SensitivitySummary(
            runs=sens.runs,
            perturbation_fraction=sens.perturbation_fraction,
            top1_changed_fraction=sens.top1_changed_fraction,
            unstable=sens.unstable,
            spearman_min=sens.spearman_min,
            spearman_median=sens.spearman_median,
            unstable_threshold=config.sensitivity.unstable_top1_change_fraction,
            description=(
                f"Each weight was perturbed by up to ±{sens.perturbation_fraction * 100:.0f}% (one at a time and in "
                f"{config.sensitivity.random_draws} seeded random draws), renormalised, and the queue re-ranked."
            ),
        ),
        road_coverage=RoadCoverage(
            road_count=len(roads_used),
            road_pixels=coverage["road_pixels"],
            valid_pixels=coverage["VALID"],
            caution_pixels=coverage["CAUTION"],
            excluded_pixels=coverage["EXCLUDED"],
            excluded_fraction=(coverage["EXCLUDED"] / coverage["road_pixels"]) if coverage["road_pixels"] else None,
            note="Share of road-crossed pixels with no usable radar observation. These roads are unobserved, not cleared.",
        ),
        corrections=manifest.corrections.model_dump(),
        caveats=GENERAL_CAVEATS,
        config=config.model_dump(mode="json"),
    )
    return AnalysisArtifacts(result, grid, relative, analysis, state, zone_labels, components)


def ablation_summary(masked: AnalysisResult, unmasked: AnalysisResult, top_n: int = 10) -> dict[str, Any]:
    """Quantify what quality masking changes. Only computed values; nothing is implied about truth."""

    def key(item: InspectionItem) -> tuple[str, ...]:
        return tuple(str(i) for i in item.osm_way_ids)

    top_masked = [key(i) for i in masked.queue[:top_n]]
    top_unmasked = [key(i) for i in unmasked.queue[:top_n]]
    shared = len(set(top_masked) & set(top_unmasked))
    area_m = sum(z.area_km2 for z in masked.zones)
    area_u = sum(z.area_km2 for z in unmasked.zones)
    return {
        "description": "Same pipeline run with quality masking (baseline) and with every pixel that has a phase value treated as VALID.",
        "with_masking": {
            "zones": len(masked.zones),
            "zone_area_km2": round(area_m, 3),
            "queue_length": len(masked.queue),
            "threshold_m": masked.threshold.threshold_m,
            "usable_pixels": masked.quality.counts["VALID"] + masked.quality.counts["CAUTION"],
        },
        "without_masking": {
            "zones": len(unmasked.zones),
            "zone_area_km2": round(area_u, 3),
            "queue_length": len(unmasked.queue),
            "threshold_m": unmasked.threshold.threshold_m,
            "usable_pixels": unmasked.quality.counts["VALID"] + unmasked.quality.counts["CAUTION"],
        },
        "zone_area_change_km2": round(area_u - area_m, 3),
        "top_n": top_n,
        "top_n_shared_roads": shared,
        "top_n_compared": min(top_n, len(top_masked), len(top_unmasked)),
        "top1_same_road": bool(top_masked and top_unmasked and top_masked[0] == top_unmasked[0]),
    }

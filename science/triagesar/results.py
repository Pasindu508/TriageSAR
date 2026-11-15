"""Versioned, typed result schema shared by the science pipeline and the API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "1.0"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FiveNumber(_Model):
    min: float
    p25: float
    median: float
    p75: float
    max: float


class GridSummary(_Model):
    crs_name: str
    epsg: int | None
    width: int
    height: int
    pixel_size_x_m: float | None
    pixel_size_y_m: float | None
    pixel_area_m2: float
    bounds_wgs84: tuple[float, float, float, float]


class RadarSummary(_Model):
    wavelength_m: float
    center_frequency_hz: float | None
    derivation: str
    source_hdf5_path: str
    frequency: str | None
    polarisation: str | None
    metres_per_fringe: float
    equation: str
    sign_convention: str


class ReferenceSummary(_Model):
    method: str
    #: short name of the quantity used for zones and ranking, e.g. "local LOS range change"
    quantity: str
    description: str
    window_m: float | None
    unreferenced_pixels: int
    #: what the map's motion layer shows (always the scene-relative field)
    scene_description: str
    component_reference_m: dict[str, float]


class ThresholdSummary(_Model):
    threshold_m: float
    floor_m: float
    robust_sigma_m: float | None
    mad_m: float | None
    multiplier: float
    rule: str
    binding: str
    note: str


class QualitySummary(_Model):
    total_pixels: int
    counts: dict[str, int]
    fractions: dict[str, float]
    reason_counts: dict[str, int]
    reason_text: dict[str, str]
    unwrapped_region_count: int
    largest_region_pixels: int | None
    masking_applied: bool
    product_mask_used: bool
    product_mask_note: str


class Zone(_Model):
    zone_id: str
    area_km2: float
    pixel_count: int
    median_los_m: float
    max_abs_los_m: float
    p90_abs_los_m: float
    iqr_los_m: float
    #: median of the scene-relative field inside the zone (context only, not used for ranking)
    scene_median_los_m: float | None
    valid_fraction: float
    caution_fraction: float
    excluded_fraction: float
    median_coherence: float | None
    coherence_summary: FiveNumber | None
    unwrapped_region_ids: list[int]
    centroid_lonlat: tuple[float, float]
    bbox_wgs84: tuple[float, float, float, float]
    geometry: dict[str, Any]
    road_candidate_count: int
    #: nearest mapped road (context only, not used for ranking); None when there are no roads
    nearest_road_name: str | None
    nearest_road_class: str | None
    nearest_road_distance_m: float | None


class CorridorSummary(_Model):
    buffer_m: float
    pixel_count: int
    valid_pixels: int
    caution_pixels: int
    excluded_pixels: int
    valid_fraction: float | None
    usable_fraction: float | None
    median_los_m: float | None
    p90_abs_los_m: float | None
    max_abs_los_m: float | None
    iqr_los_m: float | None
    #: median of the scene-relative field in the corridor (context only, not used for ranking)
    scene_median_los_m: float | None
    coherence_summary: FiveNumber | None


class ScoreComponent(_Model):
    name: str
    label: str
    value: float
    weight: float
    points: float
    raw_value: float | None
    raw_unit: str
    basis: str


class RankStability(_Model):
    min_rank: int
    max_rank: int
    stable: bool


class Explanation(_Model):
    short_reason: str
    summary: str
    why_ranked: list[str]
    caveats: list[str]
    disclaimer: str


class InspectionItem(_Model):
    id: str
    event_id: str
    rank: int
    zone_id: str
    asset_type: str
    asset_name: str
    name_source: str
    highway_class: str
    osm_way_ids: list[int]
    relation: Literal["overlaps", "near"]
    overlap_length_m: float
    distance_m: float
    bridge_tagged_length_m: float
    evidence_quality: Literal["VALID", "CAUTION", "INSUFFICIENT"]
    score: float
    components: list[ScoreComponent]
    corridor: CorridorSummary
    stability: RankStability | None
    explanation: Explanation
    marker_lonlat: tuple[float, float]
    geometry: dict[str, Any]


class SensitivitySummary(_Model):
    runs: int
    perturbation_fraction: float
    top1_changed_fraction: float | None
    unstable: bool | None
    spearman_min: float | None
    spearman_median: float | None
    unstable_threshold: float
    description: str


class RoadCoverage(_Model):
    road_count: int
    road_pixels: int
    valid_pixels: int
    caution_pixels: int
    excluded_pixels: int
    excluded_fraction: float | None
    note: str


class AnalysisResult(_Model):
    schema_version: str = SCHEMA_VERSION
    app_version: str
    event_id: str
    data_kind: str
    masking_applied: bool
    grid: GridSummary
    radar: RadarSummary
    reference: ReferenceSummary
    threshold: ThresholdSummary
    quality: QualitySummary
    zones: list[Zone]
    queue: list[InspectionItem]
    weights: dict[str, float]
    sensitivity: SensitivitySummary
    road_coverage: RoadCoverage
    corrections: dict[str, Any]
    caveats: list[str]
    config: dict[str, Any]

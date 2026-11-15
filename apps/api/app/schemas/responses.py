"""Versioned response schemas. Every response carries ``schema_version`` and ``app_version``."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from triagesar import __version__
from triagesar.results import (
    SCHEMA_VERSION,
    InspectionItem,
    QualitySummary,
    RadarSummary,
    ReferenceSummary,
    RoadCoverage,
    SensitivitySummary,
    ThresholdSummary,
)

EventStatus = Literal["ready", "fixture_not_built", "roads_missing"]


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = SCHEMA_VERSION
    app_version: str = __version__


class ErrorBody(BaseModel):
    code: str
    message: str
    hint: str | None = None


class ErrorResponse(Envelope):
    error: ErrorBody


class HealthResponse(Envelope):
    status: Literal["ok"] = "ok"
    events_total: int
    events_ready: int


class Acquisition(BaseModel):
    role: Literal["reference", "secondary"]
    start_utc: str | None
    end_utc: str | None


class AcquisitionDate(BaseModel):
    date: str
    used: bool


class EventSummary(BaseModel):
    id: str
    title: str
    summary: str
    data_kind: Literal["nasa_nisar_gunw", "synthetic_test"]
    data_label: str
    status: EventStatus
    status_message: str
    build_command: str | None
    event_time_utc: str | None
    event_source_name: str | None
    event_source_url: str | None
    bbox_wgs84: tuple[float, float, float, float] | None
    granule_id: str | None
    acquisitions: list[Acquisition]
    epicentres: list[dict[str, Any]] = Field(default_factory=list)
    place: str | None = None
    magnitude: float | None = None
    acquisition_dates: list[AcquisitionDate] = Field(default_factory=list)
    acquisition_dates_source: str | None = None
    added_by: Literal["manual", "auto_ingest", "test"] = "manual"
    added_on: str | None = None


class AutoIngestStatus(BaseModel):
    enabled: bool
    last_checked_utc: str | None
    checked_until: str | None
    added_total: int
    waiting: int
    description: str


class EventsResponse(Envelope):
    events: list[EventSummary]
    auto_ingest: AutoIngestStatus


class EventDetail(Envelope):
    event: EventSummary
    notes: list[str]
    disclaimer: str
    zone_count: int
    queue_length: int
    quality: QualitySummary
    radar: RadarSummary
    reference: ReferenceSummary
    threshold: ThresholdSummary
    sensitivity: SensitivitySummary
    road_coverage: RoadCoverage
    weights: dict[str, float]
    corrections: dict[str, Any]
    caveats: list[str]
    infrastructure: dict[str, Any]
    provenance_summary: dict[str, Any]


class LegendEntry(BaseModel):
    key: str
    label: str
    description: str
    encoding: str


class RasterMetadata(Envelope):
    event_id: str
    displacement_url: str
    quality_url: str
    local_url: str | None
    local_colour_limit_m: float | None
    local_note: str | None
    coordinates: list[list[float]] = Field(description="Image corners: top-left, top-right, bottom-right, bottom-left (lon, lat)")
    width: int
    height: int
    colour_limit_m: float | None
    colour_scale: str
    display_note: str
    grid: dict[str, Any]
    legend: list[LegendEntry]


class HotspotsResponse(Envelope):
    event_id: str
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]


class QueueResponse(Envelope):
    event_id: str
    score_label: str = "Inspection priority score"
    disclaimer: str
    total: int
    offset: int
    limit: int
    weights: dict[str, float]
    sensitivity: SensitivitySummary
    items: list[InspectionItem]


class InspectionResponse(Envelope):
    item: InspectionItem
    zone: dict[str, Any] | None
    provenance_summary: dict[str, Any]
    weights: dict[str, float]


class ProfileResponse(Envelope):
    event_id: str
    target: str
    kind: Literal["road", "transect"]
    description: str
    length_km: float
    distance_km: list[float]
    local_m: list[float | None]
    scene_m: list[float | None]
    state: list[str]
    threshold_m: float


class RoadsResponse(Envelope):
    event_id: str
    attribution: str
    licence_url: str
    roads: dict[str, Any]
    places: dict[str, Any]


class AblationResponse(Envelope):
    event_id: str
    ablation: dict[str, Any]


class ProvenanceEvent(BaseModel):
    event_id: str
    status: EventStatus
    data_kind: str
    fixture_manifest: dict[str, Any] | None
    checksum_problems: list[str] | None
    infrastructure_manifest: dict[str, Any] | None
    event_definition: dict[str, Any]


class ProvenanceResponse(Envelope):
    application: dict[str, Any]
    events: list[ProvenanceEvent]


class MethodologyResponse(Envelope):
    pipeline: list[dict[str, str]]
    equation: str
    sign_convention: str
    sign_convention_basis: str
    quality_states: list[dict[str, str]]
    quality_rules: list[dict[str, str]]
    threshold_rule: str
    score_formula: str
    score_components: list[dict[str, Any]]
    sensitivity: str
    corrections: str
    limitations: list[str]
    not_claimed: list[str]
    config: dict[str, Any]

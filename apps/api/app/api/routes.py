"""HTTP routes. All endpoints are read-only."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Response

from app.models.errors import EventNotFound, InspectionNotFound
from app.repositories import events as repo
from app.schemas import responses as rs
from app.services import analysis as svc
from app.services.methodology import build_methodology
from triagesar import __version__
from triagesar.events import EVENT_ID_RE, EventEntry
from triagesar.infrastructure.osm import OSM_ATTRIBUTION, OSM_LICENCE_URL
from triagesar.prioritisation.explanation import DISCLAIMER
from triagesar.provenance.manifest import read_manifest, verify_checksums

router = APIRouter()
EventId = Annotated[str, Path(pattern=EVENT_ID_RE.pattern, max_length=64)]
DATA_LABELS = {
    "nasa_nisar_gunw": "NASA-ISRO NISAR L2 GUNW observations",
    "synthetic_test": "SYNTHETIC TEST DATA - not NASA observations",
}
ERRORS: dict[int | str, dict[str, Any]] = {404: {"model": rs.ErrorResponse}, 409: {"model": rs.ErrorResponse}}


def _summary(entry: EventEntry) -> rs.EventSummary:
    status, message = svc.status_of(entry)
    d = entry.definition
    granule_id = (d.get("granule") or {}).get("granule_id")
    acquisitions: list[rs.Acquisition] = []
    bbox = d.get("aoi_bbox_wgs84")
    if entry.fixture_ready:
        m = read_manifest(entry.nisar_dir)
        granule_id = m.source.granule_id or granule_id
        acquisitions = [
            rs.Acquisition(role="reference", start_utc=m.acquisition.reference_start_utc, end_utc=m.acquisition.reference_end_utc),
            rs.Acquisition(role="secondary", start_utc=m.acquisition.secondary_start_utc, end_utc=m.acquisition.secondary_end_utc),
        ]
        bbox = bbox or list(m.aoi.bbox_wgs84_requested)
    return rs.EventSummary(
        id=entry.id,
        title=d["title"],
        summary=d["summary"],
        data_kind=entry.data_kind,  # type: ignore[arg-type]
        data_label=DATA_LABELS[entry.data_kind],
        status=status,  # type: ignore[arg-type]
        status_message=message,
        build_command=None if status == "ready" else svc.build_command(entry),
        event_time_utc=d.get("event_time_utc"),
        event_source_name=d.get("event_source_name"),
        event_source_url=d.get("event_source_url"),
        bbox_wgs84=tuple(bbox) if bbox else None,  # type: ignore[arg-type]
        granule_id=granule_id,
        acquisitions=acquisitions,
        epicentres=list(d.get("epicentres", [])),
        place=(d.get("epicentres") or [{}])[0].get("place"),
        magnitude=(d.get("epicentres") or [{}])[0].get("magnitude"),
        acquisition_dates=[rs.AcquisitionDate(**a) for a in d.get("acquisitions", [])],
        acquisition_dates_source=d.get("acquisitions_source"),
        added_by="test" if entry.data_kind == "synthetic_test" else ("auto_ingest" if d.get("added_by") == "auto_ingest" else "manual"),
        added_on=d.get("added_on"),
    )


def _provenance_summary(a: svc.EventAnalysis) -> dict[str, Any]:
    m = a.manifest
    return {
        "event_id": m.event.id,
        "data_kind": m.data_kind,
        "granule_id": m.source.granule_id,
        "collection": m.source.collection,
        "provider": m.source.provider,
        "product_version": m.source.product_version,
        "software_version": m.source.software_version,
        "processing_datetime": m.source.processing_datetime,
        "reference_start_utc": m.acquisition.reference_start_utc,
        "secondary_start_utc": m.acquisition.secondary_start_utc,
        "orbit_pass_direction": m.source.orbit_pass_direction,
        "track_number": m.source.track_number,
        "frame_number": m.source.frame_number,
        "fixture_command": m.build.command,
        "fixture_built_at_utc": m.build.built_at_utc,
        "application_version": __version__,
    }


@router.get("/health", response_model=rs.HealthResponse, tags=["system"])
def health() -> rs.HealthResponse:
    entries = repo.all_events()
    return rs.HealthResponse(events_total=len(entries), events_ready=sum(svc.status_of(e)[0] == "ready" for e in entries))


def _auto_ingest_status() -> rs.AutoIngestStatus:
    state = repo.read_auto_ingest_state()
    processed = (state or {}).get("processed", {})
    return rs.AutoIngestStatus(
        enabled=state is not None,
        last_checked_utc=(state or {}).get("last_checked_utc"),
        checked_until=(state or {}).get("checked_until"),
        added_total=sum(1 for v in processed.values() if v.get("status") == "added"),
        waiting=sum(1 for v in processed.values() if v.get("status") in ("waiting", "retry")),
        description=(
            "scripts/auto_ingest.py checks the USGS catalogue for significant shallow earthquakes and the ASF catalogue "
            "for NISAR interferograms that bracket them, and adds each one through the same pipeline as the "
            "hand-made case studies."
        ),
    )


@router.get("/api/v1/events", response_model=rs.EventsResponse, tags=["events"])
def list_events() -> rs.EventsResponse:
    return rs.EventsResponse(events=[_summary(e) for e in repo.all_events()], auto_ingest=_auto_ingest_status())


@router.get("/api/v1/events/{event_id}", response_model=rs.EventDetail, responses=ERRORS, tags=["events"])
def get_event(event_id: EventId) -> rs.EventDetail:
    entry = repo.require_event(event_id)
    a = svc.get_analysis(entry)
    r = a.artifacts.result
    return rs.EventDetail(
        event=_summary(entry),
        notes=list(entry.definition.get("notes", [])),
        disclaimer=DISCLAIMER,
        zone_count=len(r.zones),
        queue_length=len(r.queue),
        quality=r.quality,
        radar=r.radar,
        reference=r.reference,
        threshold=r.threshold,
        sensitivity=r.sensitivity,
        road_coverage=r.road_coverage,
        weights=r.weights,
        corrections=r.corrections,
        caveats=r.caveats,
        infrastructure=a.config.infrastructure.model_dump(mode="json"),
        provenance_summary=_provenance_summary(a),
    )


@router.get("/api/v1/events/{event_id}/raster/metadata", response_model=rs.RasterMetadata, responses=ERRORS, tags=["raster"])
def raster_metadata(event_id: EventId) -> rs.RasterMetadata:
    a = svc.get_analysis(repo.require_event(event_id))
    ov = svc.get_overlays(a)
    base = f"/api/v1/events/{event_id}/raster"
    return rs.RasterMetadata(
        event_id=event_id,
        displacement_url=f"{base}/displacement.png",
        quality_url=f"{base}/quality.png",
        local_url=f"{base}/local.png" if ov.local_png is not None else None,
        local_colour_limit_m=ov.local_colour_limit_m,
        local_note=a.artifacts.result.reference.description if ov.local_png is not None else None,
        coordinates=ov.coordinates,
        width=ov.width,
        height=ov.height,
        colour_limit_m=ov.colour_limit_m,
        colour_scale="Symmetric about zero; limit = 98th percentile of the absolute value over usable pixels, per layer.",
        display_note="Display images are resampled (nearest neighbour) to Web Mercator. Analysis uses the native grid only.",
        grid=a.artifacts.result.grid.model_dump(),
        legend=[
            rs.LegendEntry(key="away", label="Range increase", description="Ground moved away from the satellite (relative).", encoding="orange, opacity grows with magnitude"),
            rs.LegendEntry(key="towards", label="Range decrease", description="Ground moved towards the satellite (relative).", encoding="blue, opacity grows with magnitude"),
            rs.LegendEntry(key="caution", label="CAUTION", description="Usable but weaker radar evidence.", encoding="yellow dots"),
            rs.LegendEntry(key="excluded", label="EXCLUDED", description="No usable observation. Unobserved, not unmoved.", encoding="grey diagonal hatching"),
            rs.LegendEntry(key="zone", label="Deformation zone", description="Contiguous quality-approved pixels above the screening threshold.", encoding="white outline with zone number"),
        ],
    )


@router.get("/api/v1/events/{event_id}/raster/{layer}.png", responses={200: {"content": {"image/png": {}}}, **ERRORS}, tags=["raster"])
def raster_png(event_id: EventId, layer: Annotated[str, Path(pattern="^(displacement|quality|local)$")]) -> Response:
    ov = svc.get_overlays(svc.get_analysis(repo.require_event(event_id)))
    data = {"displacement": ov.displacement_png, "quality": ov.quality_png, "local": ov.local_png}[layer]
    if data is None:
        raise EventNotFound("This event has no separate local-motion layer.")
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/api/v1/events/{event_id}/hotspots", response_model=rs.HotspotsResponse, responses=ERRORS, tags=["analysis"])
def hotspots(event_id: EventId) -> rs.HotspotsResponse:
    r = svc.get_analysis(repo.require_event(event_id)).artifacts.result
    features = [
        {"type": "Feature", "id": z.zone_id, "geometry": z.geometry, "properties": z.model_dump(exclude={"geometry"})}
        for z in r.zones
    ]
    return rs.HotspotsResponse(event_id=event_id, features=features)


@router.get("/api/v1/events/{event_id}/inspection-queue", response_model=rs.QueueResponse, responses=ERRORS, tags=["analysis"])
def inspection_queue(
    event_id: EventId,
    limit: Annotated[int, Query(ge=1, le=200)] = 25,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> rs.QueueResponse:
    r = svc.get_analysis(repo.require_event(event_id)).artifacts.result
    return rs.QueueResponse(
        event_id=event_id,
        disclaimer=DISCLAIMER,
        total=len(r.queue),
        offset=offset,
        limit=limit,
        weights=r.weights,
        sensitivity=r.sensitivity,
        items=r.queue[offset : offset + limit],
    )


TargetId = Annotated[str, Path(pattern=r"^(Z\d{2,4}|[a-z0-9][a-z0-9-]{1,62}--z\d{2,4}-r\d{3,5})$", max_length=96)]


def _target_geometry(a: svc.EventAnalysis, target: str) -> tuple[str, Any]:
    """('road', road geometry) for an inspection item id, or ('zone', zone geometry) for a zone id."""
    from shapely.geometry import shape

    r = a.artifacts.result
    if target.startswith("Z"):
        zone = next((z for z in r.zones if z.zone_id == target), None)
        if zone is None:
            raise InspectionNotFound(f"No zone {target!r} in this event.")
        return "zone", shape(zone.geometry)
    item = next((q for q in r.queue if q.id == target), None)
    if item is None:
        raise InspectionNotFound(f"No inspection item with id {target!r}.")
    return "road", shape(item.geometry)


@router.get("/api/v1/events/{event_id}/profile/{target}", response_model=rs.ProfileResponse, responses=ERRORS, tags=["analysis"])
def profile(event_id: EventId, target: TargetId) -> rs.ProfileResponse:
    from triagesar.profile import sample_profile, zone_transect

    a = svc.get_analysis(repo.require_event(event_id))
    kind, geom = _target_geometry(a, target)
    art = a.artifacts
    line = geom if kind == "road" else zone_transect(geom, art.grid)
    prof = sample_profile(line, art.grid, art.analysis_m, art.relative_m, art.quality_state, "road" if kind == "road" else "transect")
    if prof is None:
        raise InspectionNotFound("No profile can be drawn for this target.")
    description = (
        "Values sampled at about one-pixel spacing along the longest continuous stretch of the road inside the corridor."
        if kind == "road"
        else "Values sampled along a straight line through the zone, along its longer axis, extended 2 km beyond it."
    )
    return rs.ProfileResponse(
        event_id=event_id,
        target=target,
        kind=prof.kind,  # type: ignore[arg-type]
        description=description + " Gaps are excluded pixels: unobserved, not zero.",
        length_km=prof.length_km,
        distance_km=prof.distance_km,
        local_m=prof.local_m,
        scene_m=prof.scene_m,
        state=prof.state,
        threshold_m=art.result.threshold.threshold_m,
    )


@router.get("/api/v1/events/{event_id}/thumbnail/{target}.png", responses={200: {"content": {"image/png": {}}}, **ERRORS}, tags=["raster"])
def thumbnail(event_id: EventId, target: TargetId) -> Response:
    from triagesar.profile import thumbnail_png

    a = svc.get_analysis(repo.require_event(event_id))
    cached = a.thumbnails.get(target)
    if cached is None:
        _, geom = _target_geometry(a, target)
        art = a.artifacts
        cached = thumbnail_png(geom, art.grid, art.analysis_m, art.quality_state, art.result.threshold.threshold_m)
        if cached is None:
            raise InspectionNotFound("The target lies outside the analysis grid.")
        a.thumbnails[target] = cached
    return Response(content=cached, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/api/v1/events/{event_id}/roads", response_model=rs.RoadsResponse, responses=ERRORS, tags=["infrastructure"])
def roads(event_id: EventId) -> rs.RoadsResponse:
    entry = repo.require_event(event_id)
    return rs.RoadsResponse(
        event_id=event_id,
        attribution=OSM_ATTRIBUTION if entry.data_kind != "synthetic_test" else "TEST ONLY synthetic roads (not OpenStreetMap data)",
        licence_url=OSM_LICENCE_URL,
        roads=repo.read_geojson(entry, "roads"),
        places=repo.read_geojson(entry, "places"),
    )


@router.get("/api/v1/events/{event_id}/ablation", response_model=rs.AblationResponse, responses=ERRORS, tags=["analysis"])
def ablation(event_id: EventId) -> rs.AblationResponse:
    return rs.AblationResponse(event_id=event_id, ablation=svc.get_ablation(svc.get_analysis(repo.require_event(event_id))))


@router.get("/api/v1/inspection/{inspection_id}", response_model=rs.InspectionResponse, responses=ERRORS, tags=["analysis"])
def inspection(inspection_id: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{1,62}--z\d{2,4}-r\d{3,5}$", max_length=96)]) -> rs.InspectionResponse:
    event_id = inspection_id.split("--", 1)[0]
    try:
        entry = repo.require_event(event_id)
    except EventNotFound:
        raise InspectionNotFound(f"No inspection item with id {inspection_id!r}.") from None
    a = svc.get_analysis(entry)
    r = a.artifacts.result
    item = next((q for q in r.queue if q.id == inspection_id), None)
    if item is None:
        raise InspectionNotFound(f"No inspection item with id {inspection_id!r}.")
    zone = next((z for z in r.zones if z.zone_id == item.zone_id), None)
    return rs.InspectionResponse(
        item=item,
        zone=None if zone is None else zone.model_dump(exclude={"geometry"}),
        provenance_summary=_provenance_summary(a),
        weights=r.weights,
    )


@router.get("/api/v1/provenance", response_model=rs.ProvenanceResponse, tags=["provenance"])
def provenance() -> rs.ProvenanceResponse:
    events: list[rs.ProvenanceEvent] = []
    for entry in repo.all_events():
        status, _ = svc.status_of(entry)
        manifest = read_manifest(entry.nisar_dir).model_dump(mode="json") if entry.fixture_ready else None
        events.append(
            rs.ProvenanceEvent(
                event_id=entry.id,
                status=status,  # type: ignore[arg-type]
                data_kind=entry.data_kind,
                fixture_manifest=manifest,
                checksum_problems=verify_checksums(entry.nisar_dir) if entry.fixture_ready else None,
                infrastructure_manifest=repo.read_osm_manifest(entry),
                event_definition=entry.definition,
            )
        )
    return rs.ProvenanceResponse(
        application={
            "name": "TriageSAR",
            "version": __version__,
            "licence": "Apache-2.0",
            "statement": "Every number shown is computed from the fixture described here. Values that could not be computed are shown as 'not computed'.",
        },
        events=events,
    )


@router.get("/api/v1/methodology", response_model=rs.MethodologyResponse, tags=["provenance"])
def methodology() -> rs.MethodologyResponse:
    return rs.MethodologyResponse(**build_methodology(svc.load_app_config()))

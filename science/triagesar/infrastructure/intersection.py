"""Intersect deformation zones with roads and summarise radar evidence along each road corridor."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from affine import Affine
from rasterio import features
from shapely import STRtree, shortest_line
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from ..config import InfrastructureConfig
from ..processing import statistics as st
from ..processing.clustering import Hotspot
from ..processing.georeference import WGS84, GridGeometry, reproject_geometry
from ..processing.quality import QualityState
from .osm import InfrastructureType, Road

CLASS_ORDER = ("motorway", "trunk", "primary", "secondary", "tertiary")


@dataclass(frozen=True)
class CorridorEvidence:
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
    coherence_summary: dict[str, float] | None
    scene_median_los_m: float | None = None


@dataclass(frozen=True)
class RoadCandidate:
    zone_id: str
    asset_type: InfrastructureType
    asset_name: str
    name_source: str  # "osm:name", "osm:ref" or "unnamed"
    highway_class: str
    osm_way_ids: tuple[int, ...]
    overlap_length_m: float
    distance_m: float
    relation: str  # "overlaps" or "near"
    bridge_tagged_length_m: float
    evidence: CorridorEvidence
    geometry_wgs84: BaseGeometry
    sort_key: tuple[str, str] = field(default=("", ""))


def geometry_pixel_window(geom_grid: BaseGeometry, grid: GridGeometry, all_touched: bool = True) -> tuple[slice, slice, np.ndarray] | None:
    """Rasterise a geometry (grid CRS) and return (rows, cols, boolean mask) or None if outside."""
    if geom_grid.is_empty:
        return None
    minx, miny, maxx, maxy = geom_grid.bounds
    inv = ~grid.transform
    c0, r0 = inv @ (minx, maxy)
    c1, r1 = inv @ (maxx, miny)
    col0 = max(0, int(math.floor(min(c0, c1))))
    col1 = min(grid.width, int(math.ceil(max(c0, c1))))
    row0 = max(0, int(math.floor(min(r0, r1))))
    row1 = min(grid.height, int(math.ceil(max(r0, r1))))
    if col1 <= col0 or row1 <= row0:
        return None
    sub_transform = grid.transform @ Affine.translation(col0, row0)
    mask = features.geometry_mask(
        [geom_grid], out_shape=(row1 - row0, col1 - col0), transform=sub_transform, invert=True, all_touched=all_touched
    )
    return slice(row0, row1), slice(col0, col1), mask


def corridor_evidence(
    corridor_grid: BaseGeometry,
    grid: GridGeometry,
    relative_m: np.ndarray,
    quality_state: np.ndarray,
    coherence: np.ndarray,
    buffer_m: float,
    scene_m: np.ndarray | None = None,
) -> CorridorEvidence:
    """Summarise ``relative_m`` (the field used for ranking) and quality inside a road corridor.

    ``scene_m`` is the scene-relative field; only its median is kept, as context.
    """
    window = geometry_pixel_window(corridor_grid, grid)
    if window is None or not window[2].any():
        return CorridorEvidence(buffer_m, 0, 0, 0, 0, None, None, None, None, None, None, None)
    rows, cols, mask = window
    q = quality_state[rows, cols][mask]
    n = int(q.size)
    valid = int(np.count_nonzero(q == int(QualityState.VALID)))
    caution = int(np.count_nonzero(q == int(QualityState.CAUTION)))
    excluded = n - valid - caution
    vals = relative_m[rows, cols][mask][q != int(QualityState.EXCLUDED)]
    coh = coherence[rows, cols][mask]
    return CorridorEvidence(
        buffer_m=buffer_m,
        pixel_count=n,
        valid_pixels=valid,
        caution_pixels=caution,
        excluded_pixels=excluded,
        valid_fraction=valid / n,
        usable_fraction=(valid + caution) / n,
        median_los_m=st.median(vals),
        p90_abs_los_m=st.percentile(np.abs(vals), 90),
        max_abs_los_m=st.max_abs(vals),
        iqr_los_m=st.iqr(vals),
        coherence_summary=st.five_number_summary(coh),
        scene_median_los_m=None if scene_m is None else st.median(scene_m[rows, cols][mask]),
    )


def _road_identity(road: Road) -> tuple[str, str, str]:
    """(group key, display name, name source). Never invents a name."""
    if road.name:
        label = f"{road.name} ({road.ref})" if road.ref else road.name
        return (f"name:{road.name}", label, "osm:name")
    if road.ref:
        return (f"ref:{road.ref}", road.ref, "osm:ref")
    return (f"way:{road.osm_id}", f"Unnamed {road.base_class} road (OSM way {road.osm_id})", "unnamed")


def _best_class(classes: list[str]) -> str:
    known = [c for c in classes if c in CLASS_ORDER]
    return min(known, key=CLASS_ORDER.index) if known else sorted(classes)[0]


def find_road_candidates(
    zones: list[Hotspot],
    roads: list[Road],
    grid: GridGeometry,
    relative_m: np.ndarray,
    quality_state: np.ndarray,
    coherence: np.ndarray,
    cfg: InfrastructureConfig,
    scene_m: np.ndarray | None = None,
) -> list[RoadCandidate]:
    """One candidate per (deformation zone, road) pair within the proximity limit."""
    if not zones or not roads:
        return []
    metric = grid.metric_crs()
    road_geoms_m = [reproject_geometry(r.geometry, WGS84, metric) for r in roads]
    tree = STRtree(road_geoms_m)
    limit = cfg.proximity_limit_m
    candidates: list[RoadCandidate] = []
    for zone in zones:
        zone_m = reproject_geometry(zone.polygon, grid.crs, metric)
        # A zone outline follows pixel edges and may consist of thousands of pieces. Its pieces are
        # indexed so that distances and overlaps are exact without ever buffering the outline.
        parts = list(zone_m.geoms) if hasattr(zone_m, "geoms") else [zone_m]
        part_tree = STRtree(parts)
        minx, miny, maxx, maxy = zone_m.bounds
        envelope = box(minx - limit, miny - limit, maxx + limit, maxy + limit)
        groups: dict[str, list[tuple[int, float, int]]] = {}
        for idx in sorted(int(i) for i in tree.query(envelope, predicate="intersects")):
            nearest_part, dist = part_tree.query_nearest(
                road_geoms_m[idx], max_distance=limit, return_distance=True, all_matches=False
            )
            if len(nearest_part) == 0:
                continue  # farther than the proximity limit from every piece of the zone
            groups.setdefault(_road_identity(roads[idx])[0], []).append((idx, float(dist[0]), int(nearest_part[0])))
        for key in sorted(groups):
            members = groups[key]
            inside_parts, near_parts, bridge_len = [], [], 0.0
            dist = min(d for _, d, _ in members)
            for idx, _, part_idx in members:
                geom = road_geoms_m[idx]
                hits = part_tree.query(geom, predicate="intersects")
                inside = unary_union([geom.intersection(parts[int(i)]) for i in hits]) if len(hits) else None
                if inside is not None and not inside.is_empty and inside.length > 0:
                    inside_parts.append(inside)
                    if roads[idx].bridge:
                        bridge_len += float(inside.length)
                # The stretch of this road closest to the zone, up to the proximity limit either side.
                closest = Point(shortest_line(geom, parts[part_idx]).coords[0])
                near = geom.intersection(closest.buffer(limit, quad_segs=8))
                if not near.is_empty and near.length > 0:
                    near_parts.append(near)
            overlap = float(sum(p.length for p in inside_parts))
            segment_m = unary_union(inside_parts) if inside_parts else unary_union(near_parts)
            if segment_m.is_empty:
                continue
            corridor_grid = reproject_geometry(segment_m.buffer(cfg.corridor_buffer_m, quad_segs=4), metric, grid.crs)
            evidence = corridor_evidence(
                corridor_grid, grid, relative_m, quality_state, coherence, cfg.corridor_buffer_m, scene_m
            )
            first = members[0][0]
            _, label, source = _road_identity(roads[first])
            candidates.append(
                RoadCandidate(
                    zone_id=zone.zone_id,
                    asset_type=InfrastructureType.ROAD,
                    asset_name=label,
                    name_source=source,
                    highway_class=_best_class([roads[i].base_class for i, _, _ in members]),
                    osm_way_ids=tuple(sorted(roads[i].osm_id for i, _, _ in members)),
                    overlap_length_m=overlap,
                    distance_m=0.0 if overlap > 0 else dist,
                    relation="overlaps" if overlap > 0 else "near",
                    bridge_tagged_length_m=bridge_len,
                    evidence=evidence,
                    geometry_wgs84=reproject_geometry(segment_m, metric, WGS84),
                    sort_key=(zone.zone_id, key),
                )
            )
    candidates.sort(key=lambda c: c.sort_key)
    return candidates


def road_observation_coverage(roads: list[Road], grid: GridGeometry, quality_state: np.ndarray) -> dict[str, int]:
    """Count road-crossed pixels by quality state, so unobserved roads are visible, not hidden."""
    if not roads:
        return {"road_pixels": 0, "VALID": 0, "CAUTION": 0, "EXCLUDED": 0}
    geoms = [reproject_geometry(r.geometry, WGS84, grid.crs) for r in roads]
    mask = features.rasterize(
        ((g, 1) for g in geoms if not g.is_empty), out_shape=grid.shape, transform=grid.transform, fill=0, dtype="uint8"
    ).astype(bool)
    q = quality_state[mask]
    return {
        "road_pixels": int(q.size),
        "VALID": int(np.count_nonzero(q == int(QualityState.VALID))),
        "CAUTION": int(np.count_nonzero(q == int(QualityState.CAUTION))),
        "EXCLUDED": int(np.count_nonzero(q == int(QualityState.EXCLUDED))),
    }


def nearest_roads(zones: list[Hotspot], roads: list[Road], grid: GridGeometry) -> dict[str, tuple[str, str, float]]:
    """For each zone: (road label, highway class, distance in metres) of the nearest road.

    Context only: it tells a planner how far the closest mapped road is. It is not used for ranking.
    """
    if not zones or not roads:
        return {}
    metric = grid.metric_crs()
    road_geoms_m = [reproject_geometry(r.geometry, WGS84, metric) for r in roads]
    tree = STRtree(road_geoms_m)
    out: dict[str, tuple[str, str, float]] = {}
    for zone in zones:
        zone_m = reproject_geometry(zone.polygon, grid.crs, metric)
        idx = int(tree.nearest(zone_m))
        _, label, _ = _road_identity(roads[idx])
        out[zone.zone_id] = (label, roads[idx].base_class, float(road_geoms_m[idx].distance(zone_m)))
    return out

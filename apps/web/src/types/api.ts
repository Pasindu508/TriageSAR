// Types mirroring the versioned API schema (see packages/shared/openapi.json).

export type EventStatus = 'ready' | 'fixture_not_built' | 'roads_missing';
export type DataKind = 'nasa_nisar_gunw' | 'synthetic_test';
export type EvidenceQuality = 'VALID' | 'CAUTION' | 'INSUFFICIENT';
export type LonLat = [number, number];
export type BBox = [number, number, number, number];

export interface Envelope {
  schema_version: string;
  app_version: string;
}

export interface Acquisition {
  role: 'reference' | 'secondary';
  start_utc: string | null;
  end_utc: string | null;
}

export interface EventSummary {
  id: string;
  title: string;
  summary: string;
  data_kind: DataKind;
  data_label: string;
  status: EventStatus;
  status_message: string;
  build_command: string | null;
  event_time_utc: string | null;
  event_source_name: string | null;
  event_source_url: string | null;
  bbox_wgs84: BBox | null;
  granule_id: string | null;
  acquisitions: Acquisition[];
  epicentres: Epicentre[];
  place: string | null;
  magnitude: number | null;
  acquisition_dates: Array<{ date: string; used: boolean }>;
  acquisition_dates_source: string | null;
  added_by: 'manual' | 'auto_ingest' | 'test';
  added_on: string | null;
}

export interface AutoIngestStatus {
  enabled: boolean;
  last_checked_utc: string | null;
  checked_until: string | null;
  added_total: number;
  waiting: number;
  description: string;
}

export interface EventsResponse extends Envelope {
  events: EventSummary[];
  auto_ingest: AutoIngestStatus;
  /** Present only on a static snapshot: when it was exported, and from which commit. */
  snapshot?: { generated_utc: string; commit: string | null };
}

export interface FiveNumber {
  min: number;
  p25: number;
  median: number;
  p75: number;
  max: number;
}

export interface QualitySummary {
  total_pixels: number;
  counts: Record<string, number>;
  fractions: Record<string, number>;
  reason_counts: Record<string, number>;
  reason_text: Record<string, string>;
  unwrapped_region_count: number;
  largest_region_pixels: number | null;
  masking_applied: boolean;
  product_mask_used: boolean;
  product_mask_note: string;
}

export interface RadarSummary {
  wavelength_m: number;
  center_frequency_hz: number | null;
  derivation: string;
  source_hdf5_path: string;
  frequency: string | null;
  polarisation: string | null;
  metres_per_fringe: number;
  equation: string;
  sign_convention: string;
}

export interface ThresholdSummary {
  threshold_m: number;
  floor_m: number;
  robust_sigma_m: number | null;
  mad_m: number | null;
  multiplier: number;
  rule: string;
  binding: string;
  note: string;
}

export interface SensitivitySummary {
  runs: number;
  perturbation_fraction: number;
  top1_changed_fraction: number | null;
  unstable: boolean | null;
  spearman_min: number | null;
  spearman_median: number | null;
  unstable_threshold: number;
  description: string;
}

export interface RoadCoverage {
  road_count: number;
  road_pixels: number;
  valid_pixels: number;
  caution_pixels: number;
  excluded_pixels: number;
  excluded_fraction: number | null;
  note: string;
}

export interface ProvenanceSummary {
  event_id: string;
  data_kind: DataKind;
  granule_id: string | null;
  collection: string | null;
  provider: string | null;
  product_version: string | null;
  software_version: string | null;
  processing_datetime: string | null;
  reference_start_utc: string | null;
  secondary_start_utc: string | null;
  orbit_pass_direction: string | null;
  track_number: number | string | null;
  frame_number: number | string | null;
  fixture_command: string;
  fixture_built_at_utc: string;
  application_version: string;
}

export interface Epicentre {
  usgs_id: string;
  magnitude: number;
  magnitude_type: string;
  lon: number;
  lat: number;
  time_utc: string;
  place: string;
}

export interface EventDetail extends Envelope {
  event: EventSummary;
  notes: string[];
  disclaimer: string;
  zone_count: number;
  queue_length: number;
  quality: QualitySummary;
  radar: RadarSummary;
  reference: {
    method: string;
    quantity: string;
    description: string;
    window_m: number | null;
    unreferenced_pixels: number;
    scene_description: string;
    component_reference_m: Record<string, number>;
  };
  threshold: ThresholdSummary;
  sensitivity: SensitivitySummary;
  road_coverage: RoadCoverage;
  weights: Record<string, number>;
  corrections: { available_layers: string[]; applied: string[]; statement: string };
  caveats: string[];
  infrastructure: { highway_classes: string[]; corridor_buffer_m: number; proximity_limit_m: number };
  provenance_summary: ProvenanceSummary;
}

export interface LegendEntry {
  key: string;
  label: string;
  description: string;
  encoding: string;
}

export interface RasterMetadata extends Envelope {
  event_id: string;
  displacement_url: string;
  quality_url: string;
  local_url: string | null;
  local_colour_limit_m: number | null;
  local_note: string | null;
  coordinates: [LonLat, LonLat, LonLat, LonLat];
  width: number;
  height: number;
  colour_limit_m: number | null;
  colour_scale: string;
  display_note: string;
  legend: LegendEntry[];
}

export interface ZoneProperties {
  zone_id: string;
  area_km2: number;
  pixel_count: number;
  median_los_m: number;
  max_abs_los_m: number;
  p90_abs_los_m: number;
  iqr_los_m: number;
  scene_median_los_m: number | null;
  valid_fraction: number;
  caution_fraction: number;
  excluded_fraction: number;
  median_coherence: number | null;
  coherence_summary: FiveNumber | null;
  unwrapped_region_ids: number[];
  centroid_lonlat: LonLat;
  bbox_wgs84: BBox;
  road_candidate_count: number;
  nearest_road_name: string | null;
  nearest_road_class: string | null;
  nearest_road_distance_m: number | null;
}

export interface GeoJsonGeometry {
  type: string;
  coordinates: unknown;
}

export interface ZoneFeature {
  type: 'Feature';
  id: string;
  geometry: GeoJsonGeometry;
  properties: ZoneProperties;
}

export interface HotspotsResponse extends Envelope {
  event_id: string;
  type: 'FeatureCollection';
  features: ZoneFeature[];
}

export interface ScoreComponent {
  name: string;
  label: string;
  value: number;
  weight: number;
  points: number;
  raw_value: number | null;
  raw_unit: string;
  basis: string;
}

export interface CorridorSummary {
  buffer_m: number;
  pixel_count: number;
  valid_pixels: number;
  caution_pixels: number;
  excluded_pixels: number;
  valid_fraction: number | null;
  usable_fraction: number | null;
  median_los_m: number | null;
  p90_abs_los_m: number | null;
  max_abs_los_m: number | null;
  iqr_los_m: number | null;
  scene_median_los_m: number | null;
  coherence_summary: FiveNumber | null;
}

export interface InspectionItem {
  id: string;
  event_id: string;
  rank: number;
  zone_id: string;
  asset_type: string;
  asset_name: string;
  name_source: string;
  highway_class: string;
  osm_way_ids: number[];
  relation: 'overlaps' | 'near';
  overlap_length_m: number;
  distance_m: number;
  bridge_tagged_length_m: number;
  evidence_quality: EvidenceQuality;
  score: number;
  components: ScoreComponent[];
  corridor: CorridorSummary;
  stability: { min_rank: number; max_rank: number; stable: boolean } | null;
  explanation: {
    short_reason: string;
    summary: string;
    why_ranked: string[];
    caveats: string[];
    disclaimer: string;
  };
  marker_lonlat: LonLat;
  geometry: GeoJsonGeometry;
}

export interface QueueResponse extends Envelope {
  event_id: string;
  score_label: string;
  disclaimer: string;
  total: number;
  offset: number;
  limit: number;
  weights: Record<string, number>;
  sensitivity: SensitivitySummary;
  items: InspectionItem[];
}

export interface FeatureCollection {
  type: 'FeatureCollection';
  features: Array<{ type: 'Feature'; properties: Record<string, unknown>; geometry: GeoJsonGeometry }>;
}

export interface ProfileResponse extends Envelope {
  event_id: string;
  target: string;
  kind: 'road' | 'transect';
  description: string;
  length_km: number;
  distance_km: number[];
  local_m: Array<number | null>;
  scene_m: Array<number | null>;
  state: string[];
  threshold_m: number;
}

export interface RoadsResponse extends Envelope {
  event_id: string;
  attribution: string;
  licence_url: string;
  roads: FeatureCollection;
  places: FeatureCollection;
}

export interface AblationSide {
  zones: number;
  zone_area_km2: number;
  queue_length: number;
  threshold_m: number;
  usable_pixels: number;
}

export interface AblationResponse extends Envelope {
  event_id: string;
  ablation: {
    description: string;
    with_masking: AblationSide;
    without_masking: AblationSide;
    zone_area_change_km2: number;
    top_n: number;
    top_n_shared_roads: number;
    top_n_compared: number;
    top1_same_road: boolean;
  };
}

export interface LayerInfo {
  file: string;
  hdf5_path: string;
  dtype: string;
  units: string | null;
  sha256: string;
  bytes: number;
}

export interface FixtureManifest {
  data_kind: DataKind;
  event: { id: string; title: string };
  source: {
    granule_id: string | null;
    file_name: string;
    collection: string | null;
    concept_id: string | null;
    provider: string | null;
    download_url: string | null;
    product_version: string | null;
    processing_datetime: string | null;
    software_version: string | null;
    track_number: number | string | null;
    frame_number: number | string | null;
    orbit_pass_direction: string | null;
    look_direction: string | null;
  };
  acquisition: { reference_start_utc: string | null; secondary_start_utc: string | null };
  radar: {
    wavelength_m: number;
    center_frequency_hz: number | null;
    derivation: string;
    source_hdf5_path: string;
    frequency: string | null;
    polarisation: string | null;
  };
  aoi: {
    bbox_wgs84_requested: BBox;
    row_start: number;
    row_stop: number;
    col_start: number;
    col_stop: number;
    source_height: number;
    source_width: number;
  };
  grid: { epsg: number | null; width: number; height: number };
  layers: Record<string, LayerInfo>;
  corrections: { available_layers: string[]; applied: string[]; statement: string };
  transformations: string[];
  build: {
    command: string;
    built_at_utc: string;
    app_version: string;
    tool_versions: Record<string, string>;
  };
}

export interface OsmManifest {
  dataset: string;
  provider: string;
  licence: string;
  licence_url: string;
  attribution: string;
  osm_base_timestamp: string | null;
  retrieved_at_utc: string;
  bbox_wgs84: number[];
  command: string;
  transformations: string[];
  files: Record<string, { sha256: string; bytes: number; features: number }>;
}

export interface ProvenanceEvent {
  event_id: string;
  status: EventStatus;
  data_kind: DataKind;
  fixture_manifest: FixtureManifest | null;
  checksum_problems: string[] | null;
  infrastructure_manifest: OsmManifest | null;
  event_definition: {
    title: string;
    event_source_name?: string;
    event_source_url?: string;
    granule?: {
      granule_id: string;
      collection: string;
      download_url: string;
      discovered_with: string;
      discovered_on: string;
    };
  };
}

export interface ProvenanceResponse extends Envelope {
  application: { name: string; version: string; licence: string; statement: string };
  events: ProvenanceEvent[];
}

export interface MethodologyResponse extends Envelope {
  pipeline: Array<{ step: string; detail: string }>;
  equation: string;
  sign_convention: string;
  sign_convention_basis: string;
  quality_states: Array<{ state: string; meaning: string; encoding: string }>;
  quality_rules: Array<{ rule: string; result: string; rationale: string }>;
  threshold_rule: string;
  score_formula: string;
  score_components: Array<{ name: string; label: string; weight: number }>;
  sensitivity: string;
  corrections: string;
  limitations: string[];
  not_claimed: string[];
}

export interface ApiErrorBody {
  error: { code: string; message: string; hint: string | null };
}

import type {
  AblationResponse,
  ApiErrorBody,
  EventDetail,
  EventsResponse,
  HotspotsResponse,
  MethodologyResponse,
  ProvenanceResponse,
  ProfileResponse,
  QueueResponse,
  RasterMetadata,
  RoadsResponse,
} from '../types/api';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly hint: string | null;

  constructor(status: number, code: string, message: string, hint: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.hint = hint;
  }
}

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { headers: { Accept: 'application/json' } });
  } catch {
    throw new ApiError(0, 'network_error', 'The TriageSAR data could not be reached. Is the server running?');
  }
  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = null;
    }
    throw new ApiError(
      response.status,
      body?.error?.code ?? 'http_error',
      body?.error?.message ?? `The server answered with HTTP ${response.status}.`,
      body?.error?.hint ?? null,
    );
  }
  return (await response.json()) as T;
}

/**
 * Static mode (VITE_STATIC_API=1): the site is a snapshot exported by scripts/export_static_site.py and every API
 * response is a pre-computed file under <base>static-api/. The numbers are identical to the live API's; only the
 * transport differs, so the site can be hosted on any static host (for example GitHub Pages).
 */
export const STATIC_API = import.meta.env.VITE_STATIC_API === '1';
const BASE = import.meta.env.BASE_URL;
const enc = encodeURIComponent;

const live = {
  events: () => '/api/v1/events',
  event: (id: string) => `/api/v1/events/${enc(id)}`,
  raster: (id: string) => `/api/v1/events/${enc(id)}/raster/metadata`,
  hotspots: (id: string) => `/api/v1/events/${enc(id)}/hotspots`,
  queue: (id: string, limit: number) => `/api/v1/events/${enc(id)}/inspection-queue?limit=${limit}`,
  roads: (id: string) => `/api/v1/events/${enc(id)}/roads`,
  profile: (id: string, target: string) => `/api/v1/events/${enc(id)}/profile/${enc(target)}`,
  thumbnail: (id: string, target: string) => `/api/v1/events/${enc(id)}/thumbnail/${enc(target)}.png`,
  ablation: (id: string) => `/api/v1/events/${enc(id)}/ablation`,
  provenance: () => '/api/v1/provenance',
  methodology: () => '/api/v1/methodology',
};

const snapshot = {
  events: () => `${BASE}static-api/events.json`,
  event: (id: string) => `${BASE}static-api/events/${enc(id)}/event.json`,
  raster: (id: string) => `${BASE}static-api/events/${enc(id)}/raster.json`,
  hotspots: (id: string) => `${BASE}static-api/events/${enc(id)}/hotspots.json`,
  queue: (id: string) => `${BASE}static-api/events/${enc(id)}/queue.json`,
  roads: (id: string) => `${BASE}static-api/events/${enc(id)}/roads.json`,
  profile: (id: string, target: string) => `${BASE}static-api/events/${enc(id)}/profile/${enc(target)}.json`,
  thumbnail: (id: string, target: string) =>
    `${BASE}static-api/events/${enc(id)}/thumbnail/${enc(target)}.png`,
  ablation: (id: string) => `${BASE}static-api/events/${enc(id)}/ablation.json`,
  provenance: () => `${BASE}static-api/provenance.json`,
  methodology: () => `${BASE}static-api/methodology.json`,
};

export const urls: typeof live = STATIC_API ? snapshot : live;

export const api = {
  events: () => getJson<EventsResponse>(urls.events()),
  event: (id: string) => getJson<EventDetail>(urls.event(id)),
  raster: (id: string) => getJson<RasterMetadata>(urls.raster(id)),
  hotspots: (id: string) => getJson<HotspotsResponse>(urls.hotspots(id)),
  queue: (id: string, limit = 200) => getJson<QueueResponse>(urls.queue(id, limit)),
  roads: (id: string) => getJson<RoadsResponse>(urls.roads(id)),
  profile: (id: string, target: string) => getJson<ProfileResponse>(urls.profile(id, target)),
  ablation: (id: string) => getJson<AblationResponse>(urls.ablation(id)),
  provenance: () => getJson<ProvenanceResponse>(urls.provenance()),
  methodology: () => getJson<MethodologyResponse>(urls.methodology()),
};

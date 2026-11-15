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
    throw new ApiError(0, 'network_error', 'The TriageSAR API could not be reached. Is the server running?');
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

const event = (id: string) => `/api/v1/events/${encodeURIComponent(id)}`;

export const api = {
  events: () => getJson<EventsResponse>('/api/v1/events'),
  event: (id: string) => getJson<EventDetail>(event(id)),
  raster: (id: string) => getJson<RasterMetadata>(`${event(id)}/raster/metadata`),
  hotspots: (id: string) => getJson<HotspotsResponse>(`${event(id)}/hotspots`),
  queue: (id: string, limit = 200) => getJson<QueueResponse>(`${event(id)}/inspection-queue?limit=${limit}`),
  roads: (id: string) => getJson<RoadsResponse>(`${event(id)}/roads`),
  profile: (id: string, target: string) =>
    getJson<ProfileResponse>(`${event(id)}/profile/${encodeURIComponent(target)}`),
  ablation: (id: string) => getJson<AblationResponse>(`${event(id)}/ablation`),
  provenance: () => getJson<ProvenanceResponse>('/api/v1/provenance'),
  methodology: () => getJson<MethodologyResponse>('/api/v1/methodology'),
};

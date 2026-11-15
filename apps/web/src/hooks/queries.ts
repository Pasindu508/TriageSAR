import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../lib/api';

const retry = (count: number, error: unknown) =>
  !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 1;

// Re-checked every 10 minutes so case studies added by the automatic ingest appear without a reload.
export const useEvents = () =>
  useQuery({ queryKey: ['events'], queryFn: api.events, retry, refetchInterval: 10 * 60 * 1000 });
export const useEvent = (id: string, enabled = true) =>
  useQuery({ queryKey: ['event', id], queryFn: () => api.event(id), retry, enabled });
export const useRaster = (id: string, enabled: boolean) =>
  useQuery({ queryKey: ['raster', id], queryFn: () => api.raster(id), retry, enabled });
export const useHotspots = (id: string, enabled: boolean) =>
  useQuery({ queryKey: ['hotspots', id], queryFn: () => api.hotspots(id), retry, enabled });
export const useQueue = (id: string, enabled: boolean) =>
  useQuery({ queryKey: ['queue', id], queryFn: () => api.queue(id), retry, enabled });
export const useRoads = (id: string) =>
  useQuery({ queryKey: ['roads', id], queryFn: () => api.roads(id), retry });
export const useProfile = (id: string, target: string | null) =>
  useQuery({
    queryKey: ['profile', id, target],
    queryFn: () => api.profile(id, target ?? ''),
    retry,
    enabled: target != null,
  });
export const useAblation = (id: string, enabled: boolean) =>
  useQuery({ queryKey: ['ablation', id], queryFn: () => api.ablation(id), retry, enabled });
export const useProvenance = (enabled: boolean) =>
  useQuery({ queryKey: ['provenance'], queryFn: api.provenance, retry, enabled });
export const useMethodology = () => useQuery({ queryKey: ['methodology'], queryFn: api.methodology, retry });

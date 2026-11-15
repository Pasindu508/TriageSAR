// Formatting helpers. A missing value is always shown as "not computed", never as zero.

export const NOT_COMPUTED = 'not computed';

export function cm(valueM: number | null | undefined, digits = 1): string {
  return valueM == null ? NOT_COMPUTED : `${(valueM * 100).toFixed(digits)} cm`;
}

export function signedCm(valueM: number | null | undefined): string {
  if (valueM == null) return NOT_COMPUTED;
  const v = valueM * 100;
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(1)} cm`;
}

export function pct(fraction: number | null | undefined, digits = 0): string {
  return fraction == null ? NOT_COMPUTED : `${(fraction * 100).toFixed(digits)}%`;
}

export function num(value: number | null | undefined, digits = 2): string {
  return value == null ? NOT_COMPUTED : value.toFixed(digits);
}

export function length(valueM: number): string {
  return valueM >= 1000 ? `${(valueM / 1000).toFixed(1)} km` : `${Math.round(valueM)} m`;
}

export function int(value: number): string {
  return value.toLocaleString('en-GB');
}

export function utcDate(iso: string | null | undefined): string {
  if (!iso) return NOT_COMPUTED;
  const d = new Date(iso.length > 23 ? `${iso.slice(0, 23)}Z` : iso.endsWith('Z') ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
}

export function utcDateTime(iso: string | null | undefined): string {
  if (!iso) return NOT_COMPUTED;
  const d = new Date(iso.length > 23 ? `${iso.slice(0, 23)}Z` : iso.endsWith('Z') ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return iso;
  const date = d.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const time = d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' });
  return `${date}, ${time} UTC`;
}

export function shortHash(sha: string): string {
  return `${sha.slice(0, 12)}…`;
}

export function thumbnailUrl(eventId: string, target: string): string {
  return `/api/v1/events/${encodeURIComponent(eventId)}/thumbnail/${encodeURIComponent(target)}.png`;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return NOT_COMPUTED;
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso.length > 23 ? `${iso.slice(0, 23)}Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

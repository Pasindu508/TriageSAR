import { useAblation } from '../hooks/queries';
import { cm, int, pct } from '../lib/format';
import type { EventDetail } from '../types/api';

/** Scene-level facts: quality gate, screening threshold, unobserved roads and the masking ablation. */
export function SceneSummary({ event }: { event: EventDetail }) {
  const ablation = useAblation(event.event.id, true);
  const q = event.quality;
  const cov = event.road_coverage;
  const a = ablation.data?.ablation;
  return (
    <details className="card card-pad why-card">
      <summary className="card-title" style={{ cursor: 'pointer' }}>
        Scene summary and quality gate
      </summary>
      <dl className="kv compact" style={{ marginTop: 12 }}>
        <dt>Radar pixels</dt>
        <dd>
          {pct(q.fractions.VALID)} VALID · {pct(q.fractions.CAUTION)} CAUTION · {pct(q.fractions.EXCLUDED)}{' '}
          EXCLUDED of {int(q.total_pixels)}
        </dd>
        <dt>Reference</dt>
        <dd>{event.reference.description}</dd>
        <dt>Local scatter</dt>
        <dd>
          robust σ {cm(event.threshold.robust_sigma_m, 2)}
          {event.reference.unreferenced_pixels > 0
            ? `; ${int(event.reference.unreferenced_pixels)} usable pixels had too few neighbours to be referenced`
            : ''}
        </dd>
        <dt>Screening threshold</dt>
        <dd>
          {cm(event.threshold.threshold_m)} of {event.reference.quantity} (
          {event.threshold.binding === 'floor' ? 'fixed floor' : 'robust 3σ rule'}), zones of at least 0.5 km²
        </dd>
        <dt>Deformation zones</dt>
        <dd>{event.zone_count}</dd>
        <dt>Unobserved roads</dt>
        <dd>
          {pct(cov.excluded_fraction)} of road-crossed pixels have no usable observation. Those roads are
          unobserved, not cleared.
        </dd>
        <dt>Wavelength</dt>
        <dd>
          {(event.radar.wavelength_m * 100).toFixed(2)} cm, from product metadata (
          <span className="mono">{event.radar.source_hdf5_path.split('/').slice(-2).join('/')}</span>)
        </dd>
        <dt>Without quality gate</dt>
        <dd>
          {a
            ? `${a.without_masking.zones} zones covering ${a.without_masking.zone_area_km2.toFixed(1)} km² instead of ${a.with_masking.zones} covering ${a.with_masking.zone_area_km2.toFixed(1)} km², and ${a.without_masking.queue_length} ranked road segments instead of ${a.with_masking.queue_length}.`
            : ablation.isError
              ? 'not computed'
              : 'computing…'}
        </dd>
      </dl>
    </details>
  );
}

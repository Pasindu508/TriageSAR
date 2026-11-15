import { useEffect, useRef } from 'react';
import { QualityChip } from '../components/QualityChip';
import { cm, length, num, pct, signedCm, utcDate } from '../lib/format';
import type { EventDetail, InspectionItem, ZoneFeature } from '../types/api';

function QualityBar({ item }: { item: InspectionItem }) {
  const c = item.corridor;
  if (c.pixel_count === 0) return <p className="note">No radar pixels fall inside this corridor.</p>;
  const share = (n: number) => `${(100 * n) / c.pixel_count}%`;
  return (
    <>
      <div
        className="qbar"
        role="img"
        aria-label={`Corridor pixels: ${c.valid_pixels} valid, ${c.caution_pixels} caution, ${c.excluded_pixels} excluded`}
      >
        <span className="v" style={{ width: share(c.valid_pixels) }} />
        <span className="c" style={{ width: share(c.caution_pixels) }} />
        <span className="x" style={{ width: share(c.excluded_pixels) }} />
      </div>
      <p className="scale-note">
        {c.valid_pixels} VALID (solid) · {c.caution_pixels} CAUTION (dots) · {c.excluded_pixels} EXCLUDED
        (hatched) of {c.pixel_count} pixels within {c.buffer_m} m of the road
      </p>
    </>
  );
}

interface Props {
  item: InspectionItem;
  zone: ZoneFeature | undefined;
  event: EventDetail;
  onBack: () => void;
  onOpenProvenance: () => void;
}

export function EvidencePanel({ item, zone, event, onBack, onOpenProvenance }: Props) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [item.id]);
  const c = item.corridor;
  const p = event.provenance_summary;
  const coh = c.coherence_summary;
  return (
    <>
      <div className="panel-head">
        <button type="button" className="btn btn-quiet" onClick={onBack}>
          ← Close evidence
        </button>
        <h2 ref={heading} tabIndex={-1} style={{ marginTop: 6 }}>
          <span className="eyebrow" style={{ display: 'block' }}>
            Rank {item.rank} · evidence
          </span>
          {item.asset_name}
        </h2>
        <div className="meta-row">
          <QualityChip quality={item.evidence_quality} />
          <span className="chip chip-info">{item.highway_class} road</span>
          <span className="score">
            {item.score.toFixed(1)} <small>/ 100 inspection priority</small>
          </span>
        </div>
      </div>
      <div className="panel-body">
        <p className="note" role="note">
          <strong>This is not a damage assessment.</strong> Satellite-observed ground motion does not show
          whether a road or structure is damaged. This location is prioritised for human field inspection
          only.
        </p>
        <p style={{ marginTop: 12 }}>
          {item.explanation.summary.replace(item.explanation.disclaimer, '').trim()}
        </p>

        <section className="section" aria-labelledby="ev-los">
          <h3 id="ev-los">Observed line-of-sight motion along the road</h3>
          <p className="scale-note" style={{ marginBottom: 8 }}>
            {event.reference.description}
          </p>
          <dl className="stat-grid">
            <div className="stat">
              <dt>90th percentile |LOS|</dt>
              <dd>
                {cm(c.p90_abs_los_m)}
                <small>used for ranking</small>
              </dd>
            </div>
            <div className="stat">
              <dt>Median LOS</dt>
              <dd>
                {signedCm(c.median_los_m)}
                <small>+ away from satellite</small>
              </dd>
            </div>
            <div className="stat">
              <dt>Largest |LOS|</dt>
              <dd>{cm(c.max_abs_los_m)}</dd>
            </div>
            <div className="stat">
              <dt>Interquartile range</dt>
              <dd>{cm(c.iqr_los_m)}</dd>
            </div>
          </dl>
          <dl className="kv">
            <dt>Scene-relative median</dt>
            <dd>{signedCm(c.scene_median_los_m)} (the map colour; context only, not used for ranking)</dd>
          </dl>
          <p className="scale-note">
            Line-of-sight range change between the two acquisitions: one viewing direction only, and always
            relative. Not vertical or horizontal displacement.
          </p>
        </section>

        <section className="section" aria-labelledby="ev-q">
          <h3 id="ev-q">Radar quality along the road</h3>
          <QualityBar item={item} />
          <dl className="kv" style={{ marginTop: 10 }}>
            <dt>Valid-pixel fraction</dt>
            <dd>{pct(c.valid_fraction)}</dd>
            <dt>Coherence</dt>
            <dd>
              {coh
                ? `median ${num(coh.median)} (quartiles ${num(coh.p25)}–${num(coh.p75)}, range ${num(coh.min)}–${num(coh.max)})`
                : 'not computed'}
            </dd>
          </dl>
        </section>

        <section className="section" aria-labelledby="ev-extent">
          <h3 id="ev-extent">Spatial extent</h3>
          <dl className="kv">
            <dt>Road and zone</dt>
            <dd>
              {item.relation === 'overlaps'
                ? `${length(item.overlap_length_m)} of road inside zone ${item.zone_id}`
                : `${length(item.distance_m)} from zone ${item.zone_id} (no overlap)`}
            </dd>
            {zone ? (
              <>
                <dt>Zone {zone.properties.zone_id}</dt>
                <dd>
                  {zone.properties.area_km2.toFixed(1)} km², median LOS{' '}
                  {signedCm(zone.properties.median_los_m)}, largest |LOS| {cm(zone.properties.max_abs_los_m)},{' '}
                  {pct(zone.properties.valid_fraction)} valid
                </dd>
              </>
            ) : null}
            {item.bridge_tagged_length_m > 0 ? (
              <>
                <dt>Bridge-tagged</dt>
                <dd>{length(item.bridge_tagged_length_m)} (OpenStreetMap tag)</dd>
              </>
            ) : null}
            <dt>OSM ways</dt>
            <dd className="mono">
              {item.osm_way_ids.slice(0, 8).join(', ')}
              {item.osm_way_ids.length > 8 ? ` … (${item.osm_way_ids.length})` : ''}
            </dd>
          </dl>
        </section>

        <section className="section" aria-labelledby="ev-why">
          <h3 id="ev-why">Inspection priority score</h3>
          <details className="why">
            <summary>Why is this ranked #{item.rank}?</summary>
            <div className="table-wrap">
              <table className="data">
                <caption className="sr-only">Score factors, their values, weights and points</caption>
                <thead>
                  <tr>
                    <th scope="col">Factor</th>
                    <th scope="col" className="num">
                      Value
                    </th>
                    <th scope="col" className="num">
                      Weight
                    </th>
                    <th scope="col" className="num">
                      Points
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {item.components.map((comp) => (
                    <tr key={comp.name}>
                      <th
                        scope="row"
                        style={{ textTransform: 'none', letterSpacing: 0, color: 'var(--text)' }}
                      >
                        {comp.label}
                        <div className="bar" aria-hidden style={{ marginTop: 4 }}>
                          <span style={{ width: `${comp.value * 100}%` }} />
                        </div>
                        <span className="scale-note" style={{ display: 'block' }}>
                          {comp.basis}
                        </span>
                      </th>
                      <td className="num">{comp.value.toFixed(2)}</td>
                      <td className="num">{comp.weight.toFixed(2)}</td>
                      <td className="num">{comp.points.toFixed(1)}</td>
                    </tr>
                  ))}
                  <tr>
                    <th scope="row" style={{ color: 'var(--text)' }}>
                      Total
                    </th>
                    <td />
                    <td />
                    <td className="num">
                      <strong>{item.score.toFixed(1)}</strong>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="scale-note">
              Score = 100 × Σ (weight × value). It ranks the strength of satellite evidence at the road. It is
              not a probability.
              {item.stability
                ? ` Under ±20% weight perturbation this item ranked between ${item.stability.min_rank} and ${item.stability.max_rank}.`
                : ''}
            </p>
          </details>
        </section>

        <section className="section" aria-labelledby="ev-src">
          <h3 id="ev-src">Source observation</h3>
          <dl className="kv">
            <dt>Granule</dt>
            <dd className="mono">{p.granule_id ?? 'not recorded'}</dd>
            <dt>Reference date</dt>
            <dd>{utcDate(p.reference_start_utc)}</dd>
            <dt>Secondary date</dt>
            <dd>{utcDate(p.secondary_start_utc)}</dd>
            <dt>Product version</dt>
            <dd>{p.product_version ?? 'not recorded'}</dd>
          </dl>
          <button
            type="button"
            className="btn btn-small"
            style={{ marginTop: 10 }}
            onClick={onOpenProvenance}
          >
            Open full provenance
          </button>
        </section>

        <section className="section" aria-labelledby="ev-notes">
          <h3 id="ev-notes">Processing notes and limitations</h3>
          <ul className="plain">
            <li>{event.corrections.statement}</li>
            {item.explanation.caveats.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}

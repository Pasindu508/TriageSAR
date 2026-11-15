import { useEffect, useRef } from 'react';
import { QualityChip, zoneQuality } from '../components/QualityChip';
import { cm, length, num, pct, signedCm } from '../lib/format';
import type { EventDetail, InspectionItem, ZoneFeature } from '../types/api';
import { EvidencePanel } from './EvidencePanel';

function ZoneDetails({
  zone,
  event,
  onOpenProvenance,
}: {
  zone: ZoneFeature;
  event: EventDetail;
  onOpenProvenance: () => void;
}) {
  const z = zone.properties;
  const share = (f: number) => `${f * 100}%`;
  return (
    <div className="panel-body">
      <p className="note" role="note">
        <strong>This is not a damage assessment.</strong> A zone marks ground that moved differently from its
        surroundings between the two acquisitions. It says nothing about the condition of structures.
      </p>
      <p style={{ marginTop: 12 }}>{event.reference.description}</p>
      <dl className="stat-grid">
        <div className="stat">
          <dt>Area</dt>
          <dd>{z.area_km2.toFixed(2)} km²</dd>
        </div>
        <div className="stat">
          <dt>Largest |local LOS|</dt>
          <dd>{cm(z.max_abs_los_m)}</dd>
        </div>
        <div className="stat">
          <dt>Median local LOS</dt>
          <dd>
            {signedCm(z.median_los_m)}
            <small>+ away from satellite</small>
          </dd>
        </div>
        <div className="stat">
          <dt>Scene-relative median</dt>
          <dd>
            {signedCm(z.scene_median_los_m)}
            <small>context only</small>
          </dd>
        </div>
      </dl>
      <section className="section" aria-labelledby="zq">
        <h3 id="zq">Radar quality inside the zone</h3>
        <div
          className="qbar"
          role="img"
          aria-label={`${pct(z.valid_fraction)} valid, ${pct(z.caution_fraction)} caution, ${pct(z.excluded_fraction)} excluded`}
        >
          <span className="v" style={{ width: share(z.valid_fraction) }} />
          <span className="c" style={{ width: share(z.caution_fraction) }} />
          <span className="x" style={{ width: share(z.excluded_fraction) }} />
        </div>
        <p className="scale-note">
          {pct(z.valid_fraction)} VALID (solid) · {pct(z.caution_fraction)} CAUTION (dots) ·{' '}
          {pct(z.excluded_fraction)} EXCLUDED (hatched) · median coherence {num(z.median_coherence)}
        </p>
        <div className="meta-row">
          <QualityChip quality={zoneQuality(z.valid_fraction, z.caution_fraction)} />
        </div>
      </section>
      <section className="section" aria-labelledby="zr">
        <h3 id="zr">Roads</h3>
        <dl className="kv">
          <dt>Nearest mapped road</dt>
          <dd>
            {z.nearest_road_name == null || z.nearest_road_distance_m == null
              ? 'not computed'
              : `${z.nearest_road_name} (${z.nearest_road_class}), ${z.nearest_road_distance_m === 0 ? 'crosses the zone' : `${length(z.nearest_road_distance_m)} away`}`}
          </dd>
          <dt>Roads ranked</dt>
          <dd>
            {z.road_candidate_count} (roads within {length(event.infrastructure.proximity_limit_m)} are
            ranked)
          </dd>
          <dt>Unwrapped regions</dt>
          <dd>{z.unwrapped_region_ids.join(', ')}</dd>
        </dl>
      </section>
      <section className="section" aria-labelledby="zl">
        <h3 id="zl">Processing notes and limitations</h3>
        <ul className="plain">
          <li>{event.corrections.statement}</li>
          {event.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
        <button type="button" className="btn btn-small" style={{ marginTop: 12 }} onClick={onOpenProvenance}>
          Open full provenance
        </button>
      </section>
    </div>
  );
}

interface Props {
  open: boolean;
  onClose: () => void;
  event: EventDetail;
  item: InspectionItem | null;
  zone: ZoneFeature | null;
  itemZone: ZoneFeature | undefined;
  onOpenProvenance: () => void;
}

export function EvidenceDrawer({ open, onClose, event, item, zone, itemZone, onOpenProvenance }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = dialog.current;
    if (!node) return;
    if (open && !node.open) {
      node.showModal();
      // Start reading at the evidence heading rather than the first button.
      node.querySelector<HTMLElement>('h2')?.focus();
    }
    if (!open && node.open) node.close();
  }, [open]);
  const title = item
    ? `Evidence: ${item.asset_name}`
    : zone
      ? `Evidence: zone ${zone.properties.zone_id}`
      : 'Evidence';
  return (
    <dialog ref={dialog} className="drawer" aria-label={title} onClose={onClose}>
      {open && item ? (
        <EvidencePanel
          item={item}
          zone={itemZone}
          event={event}
          onBack={onClose}
          onOpenProvenance={() => {
            onClose();
            onOpenProvenance();
          }}
        />
      ) : null}
      {open && !item && zone ? (
        <>
          <div className="drawer-head">
            <h2 tabIndex={-1}>Zone {zone.properties.zone_id}</h2>
            <button type="button" className="btn btn-small" onClick={onClose}>
              Close
            </button>
          </div>
          <ZoneDetails
            zone={zone}
            event={event}
            onOpenProvenance={() => {
              onClose();
              onOpenProvenance();
            }}
          />
        </>
      ) : null}
    </dialog>
  );
}

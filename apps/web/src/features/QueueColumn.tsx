import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, InfoIcon, ListIcon, PinIcon } from '../components/Icons';
import { QualityChip, zoneQuality } from '../components/QualityChip';
import { cm, length, pct, thumbnailUrl } from '../lib/format';
import type { InspectionItem, QueueResponse, ZoneFeature } from '../types/api';

export type Target = { kind: 'item'; id: string } | { kind: 'zone'; id: string };

function ItemCard({
  eventId,
  item,
  selected,
  onSelect,
}: {
  eventId: string;
  item: InspectionItem;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button type="button" className="qitem" aria-pressed={selected} onClick={onSelect}>
        <span className="thumb">
          <img src={thumbnailUrl(eventId, item.id)} alt="" loading="lazy" />
          <span className="rank-tag">#{item.rank}</span>
        </span>
        <span>
          <h3>
            <span className="sr-only">Rank {item.rank}: </span>
            {item.asset_name}
          </h3>
          <span className="where">
            <PinIcon />
            {item.highway_class} road ·{' '}
            {item.relation === 'overlaps'
              ? `${length(item.overlap_length_m)} inside ${item.zone_id}`
              : `${length(item.distance_m)} from ${item.zone_id}`}
          </span>
          <span className="chips">
            <span
              className="chip chip-priority"
              title="Inspection priority score: weighted sum of six visible factors, not a probability"
            >
              {item.score.toFixed(1)} priority
            </span>
            <QualityChip quality={item.evidence_quality} />
          </span>
        </span>
        <span className="chev">
          <ChevronRight />
        </span>
      </button>
    </li>
  );
}

function ZoneCard({
  eventId,
  zone,
  selected,
  onSelect,
}: {
  eventId: string;
  zone: ZoneFeature;
  selected: boolean;
  onSelect: () => void;
}) {
  const z = zone.properties;
  return (
    <li>
      <button type="button" className="qitem" aria-pressed={selected} onClick={onSelect}>
        <span className="thumb">
          <img src={thumbnailUrl(eventId, z.zone_id)} alt="" loading="lazy" />
          <span className="rank-tag zone">{z.zone_id}</span>
        </span>
        <span>
          <h3>
            Zone {z.zone_id} · {z.area_km2.toFixed(2)} km²
          </h3>
          <span className="where">
            <PinIcon />
            {z.nearest_road_name == null || z.nearest_road_distance_m == null
              ? 'no mapped road nearby'
              : z.nearest_road_distance_m === 0
                ? `crosses ${z.nearest_road_name}`
                : `${length(z.nearest_road_distance_m)} from ${z.nearest_road_name}`}
          </span>
          <span className="chips">
            <span className="chip chip-info">up to {cm(z.max_abs_los_m)} local</span>
            <QualityChip quality={zoneQuality(z.valid_fraction, z.caution_fraction)} />
          </span>
        </span>
        <span className="chev">
          <ChevronRight />
        </span>
      </button>
    </li>
  );
}

interface Props {
  eventId: string;
  queue: QueueResponse;
  zones: ZoneFeature[];
  target: Target | null;
  onTarget: (t: Target) => void;
  proximityLimitM: number | null;
  unobservedFraction: number | null;
}

const PAGE = 20;

export function QueueColumn({
  eventId,
  queue,
  zones,
  target,
  onTarget,
  proximityLimitM,
  unobservedFraction,
}: Props) {
  const s = queue.sensitivity;
  // Long queues (Kumamoto ranks 936 segments) are revealed a page at a time so the page stays usable on phones.
  const [shownItems, setShownItems] = useState(PAGE);
  const [shownZones, setShownZones] = useState(PAGE);
  const items = queue.items.slice(0, shownItems);
  const zoneList = zones.slice(0, shownZones);
  return (
    <section className="card queue-card" aria-labelledby="queue-h">
      <div className="queue-head">
        <h2 className="card-title" id="queue-h">
          Evidence-ranked inspection queue
          <span title="Road segments ordered by the inspection priority score. Not a probability of damage.">
            <InfoIcon />
          </span>
        </h2>
        <p className="card-sub">
          Road segments ordered by satellite evidence of ground motion and its quality.
        </p>
      </div>
      <div className="queue-body">
        {queue.total === 0 ? (
          <p className="note info">
            <strong>No road is ranked.</strong>{' '}
            {zones.length === 0
              ? 'No deformation zone was found, so there is nothing to intersect with roads.'
              : `No mapped road (motorway to tertiary) lies within ${
                  proximityLimitM == null ? 'the configured distance' : length(proximityLimitM)
                } of any of the ${zones.length} deformation zone${zones.length === 1 ? '' : 's'}.`}{' '}
            This is a result, not an error, and not a statement that roads are undamaged
            {unobservedFraction != null ? `: ${pct(unobservedFraction)} of road pixels are unobserved` : ''}.
          </p>
        ) : (
          <>
            {s.unstable != null ? (
              <p
                className={`chip chip-wrap ${s.unstable ? 'chip-warn' : 'chip-valid'}`}
                style={{ justifySelf: 'start' }}
              >
                {s.unstable ? 'RANKING UNSTABLE' : 'RANKING STABLE'}: top item changed in{' '}
                {pct(s.top1_changed_fraction)} of {s.runs} weight perturbations
              </p>
            ) : null}
            <ol className="qlist" aria-label="Inspection queue, highest priority first">
              {items.map((item) => (
                <ItemCard
                  key={item.id}
                  eventId={eventId}
                  item={item}
                  selected={target?.kind === 'item' && target.id === item.id}
                  onSelect={() => onTarget({ kind: 'item', id: item.id })}
                />
              ))}
            </ol>
            {queue.items.length > items.length ? (
              <button type="button" className="btn btn-small" onClick={() => setShownItems((n) => n + PAGE)}>
                Show {Math.min(PAGE, queue.items.length - items.length)} more ({items.length} of {queue.total}{' '}
                shown)
              </button>
            ) : queue.total > queue.items.length ? (
              <p className="scale-note">
                {queue.items.length} of {queue.total} shown here; the text table lists the rest.
              </p>
            ) : null}
          </>
        )}
        <h3 className="section-label">Deformation zones · {zones.length}</h3>
        {zones.length === 0 ? (
          <p className="note info">
            No area of quality-approved pixels exceeds the screening threshold over the minimum area.
          </p>
        ) : (
          <ol className="qlist" aria-label="Deformation zones, largest local motion first">
            {zoneList.map((zone) => (
              <ZoneCard
                key={zone.id}
                eventId={eventId}
                zone={zone}
                selected={target?.kind === 'zone' && target.id === zone.id}
                onSelect={() => onTarget({ kind: 'zone', id: zone.id })}
              />
            ))}
          </ol>
        )}
        {zones.length > zoneList.length ? (
          <button type="button" className="btn btn-small" onClick={() => setShownZones((n) => n + PAGE)}>
            Show {Math.min(PAGE, zones.length - zoneList.length)} more zones
          </button>
        ) : null}
        <Link className="btn btn-block" to={`/events/${eventId}/queue`}>
          <ListIcon />
          Full queue and zones as a text table
        </Link>
      </div>
    </section>
  );
}

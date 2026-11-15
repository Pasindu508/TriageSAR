import { AcquisitionTimeline } from '../components/AcquisitionTimeline';
import {
  AlertIcon,
  ArrowRight,
  InfoIcon,
  PinIcon,
  SatelliteIcon,
  SignalIcon,
  WaveIcon,
} from '../components/Icons';
import { ProfileChart } from '../components/ProfileChart';
import { QualityChip, zoneQuality } from '../components/QualityChip';
import { ErrorNote, Loading } from '../components/Status';
import { useProfile } from '../hooks/queries';
import { cm, length, num, pct, signedCm, thumbnailUrl } from '../lib/format';
import type { EventDetail, EventSummary, InspectionItem, ZoneFeature } from '../types/api';
import type { Target } from './QueueColumn';

function Ring({ fraction, label }: { fraction: number | null; label: string }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const f = Math.max(0, Math.min(1, fraction ?? 0));
  return (
    <svg className="ring" viewBox="0 0 64 64" role="img" aria-label={label}>
      <circle className="bg" cx="32" cy="32" r={r} fill="none" strokeWidth="7" />
      <circle
        className="fg"
        cx="32"
        cy="32"
        r={r}
        fill="none"
        strokeWidth="7"
        strokeDasharray={`${c * f} ${c}`}
        transform="rotate(-90 32 32)"
      />
    </svg>
  );
}

interface Props {
  summary: EventSummary;
  detail: EventDetail;
  target: Target | null;
  item: InspectionItem | null;
  zone: ZoneFeature | null;
  onReview: () => void;
}

export function EvidenceStrip({ summary, detail, target, item, zone, onReview }: Props) {
  const profile = useProfile(summary.id, target?.id ?? null);
  if (!target || (!item && !zone)) {
    return (
      <section className="card card-pad" aria-label="Evidence">
        <p className="note info">
          Nothing is selected because this event has neither ranked roads nor deformation zones. The scene
          figures above still apply.
        </p>
        <AcquisitionTimeline event={summary} />
      </section>
    );
  }
  const z = zone?.properties;
  const title = item ? item.asset_name : `Zone ${z!.zone_id}`;
  const tag = item ? `#${item.rank}` : z!.zone_id;
  const quality = item ? item.evidence_quality : zoneQuality(z!.valid_fraction, z!.caution_fraction);
  const validFraction = item ? item.corridor.valid_fraction : z!.valid_fraction;
  const text = item
    ? item.explanation.summary.replace(item.explanation.disclaimer, '').trim()
    : `A contiguous patch of ${z!.area_km2.toFixed(2)} km² where the ground moved up to ${cm(z!.max_abs_los_m)} differently from its surroundings (median ${signedCm(z!.median_los_m)}). ${
        z!.nearest_road_name == null || z!.nearest_road_distance_m == null
          ? 'No mapped road is nearby.'
          : z!.nearest_road_distance_m === 0
            ? `${z!.nearest_road_name} crosses it.`
            : `The nearest mapped road, ${z!.nearest_road_name}, is ${length(z!.nearest_road_distance_m)} away.`
      }`;
  const coh = item ? item.corridor.coherence_summary?.median : z!.median_coherence;
  const localValue = item ? item.corridor.p90_abs_los_m : z!.max_abs_los_m;
  const localLabel = item ? '90th percentile along the road' : 'largest in the zone';
  const scene = item ? item.corridor.scene_median_los_m : z!.scene_median_los_m;
  return (
    <section className="card evidence" aria-labelledby="ev-h">
      <section>
        <div className="ev-head">
          <img
            src={thumbnailUrl(summary.id, target.id)}
            alt={`Local motion and radar quality around ${title}`}
          />
          <div>
            <span
              className={`rank-tag ${item ? '' : 'zone'}`}
              style={{ position: 'static', display: 'inline-block' }}
            >
              {tag}
            </span>
            <h2 id="ev-h" style={{ marginTop: 6 }}>
              {title}
            </h2>
            <p className="card-sub" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <PinIcon />
              {summary.place ?? summary.title}
            </p>
          </div>
        </div>
        <p className="ev-text">{text}</p>
        <div className="chips">
          <QualityChip quality={quality} />
          <span className="chip chip-neutral">
            {item ? `${item.highway_class} road` : 'deformation zone'}
          </span>
          <span className="chip chip-info">NISAR GUNW</span>
        </div>
        <p className="scale-note">This is not a damage assessment.</p>
      </section>

      <section>
        <h3 className="ev-title">
          {item ? 'Surface displacement along the road (LOS)' : 'Surface displacement across the zone (LOS)'}
          <span title={profile.data?.description ?? ''}>
            <InfoIcon />
          </span>
        </h3>
        {profile.isLoading ? <Loading what="the profile" /> : null}
        {profile.isError ? <ErrorNote error={profile.error} context="the profile" /> : null}
        {profile.data ? (
          <ProfileChart profile={profile.data} title={`Line-of-sight profile for ${title}`} />
        ) : null}
        <AcquisitionTimeline event={summary} />
      </section>

      <section>
        <h3 className="ev-title">Key evidence</h3>
        <ul className="kv-list">
          <li>
            <span className="k-ico">
              <SatelliteIcon />
            </span>
            <span>
              <strong>NISAR local LOS motion</strong>
              <span>
                {cm(localValue)} ({localLabel})
              </span>
            </span>
          </li>
          <li>
            <span className="k-ico">
              <WaveIcon />
            </span>
            <span>
              <strong>Coherence</strong>
              <span>median {num(coh ?? null)} (0 = noise, 1 = identical echoes)</span>
            </span>
          </li>
          <li>
            <span className="k-ico">
              <SignalIcon />
            </span>
            <span>
              <strong>Scene-relative motion</strong>
              <span>median {signedCm(scene ?? null)} (context, not ranked)</span>
            </span>
          </li>
        </ul>
      </section>

      <section className="ring-box">
        <div className="ring-card">
          <span className="eyebrow">Valid radar pixels</span>
          <div className="ring-row">
            <span className="big">{pct(validFraction)}</span>
            <Ring fraction={validFraction} label={`${pct(validFraction)} of pixels valid`} />
          </div>
          <span className="eyebrow" style={{ display: 'block', marginTop: 12 }}>
            Inspection priority
          </span>
          {item ? (
            <span className="prio on">
              <AlertIcon />
              {item.score.toFixed(1)} / 100 · rank {item.rank}
            </span>
          ) : (
            <span className="prio off">Not ranked: no road within reach</span>
          )}
        </div>
        <button type="button" className="btn btn-primary btn-block" onClick={onReview}>
          Review evidence
          <ArrowRight />
        </button>
        <p className="scale-note">
          {detail.corrections.applied.length === 0 ? 'No atmospheric correction applied.' : ''} One viewing
          direction; relative values.
        </p>
      </section>
    </section>
  );
}

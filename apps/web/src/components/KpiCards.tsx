import { cm, int, pct } from '../lib/format';
import type { EventDetail } from '../types/api';
import { ActivityIcon, AlertIcon, CheckIcon, EyeOffIcon } from './Icons';

/** Four headline figures, all computed from the fixture. No trends are shown: there is one interferogram. */
export function KpiCards({ event }: { event: EventDetail }) {
  const q = event.quality;
  const cards = [
    {
      tone: 'tone-orange',
      icon: <ActivityIcon />,
      label: 'Deformation zones',
      value: String(event.zone_count),
      note: `≥ ${cm(event.threshold.threshold_m)} local motion over ≥ 0.5 km²`,
    },
    {
      tone: 'tone-red',
      icon: <AlertIcon />,
      label: 'Roads to inspect',
      value: String(event.queue_length),
      note: `road segments within ${(event.infrastructure.proximity_limit_m / 1000).toFixed(1)} km of a zone`,
    },
    {
      tone: 'tone-slate',
      icon: <EyeOffIcon />,
      label: 'Road pixels unobserved',
      value: pct(event.road_coverage.excluded_fraction),
      note: `of ${int(event.road_coverage.road_pixels)} road-crossed pixels: unobserved, not cleared`,
    },
    {
      tone: 'tone-green',
      icon: <CheckIcon />,
      label: 'Valid radar pixels',
      value: pct(q.fractions.VALID),
      note: `${pct(q.fractions.CAUTION)} caution · ${pct(q.fractions.EXCLUDED)} excluded`,
    },
  ];
  return (
    <section className="kpis" aria-label="Headline figures">
      {cards.map((c) => (
        <dl key={c.label} className={`card kpi ${c.tone}`}>
          <span className="k-ico" aria-hidden>
            {c.icon}
          </span>
          <div>
            <dt>{c.label}</dt>
            <dd className="k-val">{c.value}</dd>
            <dd className="k-note">{c.note}</dd>
          </div>
        </dl>
      ))}
    </section>
  );
}

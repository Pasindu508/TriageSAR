import { useElementWidth } from '../hooks/useElementWidth';
import type { ProfileResponse } from '../types/api';

const PAD = { l: 52, r: 14, t: 12, b: 28 };

function niceStep(range: number): number {
  const raw = range / 4;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const n = raw / pow;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * pow;
}

/** Line-of-sight values along a road or across a zone. Gaps (excluded pixels) are shaded, never joined. */
export function ProfileChart({ profile, title }: { profile: ProfileResponse; title: string }) {
  // Draw in real pixels so labels keep a readable size on phones as well as desktops.
  const [box, measured] = useElementWidth<HTMLElement>(560);
  const W = Math.max(280, measured);
  const H = W < 420 ? 180 : 200;
  const toCm = (v: number | null) => (v == null ? null : v * 100);
  const local = profile.local_m.map(toCm);
  // Scale to the local field (what zones use); the scene-relative median is reported beside the chart.
  const finite = local.filter((v): v is number => v != null);
  const thr = profile.threshold_m * 100;
  const hi = Math.max(thr * 1.4, ...finite.map(Math.abs), 1);
  const lo = -hi;
  const step = niceStep(hi - lo);
  const yMax = Math.ceil(hi / step) * step;
  const yMin = -yMax;
  const xMax = profile.length_km || 1;
  const x = (d: number) => PAD.l + (d / xMax) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + ((yMax - v) / (yMax - yMin)) * (H - PAD.t - PAD.b);

  const path = (vals: Array<number | null>) => {
    let d = '';
    let pen = false;
    vals.forEach((v, i) => {
      const dist = profile.distance_km[i] ?? 0;
      if (v == null) {
        pen = false;
        return;
      }
      d += `${pen ? 'L' : 'M'}${x(dist).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  const gaps: Array<[number, number]> = [];
  local.forEach((v, i) => {
    if (v != null) return;
    const d = profile.distance_km[i] ?? 0;
    const last = gaps[gaps.length - 1];
    if (last && Math.abs(last[1] - (profile.distance_km[i - 1] ?? -1)) < 1e-9) last[1] = d;
    else gaps.push([d, d]);
  });
  const ticks: number[] = [];
  for (let v = yMin; v <= yMax + 1e-9; v += step) ticks.push(Math.round(v * 100) / 100);
  const xTicks = W < 420 ? [0, xMax / 2, xMax] : [0, xMax / 4, xMax / 2, (3 * xMax) / 4, xMax];
  const observed = local.filter((v) => v != null).length;
  const maxAbs = Math.max(0, ...local.filter((v): v is number => v != null).map(Math.abs));
  const summary = `${title}. ${profile.length_km.toFixed(1)} km sampled at ${profile.distance_km.length} points; ${observed} observed. Largest local line-of-sight value ${maxAbs.toFixed(1)} cm; screening threshold ${thr.toFixed(1)} cm.`;

  return (
    <figure ref={box} style={{ margin: 0 }}>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
        {gaps.map(([a, b]) => (
          <rect
            key={`${a}-${b}`}
            className="gap"
            x={x(a) - 1}
            y={PAD.t}
            width={Math.max(2, x(b) - x(a) + 2)}
            height={H - PAD.t - PAD.b}
          />
        ))}
        <rect className="thr" x={PAD.l} y={y(thr)} width={W - PAD.l - PAD.r} height={y(-thr) - y(thr)} />
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={PAD.l} x2={W - PAD.r} y1={y(t)} y2={y(t)} />
            <text x={PAD.l - 8} y={y(t) + 4} textAnchor="end">
              {t > 0 ? '+' : ''}
              {t} cm
            </text>
          </g>
        ))}
        <line className="thr-line" x1={PAD.l} x2={W - PAD.r} y1={y(thr)} y2={y(thr)} />
        <line className="thr-line" x1={PAD.l} x2={W - PAD.r} y1={y(-thr)} y2={y(-thr)} />
        {xTicks.map((t) => (
          <text key={t} x={x(t)} y={H - 8} textAnchor={t === 0 ? 'start' : t === xMax ? 'end' : 'middle'}>
            {t.toFixed(1)} km
          </text>
        ))}
        <path className="local" d={path(local)} />
      </svg>
      <figcaption className="chart-legend">
        <span>Local LOS (used for zones)</span>
        <span className="l-thr">±{thr.toFixed(1)} cm threshold</span>
        <span className="l-gap">Excluded (unobserved)</span>
      </figcaption>
    </figure>
  );
}

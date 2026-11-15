import { cm } from '../lib/format';
import type { RasterMetadata } from '../types/api';
import { ChevronDown, LayersIcon } from './Icons';

export type MotionLayer = 'scene' | 'local' | 'none';
export type Basemap = 'plain' | 'satellite' | 'terrain';

export interface LayerState {
  motion: MotionLayer;
  basemap: Basemap;
  quality: boolean;
  zones: boolean;
  roads: boolean;
  markers: boolean;
}

export const DEFAULT_LAYERS: LayerState = {
  motion: 'scene',
  basemap: 'terrain',
  quality: true,
  zones: true,
  roads: true,
  markers: true,
};

const TOGGLES: Array<[keyof LayerState, string]> = [
  ['quality', 'Show uncertainty (quality)'],
  ['zones', 'Deformation zones'],
  ['roads', 'Roads'],
  ['markers', 'Inspection markers'],
];

interface Props {
  layers: LayerState;
  onChange: (next: LayerState) => void;
  raster: RasterMetadata | null;
  hasObservations: boolean;
}

/** Map controls: motion layer, extra layers and basemap. All are native, keyboard-operable controls. */
export function MapControls({ layers, onChange, raster, hasObservations }: Props) {
  return (
    <>
      <div className="map-ctl tl">
        <label className="chipbox layer-select">
          <span className="sr-only">Motion layer</span>
          <span className="ico">
            <LayersIcon />
          </span>
          <select
            value={hasObservations ? layers.motion : 'none'}
            disabled={!hasObservations}
            onChange={(e) => onChange({ ...layers, motion: e.target.value as MotionLayer })}
          >
            <option value="scene">Surface motion (LOS)</option>
            <option value="local" disabled={!raster?.local_url}>
              Local motion (used for zones)
            </option>
            <option value="none">No motion layer</option>
          </select>
          <span className="chev">
            <ChevronDown />
          </span>
        </label>
        <details className="chipbox more-layers">
          <summary>More layers</summary>
          <fieldset>
            <legend className="sr-only">Map layers</legend>
            {TOGGLES.map(([key, label]) => {
              const disabled = !hasObservations && key !== 'roads';
              return (
                <label key={key} className="layer-row">
                  <input
                    type="checkbox"
                    checked={Boolean(layers[key]) && !disabled}
                    disabled={disabled}
                    onChange={(e) => onChange({ ...layers, [key]: e.target.checked })}
                  />
                  {label}
                </label>
              );
            })}
          </fieldset>
        </details>
      </div>
      <div className="map-ctl tr">
        <div className="chipbox seg" role="group" aria-label="Basemap">
          {(
            [
              ['plain', 'Plain'],
              ['satellite', 'Satellite'],
              ['terrain', 'Terrain'],
            ] as Array<[Basemap, string]>
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={layers.basemap === key}
              onClick={() => onChange({ ...layers, basemap: key })}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

/** Legend in the map corner. Every symbol is described in text. */
export function MapLegend({ layers, raster }: { layers: LayerState; raster: RasterMetadata | null }) {
  const limit = layers.motion === 'local' ? raster?.local_colour_limit_m : raster?.colour_limit_m;
  // Open by default, except on phones where the legend would cover most of the map.
  const startOpen = typeof window === 'undefined' || !window.matchMedia?.('(max-width: 640px)').matches;
  return (
    <details className="legend-card" open={startOpen}>
      <summary>
        <span className="sr-only">Legend: </span>
        {layers.motion === 'local' ? 'Local motion (LOS)' : 'Surface motion (LOS)'}
        {layers.motion === 'none' ? ' hidden' : ''}
      </summary>
      {raster && layers.motion !== 'none' ? (
        <>
          <div className="ramp" aria-hidden />
          <div className="ramp-labels">
            <span>−{cm(limit, 0)}</span>
            <span>0</span>
            <span>+{cm(limit, 0)}</span>
          </div>
          <p style={{ margin: '4px 0 0' }}>
            Blue: towards the satellite · Orange: away.{' '}
            {layers.motion === 'local'
              ? 'Full colour = screening threshold.'
              : 'Relative to the scene median.'}
          </p>
        </>
      ) : null}
      <ul className="legend-list">
        <li>
          <span className="swatch swatch-caution" aria-hidden />
          <span>CAUTION</span>
        </li>
        <li>
          <span className="swatch swatch-excluded" aria-hidden />
          <span>EXCLUDED</span>
        </li>
        <li>
          <span className="swatch swatch-zone" aria-hidden />
          <span>Zone</span>
        </li>
        <li>
          <span className="swatch swatch-road" aria-hidden />
          <span>Road (OSM)</span>
        </li>
      </ul>
      <p className="sr-only">
        Dots mark CAUTION pixels (weaker evidence); diagonal hatching marks EXCLUDED pixels (unobserved);
        white outlines are deformation zones; lines are OpenStreetMap roads.
      </p>
    </details>
  );
}

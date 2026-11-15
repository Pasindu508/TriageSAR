import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useDocumentTitle } from '../accessibility/useDocumentTitle';
import { CalendarIcon, ChevronDown, PinIcon } from '../components/Icons';
import { KpiCards } from '../components/KpiCards';
import { DEFAULT_LAYERS, MapControls, MapLegend, type LayerState } from '../components/MapControls';
import { ErrorNote, Loading } from '../components/Status';
import { EvidenceDrawer } from '../features/EvidenceDrawer';
import { EvidenceStrip } from '../features/EvidenceStrip';
import { QueueColumn, type Target } from '../features/QueueColumn';
import { SceneSummary } from '../features/SceneSummary';
import { useEvent, useEvents, useHotspots, useQueue, useRaster, useRoads } from '../hooks/queries';
import { ApiError } from '../lib/api';
import { cm, pct, shortDate } from '../lib/format';

const MapView = lazy(() => import('../features/MapView'));
const NISAR_ATTRIBUTION = 'NISAR L2 GUNW: NASA/ISRO via ASF DAAC';

export function EventPage({ onOpenProvenance }: { onOpenProvenance: () => void }) {
  const { eventId = '' } = useParams();
  const navigate = useNavigate();
  const events = useEvents();
  const summary = events.data?.events.find((e) => e.id === eventId);
  const ready = summary?.status === 'ready';
  const detail = useEvent(eventId, ready);
  const raster = useRaster(eventId, ready);
  const hotspots = useHotspots(eventId, ready);
  const queue = useQueue(eventId, ready);
  const roads = useRoads(eventId);
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);
  const [target, setTarget] = useState<Target | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  useDocumentTitle(summary?.title ?? 'Case study');

  const items = useMemo(() => queue.data?.items ?? [], [queue.data]);
  const zones = useMemo(() => hotspots.data?.features ?? [], [hotspots.data]);

  // Default selection: the top-ranked road, otherwise the first zone. Reset when the event changes.
  useEffect(() => {
    setTarget(null);
    setDrawerOpen(false);
  }, [eventId]);
  useEffect(() => {
    if (target || !queue.data || !hotspots.data) return;
    if (items[0]) setTarget({ kind: 'item', id: items[0].id });
    else if (zones[0]) setTarget({ kind: 'zone', id: zones[0].id });
  }, [target, queue.data, hotspots.data, items, zones]);

  const item = target?.kind === 'item' ? (items.find((i) => i.id === target.id) ?? null) : null;
  const zone = target?.kind === 'zone' ? (zones.find((z) => z.id === target.id) ?? null) : null;
  const selectItem = useCallback((id: string) => setTarget({ kind: 'item', id }), []);
  const selectZone = useCallback((id: string) => setTarget({ kind: 'zone', id }), []);

  if (events.isLoading) {
    return (
      <div className="page">
        <Loading what="the case study" />
      </div>
    );
  }
  if (events.isError || !summary) {
    return (
      <div className="page">
        <h1>Case study unavailable</h1>
        <ErrorNote
          error={
            events.error ?? new ApiError(404, 'event_not_found', `There is no event called “${eventId}”.`)
          }
          context="this case study"
        />
      </div>
    );
  }

  const ref = summary.acquisitions.find((a) => a.role === 'reference');
  const sec = summary.acquisitions.find((a) => a.role === 'secondary');
  const attribution = `${summary.data_kind === 'synthetic_test' ? 'Synthetic test data (not NASA observations)' : NISAR_ATTRIBUTION} | Roads: ${roads.data?.attribution ?? '© OpenStreetMap contributors'}`;
  const top = items[0];
  const mapSummary = ready
    ? `The map shows ${zones.length} deformation zone${zones.length === 1 ? '' : 's'} and ${items.length} ranked road segment${items.length === 1 ? '' : 's'}.` +
      (top
        ? ` Highest inspection priority: ${top.asset_name}, score ${top.score.toFixed(1)} out of 100, ${cm(top.corridor.p90_abs_los_m)} local line-of-sight motion, evidence quality ${top.evidence_quality}.`
        : ' No road is ranked.') +
      (zones[0]
        ? ` Zone ${zones[0].properties.zone_id} covers ${zones[0].properties.area_km2.toFixed(2)} square kilometres with up to ${cm(zones[0].properties.max_abs_los_m)} local motion.`
        : '') +
      (detail.data
        ? ` ${pct(detail.data.quality.fractions.EXCLUDED)} of radar pixels are excluded as unobserved.`
        : '') +
      ' The same information is listed beside the map.'
    : 'The map shows the study area and roads only. No radar observations are loaded for this event yet.';

  return (
    <div className="dash">
      <header className="dash-head">
        <div>
          <h1>Infrastructure intelligence</h1>
          <p>From satellite surface motion to an evidence-ranked inspection queue</p>
        </div>
        <div className="dash-controls">
          <span className="pill" title="Reference and secondary acquisitions of the interferogram">
            <CalendarIcon />
            {ref && sec
              ? `${shortDate(ref.start_utc)} – ${shortDate(sec.start_utc)} 2026`
              : 'Dates not available'}
          </span>
          <label className="select-wrap">
            <span className="sr-only">Case study</span>
            <span className="ico">
              <PinIcon />
            </span>
            <select value={eventId} onChange={(e) => navigate(`/events/${e.target.value}`)}>
              {(events.data?.events ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title}
                  {e.status === 'ready' ? '' : ' (not built)'}
                </option>
              ))}
            </select>
            <span className="chev">
              <ChevronDown />
            </span>
          </label>
        </div>
      </header>

      <p className="disclaimer" role="note">
        <span>
          <strong>This is not a damage assessment.</strong> {summary.data_label}: research-grade, provisional
          observations, ranked for human field inspection only.
        </span>
      </p>

      {detail.data ? <KpiCards event={detail.data} /> : null}
      {detail.isError ? <ErrorNote error={detail.error} context="the analysis" /> : null}

      <div className="grid-main">
        <div className="map-card">
          <p className="sr-only" role="status">
            {mapSummary}
          </p>
          <Suspense fallback={<Loading what="the map" />}>
            <MapView
              key={eventId}
              label={`Map of ${summary.title}`}
              bbox={summary.bbox_wgs84}
              raster={raster.data ?? null}
              zones={zones}
              roads={roads.data?.roads ?? null}
              places={roads.data?.places ?? null}
              epicentres={summary.epicentres}
              items={items}
              selectedId={item?.id ?? null}
              focusZoneId={zone?.id ?? null}
              onSelect={selectItem}
              onZoneSelect={selectZone}
              layers={layers}
              attribution={attribution}
            />
          </Suspense>
          <MapControls
            layers={layers}
            onChange={setLayers}
            raster={raster.data ?? null}
            hasObservations={ready}
          />
          <MapLegend layers={layers} raster={raster.data ?? null} />
          {!ready ? (
            <div className="card map-empty" role="status">
              <h2>No NISAR observations loaded</h2>
              <p>{summary.status_message}</p>
              {summary.build_command ? <code className="cmd">{summary.build_command}</code> : null}
            </div>
          ) : null}
        </div>

        <div style={{ display: 'grid', gap: 14 }}>
          {queue.data ? (
            <QueueColumn
              eventId={eventId}
              queue={queue.data}
              zones={zones}
              target={target}
              onTarget={setTarget}
              proximityLimitM={detail.data?.infrastructure.proximity_limit_m ?? null}
              unobservedFraction={detail.data?.road_coverage.excluded_fraction ?? null}
            />
          ) : (
            <section className="card card-pad" aria-labelledby="queue-h">
              <h2 className="card-title" id="queue-h">
                Evidence-ranked inspection queue
              </h2>
              {queue.isError ? <ErrorNote error={queue.error} context="the inspection queue" /> : null}
              {ready && queue.isLoading ? <Loading what="the inspection queue" /> : null}
              {!ready ? (
                <p className="note" style={{ marginTop: 10 }}>
                  The inspection queue is <strong>not computed</strong> because the real-data fixture has not
                  been built. Nothing is shown in its place.
                </p>
              ) : null}
            </section>
          )}
          {detail.data ? <SceneSummary event={detail.data} /> : null}
        </div>
      </div>

      {detail.data && queue.data && hotspots.data ? (
        <EvidenceStrip
          summary={summary}
          detail={detail.data}
          target={target}
          item={item}
          zone={zone}
          onReview={() => setDrawerOpen(true)}
        />
      ) : null}

      {detail.data ? (
        <EvidenceDrawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          event={detail.data}
          item={item}
          zone={zone}
          itemZone={item ? zones.find((z) => z.id === item.zone_id) : undefined}
          onOpenProvenance={onOpenProvenance}
        />
      ) : null}
    </div>
  );
}

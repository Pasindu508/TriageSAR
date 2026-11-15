import { Link, useParams } from 'react-router-dom';
import { useDocumentTitle } from '../accessibility/useDocumentTitle';
import { ErrorNote, Loading } from '../components/Status';
import { useEvent, useHotspots, useQueue } from '../hooks/queries';
import { cm, length, num, pct, signedCm, utcDate } from '../lib/format';

/** Text alternative: the whole product without the interactive map. */
export function QueueTablePage() {
  const { eventId = '' } = useParams();
  const detail = useEvent(eventId);
  const queue = useQueue(eventId, true);
  const hotspots = useHotspots(eventId, true);
  useDocumentTitle('Inspection queue (text)');
  const error = detail.error ?? queue.error;
  return (
    <div className="page" style={{ maxWidth: 1240 }}>
      <p>
        <Link to={`/events/${eventId}`}>← Back to the map</Link>
      </p>
      <h1>Inspection queue</h1>
      {detail.isLoading || queue.isLoading ? <Loading what="the inspection queue" /> : null}
      {error ? <ErrorNote error={error} context="the inspection queue" /> : null}
      {detail.data && queue.data ? (
        <>
          <p className="lede">
            {detail.data.event.title}. {detail.data.event.data_label}, granule{' '}
            <span className="mono">{detail.data.provenance_summary.granule_id}</span>, reference{' '}
            {utcDate(detail.data.provenance_summary.reference_start_utc)}, secondary{' '}
            {utcDate(detail.data.provenance_summary.secondary_start_utc)}.
          </p>
          <p className="note" role="note" style={{ margin: '14px 0' }}>
            <strong>This is not a damage assessment.</strong>{' '}
            {queue.data.disclaimer.replace('This is not a damage assessment. ', '')}
          </p>
          {queue.data.total === 0 ? (
            <p className="note info" style={{ margin: '14px 0' }}>
              <strong>No road is ranked.</strong> No mapped road (motorway to tertiary) lies within{' '}
              {length(detail.data.infrastructure.proximity_limit_m)} of a deformation zone. This is a result,
              not an error, and not a statement that roads are undamaged:{' '}
              {pct(detail.data.road_coverage.excluded_fraction)} of road-crossed pixels have no usable radar
              observation.
            </p>
          ) : null}
          <div className="table-wrap">
            <table className="data">
              <caption className="sr-only">
                Road segments ranked by inspection priority score, with the radar evidence behind each
              </caption>
              <thead>
                <tr>
                  <th scope="col" className="num">
                    Rank
                  </th>
                  <th scope="col">Road</th>
                  <th scope="col" className="num">
                    Priority score
                  </th>
                  <th scope="col">Zone</th>
                  <th scope="col">Relation</th>
                  <th scope="col" className="num">
                    |LOS| p90
                  </th>
                  <th scope="col" className="num">
                    Valid pixels
                  </th>
                  <th scope="col">Evidence quality</th>
                  <th scope="col">Rank range</th>
                </tr>
              </thead>
              <tbody>
                {queue.data.items.map((item) => (
                  <tr key={item.id}>
                    <td className="num">{item.rank}</td>
                    <th
                      scope="row"
                      style={{
                        textTransform: 'none',
                        letterSpacing: 0,
                        color: 'var(--text)',
                        fontSize: '0.92rem',
                      }}
                    >
                      {item.asset_name}
                      <span className="scale-note" style={{ display: 'block', fontWeight: 400 }}>
                        {item.highway_class}
                      </span>
                    </th>
                    <td className="num">{item.score.toFixed(1)}</td>
                    <td>{item.zone_id}</td>
                    <td>
                      {item.relation === 'overlaps'
                        ? `${length(item.overlap_length_m)} inside`
                        : `${length(item.distance_m)} away`}
                    </td>
                    <td className="num">{cm(item.corridor.p90_abs_los_m)}</td>
                    <td className="num">{pct(item.corridor.valid_fraction)}</td>
                    <td>{item.evidence_quality}</td>
                    <td>
                      {item.stability
                        ? `${item.stability.min_rank}–${item.stability.max_rank}`
                        : 'not computed'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h2>Deformation zones</h2>
          <p>{detail.data.reference.description}</p>
          <div className="table-wrap" style={{ marginTop: 10 }}>
            <table className="data">
              <caption className="sr-only">
                Deformation zones with their radar evidence and nearest road
              </caption>
              <thead>
                <tr>
                  <th scope="col">Zone</th>
                  <th scope="col" className="num">
                    Area
                  </th>
                  <th scope="col" className="num">
                    Median local LOS
                  </th>
                  <th scope="col" className="num">
                    Largest |LOS|
                  </th>
                  <th scope="col" className="num">
                    Scene-relative median
                  </th>
                  <th scope="col" className="num">
                    Valid pixels
                  </th>
                  <th scope="col" className="num">
                    Median coherence
                  </th>
                  <th scope="col">Nearest road</th>
                </tr>
              </thead>
              <tbody>
                {(hotspots.data?.features ?? []).map((zone) => {
                  const z = zone.properties;
                  return (
                    <tr key={z.zone_id}>
                      <th scope="row" style={{ color: 'var(--text)' }}>
                        {z.zone_id}
                      </th>
                      <td className="num">{z.area_km2.toFixed(2)} km²</td>
                      <td className="num">{signedCm(z.median_los_m)}</td>
                      <td className="num">{cm(z.max_abs_los_m)}</td>
                      <td className="num">{signedCm(z.scene_median_los_m)}</td>
                      <td className="num">{pct(z.valid_fraction)}</td>
                      <td className="num">{num(z.median_coherence)}</td>
                      <td>
                        {z.nearest_road_name == null || z.nearest_road_distance_m == null
                          ? 'not computed'
                          : `${z.nearest_road_name}, ${z.nearest_road_distance_m === 0 ? 'crosses the zone' : `${length(z.nearest_road_distance_m)} away`}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="scale-note" style={{ marginTop: 10 }}>
            {queue.data.total} road segments. Score = 100 × Σ (weight × factor); weights:{' '}
            {Object.entries(queue.data.weights)
              .map(([k, v]) => `${k.replace(/_/g, ' ')} ${v.toFixed(2)}`)
              .join(', ')}
            . Rank range is under ±{pct(queue.data.sensitivity.perturbation_fraction)} weight perturbation.
          </p>
        </>
      ) : null}
    </div>
  );
}

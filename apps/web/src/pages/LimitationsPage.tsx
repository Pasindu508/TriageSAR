import { Link } from 'react-router-dom';
import { useDocumentTitle } from '../accessibility/useDocumentTitle';
import { ErrorNote, Loading } from '../components/Status';
import { useMethodology } from '../hooks/queries';

export function LimitationsPage() {
  useDocumentTitle('Limitations');
  const { data, isLoading, isError, error } = useMethodology();
  return (
    <div className="page">
      <p className="eyebrow">Limitations</p>
      <h1>What this tool cannot tell you</h1>
      <p className="lede">
        TriageSAR is a research prototype built in a hackathon. It has never been compared with field
        inspection results, so nobody knows yet how often its top-ranked roads turn out to matter.
      </p>
      <div className="note" role="note" style={{ marginTop: 16 }}>
        <strong>This is not a damage assessment.</strong> Ground motion is not damage. A road can move with
        the ground and stay intact, and a structure can fail where the radar saw nothing.
      </div>
      {isLoading ? <Loading what="the limitations" /> : null}
      {isError ? <ErrorNote error={error} context="the limitations" /> : null}
      {data ? (
        <>
          <h2>Scientific limitations</h2>
          <ul>
            {data.limitations.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <h2>What is not claimed</h2>
          <ul>
            {data.not_claimed.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </>
      ) : null}
      <h2>Before any operational use</h2>
      <ul>
        <li>Comparison of ranked zones with real field-inspection outcomes across several events.</li>
        <li>
          Atmospheric correction and a second viewing geometry (ascending and descending) to separate vertical
          from horizontal motion.
        </li>
        <li>
          Authoritative road and bridge inventories from the responsible agency, instead of OpenStreetMap
          alone.
        </li>
        <li>
          Review by remote-sensing scientists and structural engineers, and agreement with the responding
          agency on how the queue is used.
        </li>
      </ul>
      <p style={{ marginTop: 16 }}>
        The method is described in the <Link to="/methodology">methodology</Link>.
      </p>
    </div>
  );
}

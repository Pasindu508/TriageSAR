import { useDocumentTitle } from '../accessibility/useDocumentTitle';
import { EventCard } from '../components/EventCard';
import { ErrorNote, Loading } from '../components/Status';
import { useEvents } from '../hooks/queries';
import { utcDateTime } from '../lib/format';
import type { AutoIngestStatus } from '../types/api';

function AutoIngestNote({ status }: { status: AutoIngestStatus }) {
  return (
    <p className="note info auto-note" role="status">
      <strong>Automatic updates.</strong>{' '}
      {status.enabled ? (
        <>
          New NISAR data over significant earthquakes were last checked {utcDateTime(status.last_checked_utc)}
          . {status.added_total} case {status.added_total === 1 ? 'study has' : 'studies have'} been added
          automatically
          {status.waiting > 0
            ? `; ${status.waiting} earthquake${status.waiting === 1 ? ' is' : 's are'} waiting for NISAR to publish an interferogram`
            : ''}
          .
        </>
      ) : (
        <>Automatic checking has not run on this server yet.</>
      )}
      <span className="scale-note" style={{ display: 'block' }}>
        {status.description}
      </span>
    </p>
  );
}

/** All case studies. Each is one real NISAR interferogram spanning an earthquake. */
export function EventsPage() {
  useDocumentTitle('Case studies');
  const events = useEvents();
  return (
    <div className="page" style={{ maxWidth: 1240 }}>
      <p className="eyebrow">Case studies</p>
      <h1>Earthquakes observed by NISAR in 2026</h1>
      <p className="lede">
        Each case study is one NASA–ISRO NISAR interferogram whose two acquisitions bracket the earthquake,
        cropped to a study area and analysed in exactly the same way.
      </p>
      {events.data ? <AutoIngestNote status={events.data.auto_ingest} /> : null}
      {events.data?.snapshot ? (
        <p className="scale-note">
          This site is a static snapshot exported {utcDateTime(events.data.snapshot.generated_utc)}
          {events.data.snapshot.commit ? ` from commit ${events.data.snapshot.commit.slice(0, 7)}` : ''}. New
          case studies appear after the next rebuild.
        </p>
      ) : null}
      {events.isLoading ? <Loading what="case studies" /> : null}
      {events.isError ? <ErrorNote error={events.error} context="the case studies" /> : null}
      <div className="event-grid">
        {events.data?.events.map((e) => (
          <EventCard key={e.id} event={e} />
        ))}
      </div>
    </div>
  );
}

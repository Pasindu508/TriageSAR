import { useDocumentTitle } from '../accessibility/useDocumentTitle';
import { EventCard } from '../components/EventCard';
import { ErrorNote, Loading } from '../components/Status';
import { useEvents } from '../hooks/queries';
import { utcDateTime } from '../lib/format';

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
      {events.data?.snapshot ? (
        <p className="scale-note">
          Case studies published{' '}
          <time dateTime={events.data.snapshot.generated_utc}>
            {utcDateTime(events.data.snapshot.generated_utc)}
          </time>
          .
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

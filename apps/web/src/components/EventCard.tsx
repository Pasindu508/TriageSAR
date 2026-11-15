import { Link } from 'react-router-dom';
import { shortDate, utcDateTime } from '../lib/format';
import type { EventSummary } from '../types/api';
import { CalendarIcon, PinIcon } from './Icons';

/** One case study, shared by the Case studies and About pages. */
export function EventCard({ event }: { event: EventSummary }) {
  const ref = event.acquisitions.find((a) => a.role === 'reference');
  const sec = event.acquisitions.find((a) => a.role === 'secondary');
  return (
    <Link to={`/events/${event.id}`} className="card event-card">
      <span className="eyebrow">{event.data_label}</span>
      <h2>{event.title}</h2>
      <p className="meta">
        <PinIcon />
        {event.place ?? 'location not recorded'}
        {event.magnitude != null ? ` · M ${event.magnitude}` : ''}
      </p>
      <p className="meta">
        <CalendarIcon />
        {event.event_time_utc ? utcDateTime(event.event_time_utc) : 'no event time'}
      </p>
      <p>
        Interferogram:{' '}
        {ref && sec
          ? `${shortDate(ref.start_utc)} → ${shortDate(sec.start_utc)}`
          : 'not built on this machine'}
      </p>
      <span className="chips" style={{ marginTop: 0 }}>
        <span className={`chip ${event.status === 'ready' ? 'chip-valid' : 'chip-warn'}`}>
          {event.status === 'ready' ? 'FIXTURE READY' : 'FIXTURE NOT BUILT YET'}
        </span>
        {event.added_by === 'auto_ingest' ? (
          <span
            className="chip chip-info"
            title="Found and processed by the automatic ingest, without manual review"
          >
            ADDED AUTOMATICALLY{event.added_on ? ` · ${shortDate(event.added_on)}` : ''}
          </span>
        ) : null}
      </span>
    </Link>
  );
}

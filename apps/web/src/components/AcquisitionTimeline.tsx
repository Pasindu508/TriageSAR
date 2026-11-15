import { shortDate } from '../lib/format';
import type { EventSummary } from '../types/api';
import { InfoIcon } from './Icons';

/** NISAR acquisitions of this track and frame around the event, from the ASF catalogue. */
export function AcquisitionTimeline({ event }: { event: EventSummary }) {
  const dates = event.acquisition_dates;
  if (dates.length === 0) return null;
  const eventDay = event.event_time_utc?.slice(0, 10) ?? null;
  type Entry = { key: string; date: string; kind: 'used' | 'other' | 'event' };
  const entries: Entry[] = dates.map((a) => ({ key: a.date, date: a.date, kind: a.used ? 'used' : 'other' }));
  if (eventDay) entries.push({ key: `event-${eventDay}`, date: eventDay, kind: 'event' });
  entries.sort((a, b) => a.date.localeCompare(b.date) || (a.kind === 'event' ? 1 : -1));
  return (
    <section className="acq" aria-labelledby="acq-h">
      <h3 className="ev-title" id="acq-h">
        Satellite acquisitions (NISAR)
        <span title={event.acquisition_dates_source ?? ''}>
          <InfoIcon />
        </span>
      </h3>
      <ol>
        {entries.map((e) => (
          <li key={e.key} className={e.kind === 'other' ? '' : e.kind}>
            <span className="dot" aria-hidden />
            <span>
              {shortDate(e.date)}
              <span className="sr-only">
                {e.kind === 'used'
                  ? ': acquisition used in this interferogram'
                  : e.kind === 'event'
                    ? ': earthquake'
                    : ': acquisition, not used'}
              </span>
            </span>
          </li>
        ))}
      </ol>
      <p className="scale-note">
        Filled: the two acquisitions used. Open: other acquisitions of the same track and frame. Diamond: the
        earthquake.
      </p>
    </section>
  );
}

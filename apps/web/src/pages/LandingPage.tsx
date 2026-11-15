import { Link } from 'react-router-dom';
import { useDocumentTitle } from '../accessibility/useDocumentTitle';
import { EventCard } from '../components/EventCard';
import { ArrowRight, CheckIcon, LayersIcon, ListIcon, SatelliteIcon, SlashIcon } from '../components/Icons';
import { ErrorNote, Loading } from '../components/Status';
import { useEvents } from '../hooks/queries';

const STEPS = [
  {
    icon: <SatelliteIcon />,
    label: '1 · Observe',
    title: 'Real NISAR interferograms',
    text: 'Unwrapped phase from a NISAR GUNW product becomes line-of-sight range change, using the wavelength in the product’s own metadata.',
  },
  {
    icon: <LayersIcon />,
    label: '2 · Quality-gate',
    title: 'Uncertainty stays visible',
    text: 'Every pixel is VALID, CAUTION or EXCLUDED by transparent rules. Excluded areas are shown as unobserved and never filled in.',
  },
  {
    icon: <ListIcon />,
    label: '3 · Prioritise',
    title: 'An auditable inspection queue',
    text: 'Zones that move differently from their surroundings are intersected with roads. Six visible factors give a score you can check by hand.',
  },
];

const DOES = [
  'Reads real NISAR data and keeps every value traceable to its granule',
  'Shows where radar evidence of ground motion meets roads, and how good that evidence is',
  'Says plainly when nothing stands out, and which roads it could not observe',
];
const DOES_NOT = [
  'Detect structural damage or predict casualties',
  'Treat satellite observations as ground truth',
  'Turn the score into a probability, an accuracy or a “confidence”',
];
const SOURCES = [
  ['NISAR L2 GUNW', 'NASA–ISRO, via ASF DAAC'],
  ['Earthquake catalogue', 'USGS'],
  ['Roads and places', '© OpenStreetMap contributors'],
  ['Basemaps (optional)', 'NASA GIBS'],
];

export function LandingPage() {
  useDocumentTitle('About');
  const events = useEvents();
  const list = events.data?.events ?? [];
  const first = list.find((e) => e.status === 'ready' && e.data_kind === 'nasa_nisar_gunw') ?? list[0];
  const ready = list.filter((e) => e.status === 'ready' && e.data_kind === 'nasa_nisar_gunw').length;
  return (
    <div className="about">
      <section className="about-hero" aria-labelledby="hero-h">
        <div className="about-hero-text">
          <p className="eyebrow">NASA Space Apps 2026 · Dancing with the SARs</p>
          <h1 id="hero-h">
            <span>See where the ground moved.</span>
            <span className="hl">Know where to inspect first.</span>
          </h1>
          <p className="sub">
            TriageSAR turns NASA–ISRO NISAR surface-motion observations into transparent, evidence-ranked
            infrastructure inspection priorities.
          </p>
          <div className="cta-row">
            <Link className="btn btn-brand" to={first ? `/events/${first.id}` : '/events'}>
              Explore the 2026 case study
              <ArrowRight />
            </Link>
            <Link className="btn btn-ghost" to="/methodology">
              How the science works
            </Link>
          </div>
          {ready > 0 ? (
            <p className="hero-note">
              {ready} real NISAR case {ready === 1 ? 'study' : 'studies'} ready to explore, analysed with
              identical settings.
            </p>
          ) : null}
        </div>
        <ol className="about-steps" aria-label="How TriageSAR works">
          {STEPS.map((s) => (
            <li key={s.label}>
              <span className="step-ico" aria-hidden>
                {s.icon}
              </span>
              <span>
                <span className="eyebrow">{s.label}</span>
                <strong>{s.title}</strong>
                <span className="step-text">{s.text}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className="about-section" aria-labelledby="events-h">
        <div className="section-head">
          <h2 id="events-h">Case studies</h2>
          <Link to="/events">
            All case studies <ArrowRight />
          </Link>
        </div>
        {events.isLoading ? <Loading what="case studies" /> : null}
        {events.isError ? <ErrorNote error={events.error} context="the case studies" /> : null}
        <div className="event-grid">
          {list.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      </section>

      <section className="about-section" aria-labelledby="scope-h">
        <h2 id="scope-h">What TriageSAR is, and is not</h2>
        <div className="scope-grid">
          <div className="card card-pad scope does">
            <h3>It does</h3>
            <ul>
              {DOES.map((t) => (
                <li key={t}>
                  <CheckIcon />
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="card card-pad scope does-not">
            <h3>It does not</h3>
            <ul>
              {DOES_NOT.map((t) => (
                <li key={t}>
                  <SlashIcon />
                  {t}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="note" role="note" style={{ marginTop: 14 }}>
          <strong>This is not a damage assessment.</strong> TriageSAR ranks where radar evidence of ground
          motion meets roads, so people can decide where to look first. Existing portals help experts inspect
          raster products; TriageSAR is the decision layer after the map. Read the{' '}
          <Link to="/limitations">limitations</Link>.
        </p>
      </section>

      <section className="about-section" aria-labelledby="data-h">
        <h2 id="data-h">Built on open data</h2>
        <ul className="source-list">
          {SOURCES.map(([name, by]) => (
            <li key={name} className="card">
              <strong>{name}</strong>
              <span>{by}</span>
            </li>
          ))}
        </ul>
        <p className="scale-note">
          Open source under Apache-2.0. Not affiliated with or endorsed by NASA, ISRO, JPL, ASF, USGS or
          OpenStreetMap.
        </p>
      </section>
    </div>
  );
}

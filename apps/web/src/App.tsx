import { useEffect, useState } from 'react';
import { Link, Navigate, Route, Routes, useLocation, useMatch } from 'react-router-dom';
import { SkipLink } from './accessibility/SkipLink';
import { LogoIcon, MenuIcon } from './components/Icons';
import { ProvenanceDrawer } from './components/ProvenanceDrawer';
import { Sidebar } from './components/Sidebar';
import { Loading } from './components/Status';
import { useEvent, useEvents } from './hooks/queries';
import { EventPage } from './pages/EventPage';
import { EventsPage } from './pages/EventsPage';
import { LandingPage } from './pages/LandingPage';
import { LimitationsPage } from './pages/LimitationsPage';
import { MethodologyPage } from './pages/MethodologyPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { QueueTablePage } from './pages/QueueTablePage';

function Home() {
  const events = useEvents();
  if (events.isLoading) {
    return (
      <div className="page">
        <Loading what="case studies" />
      </div>
    );
  }
  const list = events.data?.events ?? [];
  const first =
    list.find((e) => e.status === 'ready' && e.data_kind === 'nasa_nisar_gunw') ??
    list.find((e) => e.status === 'ready') ??
    list[0];
  return first ? <Navigate to={`/events/${first.id}`} replace /> : <EventsPage />;
}

export default function App() {
  const [provenanceOpen, setProvenanceOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const events = useEvents();
  // The small-screen menu closes on navigation and with Escape.
  useEffect(() => setMenuOpen(false), [location.pathname]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [menuOpen]);
  const match = useMatch('/events/:eventId/*');
  const eventId = match?.params.eventId ?? null;
  const current = events.data?.events.find((e) => e.id === eventId);
  const detail = useEvent(eventId ?? '', current?.status === 'ready');
  const synthetic = events.data?.events.some((e) => e.data_kind === 'synthetic_test') ?? false;
  const openProvenance = () => setProvenanceOpen(true);
  return (
    <div className="shell">
      <SkipLink />
      <Sidebar
        eventId={current ? eventId : null}
        queueCount={detail.data?.queue_length ?? null}
        onOpenProvenance={openProvenance}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
      />
      {menuOpen ? (
        <button
          type="button"
          className="menu-backdrop"
          aria-label="Close menu"
          tabIndex={-1}
          onClick={() => setMenuOpen(false)}
        />
      ) : null}
      <main id="main" className="main" tabIndex={-1}>
        <header className="mobile-bar">
          <Link to={current ? `/events/${eventId}` : '/'} className="brand" aria-label="TriageSAR home">
            <LogoIcon />
            <span>TriageSAR</span>
          </Link>
          <button
            type="button"
            className="menu-btn"
            aria-label="Open menu"
            aria-expanded={menuOpen}
            aria-controls="app-menu"
            onClick={() => setMenuOpen(true)}
          >
            <MenuIcon />
          </button>
        </header>
        {synthetic ? (
          <div className="banner-synthetic" role="status">
            SYNTHETIC TEST DATA ENABLED — the “synthetic test event” contains made-up values and is not a NASA
            observation.
          </div>
        ) : null}
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/events/:eventId" element={<EventPage onOpenProvenance={openProvenance} />} />
          <Route path="/events/:eventId/queue" element={<QueueTablePage />} />
          <Route path="/about" element={<LandingPage />} />
          <Route path="/methodology" element={<MethodologyPage />} />
          <Route path="/limitations" element={<LimitationsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <ProvenanceDrawer open={provenanceOpen} onClose={() => setProvenanceOpen(false)} />
    </div>
  );
}

import { Link, NavLink } from 'react-router-dom';
import { BookIcon, CloseIcon, FileIcon, GlobeIcon, HomeIcon, ListIcon, LogoIcon, ShieldIcon } from './Icons';

interface Props {
  eventId: string | null;
  queueCount: number | null;
  onOpenProvenance: () => void;
  /** Small screens only: whether the off-canvas menu is open. */
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ eventId, queueCount, onOpenProvenance, open, onClose }: Props) {
  const dash = eventId ? `/events/${eventId}` : '/';
  return (
    <aside id="app-menu" className={`sidebar${open ? ' open' : ''}`} aria-label="Application">
      <button type="button" className="side-close" onClick={onClose} aria-label="Close menu">
        <CloseIcon />
      </button>
      <Link to={dash} className="brand" aria-label="TriageSAR home">
        <LogoIcon />
        <span>TriageSAR</span>
      </Link>
      <p className="brand-tag">Surface motion to inspection action</p>
      <nav className="side-nav" aria-label="Main">
        <NavLink to={dash} end>
          <HomeIcon />
          Overview
        </NavLink>
        <NavLink to="/events" end>
          <GlobeIcon />
          Case studies
        </NavLink>
        {eventId ? (
          <NavLink to={`/events/${eventId}/queue`}>
            <ListIcon />
            Inspection queue
            {queueCount != null ? (
              <span className={`badge${queueCount === 0 ? ' zero' : ''}`}>
                <span className="sr-only">, </span>
                {queueCount}
                <span className="sr-only"> roads ranked</span>
              </span>
            ) : null}
          </NavLink>
        ) : null}
        <button
          type="button"
          onClick={() => {
            onClose();
            onOpenProvenance();
          }}
        >
          <FileIcon />
          Provenance
        </button>
        <NavLink to="/methodology">
          <BookIcon />
          Methodology
        </NavLink>
        <NavLink to="/limitations">
          <ShieldIcon />
          Limitations
        </NavLink>
      </nav>
      <div className="side-foot">
        <strong>Earth observation for safer infrastructure</strong>
        <NavLink to="/about" className="side-about">
          About TriageSAR
        </NavLink>
        <div className="bar" aria-hidden />
      </div>
    </aside>
  );
}

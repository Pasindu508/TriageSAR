// Small inline icons. Each is decorative (aria-hidden); meaning is always carried by adjacent text.
import type { ReactNode } from 'react';

function Icon({ children, size = 16 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable={false}
    >
      {children}
    </svg>
  );
}

export const CheckIcon = () => (
  <Icon>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Icon>
);
export const AlertIcon = () => (
  <Icon>
    <path d="M12 3.5l9 16H3z" />
    <path d="M12 10v4M12 17.2v.1" />
  </Icon>
);
export const SlashIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M6 18L18 6" />
  </Icon>
);
export const InfoIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5.5M12 7.7v.1" />
  </Icon>
);
export const HomeIcon = () => (
  <Icon>
    <path d="M4 11l8-7 8 7v8.5a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z" />
  </Icon>
);
export const GlobeIcon = () => (
  <Icon>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M3.5 12h17M12 3.5c2.5 2.6 3.6 5.4 3.6 8.5s-1.1 5.9-3.6 8.5c-2.5-2.6-3.6-5.4-3.6-8.5S9.5 6.1 12 3.5z" />
  </Icon>
);
export const ListIcon = () => (
  <Icon>
    <path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" />
  </Icon>
);
export const FileIcon = () => (
  <Icon>
    <path d="M14 3.5H6.5a1 1 0 0 0-1 1v15a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V8z" />
    <path d="M14 3.5V8h4.5M9 13h6M9 16.5h6" />
  </Icon>
);
export const BookIcon = () => (
  <Icon>
    <path d="M4.5 5.5A2 2 0 0 1 6.5 3.5h12v14h-12a2 2 0 0 0-2 2z" />
    <path d="M4.5 19.5a2 2 0 0 0 2 1h12v-3" />
  </Icon>
);
export const ShieldIcon = () => (
  <Icon>
    <path d="M12 3.5l7 3v5c0 4.4-3 7.9-7 9-4-1.1-7-4.6-7-9v-5z" />
    <path d="M12 9v4M12 15.7v.1" />
  </Icon>
);
export const LayersIcon = () => (
  <Icon>
    <path d="M12 4l8.5 4.5L12 13 3.5 8.5z" />
    <path d="M3.5 12.5L12 17l8.5-4.5M3.5 16.5L12 21l8.5-4.5" />
  </Icon>
);
export const PinIcon = () => (
  <Icon>
    <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z" />
    <circle cx="12" cy="10" r="2.3" />
  </Icon>
);
export const ChevronDown = () => (
  <Icon>
    <path d="M6 9l6 6 6-6" />
  </Icon>
);
export const ChevronRight = () => (
  <Icon>
    <path d="M9 6l6 6-6 6" />
  </Icon>
);
export const ArrowRight = () => (
  <Icon>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
);
export const CalendarIcon = () => (
  <Icon>
    <rect x="4" y="5" width="16" height="15.5" rx="2" />
    <path d="M4 10h16M8.5 3v4M15.5 3v4" />
  </Icon>
);
export const ActivityIcon = () => (
  <Icon>
    <path d="M3 12h4l2.5-6 4.5 12 2.5-6H21" />
  </Icon>
);
export const RoadIcon = () => (
  <Icon>
    <path d="M8 3.5L4.5 20.5M16 3.5l3.5 17M12 5v2.5M12 11v2.5M12 17v2.5" />
  </Icon>
);
export const EyeOffIcon = () => (
  <Icon>
    <path d="M3.5 3.5l17 17" />
    <path d="M10 6.2A9.7 9.7 0 0 1 12 6c5 0 8.5 6 8.5 6a16 16 0 0 1-2.7 3.4M6.6 7.7C4.6 9.3 3.5 12 3.5 12S7 18 12 18c1.3 0 2.5-.4 3.6-.9" />
  </Icon>
);
export const SatelliteIcon = () => (
  <Icon>
    <path d="M13 7l4 4-6 6-4-4z" />
    <path d="M15 5l2-2 4 4-2 2M9 19l-2 2-4-4 2-2M5 13a6 6 0 0 0 6 6" />
  </Icon>
);
export const WaveIcon = () => (
  <Icon>
    <path d="M3 9c3-3 6 3 9 0s6 3 9 0M3 15c3-3 6 3 9 0s6 3 9 0" />
  </Icon>
);
export const SignalIcon = () => (
  <Icon>
    <path d="M5 19v-3M10 19v-6M15 19v-9M20 19V7" />
  </Icon>
);
export const MenuIcon = () => (
  <Icon size={22}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </Icon>
);
export const CloseIcon = () => (
  <Icon size={22}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Icon>
);
export const LogoIcon = () => (
  <svg viewBox="0 0 40 40" aria-hidden focusable={false}>
    <path d="M4 33L17 8l6 11.5L27 13l9 20z" fill="#f97316" />
    <path d="M17 8l6 11.5-4.5 8.5L11 21z" fill="#fdba74" />
    <path d="M27 13l9 20h-8l-5-13.5z" fill="#ea580c" />
  </svg>
);

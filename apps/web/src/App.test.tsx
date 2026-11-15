import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fixtures, mockApi, REAL, renderApp, SYN } from './test/harness';

// WebGL is not available in jsdom: replace the map with a stub that exposes what it was given.
vi.mock('./features/MapView', () => ({
  default: (props: {
    label: string;
    items: unknown[];
    zones: unknown[];
    raster: unknown;
    selectedId: string | null;
    focusZoneId: string | null;
    layers: { motion: string; basemap: string };
  }) => (
    <div
      data-testid="map"
      aria-label={props.label}
      data-items={props.items.length}
      data-zones={props.zones.length}
      data-raster={props.raster ? 'yes' : 'no'}
      data-selected={props.selectedId ?? ''}
      data-zone={props.focusZoneId ?? ''}
      data-motion={props.layers.motion}
      data-basemap={props.layers.basemap}
    />
  ),
}));

const firstItem = fixtures.queue.items[0]!;
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

beforeEach(() => {
  mockApi();
});

describe('navigation', () => {
  it('opens the first ready case study as the overview and shows the sidebar', async () => {
    renderApp('/');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Infrastructure intelligence' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Case study' })).toHaveValue(SYN);
    const nav = screen.getByRole('navigation', { name: 'Main' });
    for (const name of ['Overview', 'Case studies', 'Methodology', 'Limitations']) {
      expect(within(nav).getByRole('link', { name })).toBeInTheDocument();
    }
    expect(await within(nav).findByRole('link', { name: /Inspection queue/ })).toHaveTextContent(
      String(fixtures.event.queue_length),
    );
  });

  it('switches case study with the selector', async () => {
    const user = userEvent.setup();
    renderApp(`/events/${SYN}`);
    const select = await screen.findByRole('combobox', { name: 'Case study' });
    expect(within(select).getAllByRole('option')).toHaveLength(fixtures.events.events.length);
    await user.selectOptions(select, REAL);
    expect(await screen.findByRole('heading', { name: 'No NISAR observations loaded' })).toBeInTheDocument();
  });

  it('lists every case study and labels unavailable analyses and synthetic data', async () => {
    renderApp('/events');
    expect(
      await screen.findByRole('heading', { level: 1, name: /Earthquakes observed by NISAR/ }),
    ).toBeInTheDocument();
    expect(await screen.findAllByText('ANALYSIS UNAVAILABLE')).toHaveLength(4);
    expect(screen.getByText('ANALYSIS READY')).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC TEST DATA ENABLED/)).toBeInTheDocument();
  });

  it('keeps the original headline and disclaimer on the About page', () => {
    renderApp('/about');
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1).toHaveTextContent('See where the ground moved.');
    expect(h1).toHaveTextContent('Know where to inspect first.');
    expect(screen.getByRole('link', { name: 'How the science works' })).toHaveAttribute(
      'href',
      '/methodology',
    );
    expect(screen.getByText('Detect structural damage or predict casualties')).toBeInTheDocument();
    expect(screen.getByText(/This is not a damage assessment/)).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'How TriageSAR works' }).children).toHaveLength(3);
  });

  it('lists the case studies and the open data sources on the About page', async () => {
    renderApp('/about');
    expect(await screen.findAllByText('ANALYSIS UNAVAILABLE')).toHaveLength(4);
    for (const name of ['NISAR L2 GUNW', 'Earthquake catalogue', 'Roads and places']) {
      expect(screen.getByText(name)).toBeInTheDocument();
    }
    expect(screen.getByRole('link', { name: /All case studies/ })).toHaveAttribute('href', '/events');
  });
});

describe('case study publication', () => {
  it('marks automatically added case studies without exposing ingestion diagnostics', async () => {
    const auto = {
      ...fixtures.events.events[0]!,
      id: 'japan-2026-07-28',
      title: 'Testtown, Japan earthquake',
      added_by: 'auto_ingest',
      added_on: '2026-11-15',
    };
    mockApi({
      '/api/v1/events': {
        body: {
          ...fixtures.events,
          events: [...fixtures.events.events, auto],
          auto_ingest: {
            ...fixtures.events.auto_ingest,
            enabled: true,
            last_checked_utc: '2026-11-15T06:00:00Z',
            added_total: 1,
            waiting: 2,
          },
        },
      },
    });
    renderApp('/events');
    expect(await screen.findByText(/ADDED AUTOMATICALLY · 15 Nov/)).toBeInTheDocument();
    expect(screen.queryByText(/Automatic updates|last checked|scripts\/auto_ingest/)).not.toBeInTheDocument();
  });

  it('shows case studies without server setup messages when ingestion has never run', async () => {
    renderApp('/events');
    expect(await screen.findByText('ANALYSIS READY')).toBeInTheDocument();
    expect(screen.queryByText(/Automatic checking|scripts\/auto_ingest/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Case studies published/)).not.toBeInTheDocument();
  });

  it('shows the publication time without deployment details on the release site', async () => {
    mockApi({
      '/api/v1/events': {
        body: {
          ...fixtures.events,
          snapshot: { generated_utc: '2026-11-15T05:12:00Z', commit: '0123456789abcdef' },
        },
      },
    });
    renderApp('/events');
    const published = await screen.findByText('15 Nov 2026, 05:12 UTC');
    expect(published).toHaveAttribute('datetime', '2026-11-15T05:12:00Z');
    expect(published.parentElement).toHaveTextContent('Case studies published');
    expect(
      screen.queryByText(/static snapshot|commit 0123456|next rebuild|on this server|scripts\/auto_ingest/),
    ).not.toBeInTheDocument();
  });
});

describe('dashboard', () => {
  it('shows real KPI values, the queue, the zones and the evidence for the top item', async () => {
    renderApp(`/events/${SYN}`);
    const kpis = await screen.findByRole('region', { name: 'Headline figures' });
    expect(within(kpis).getByText('Deformation zones')).toBeInTheDocument();
    expect(within(kpis).getByText(String(fixtures.event.zone_count))).toBeInTheDocument();
    expect(within(kpis).getByText(String(fixtures.event.queue_length))).toBeInTheDocument();
    expect(kpis).not.toHaveTextContent(/confidence|risk/i);

    const queue = screen.getByRole('list', { name: /Inspection queue/ });
    expect(within(queue).getAllByRole('listitem')).toHaveLength(fixtures.queue.items.length);
    const first = within(queue).getAllByRole('button')[0]!;
    expect(first).toHaveTextContent(firstItem.asset_name);
    expect(first).toHaveTextContent(`${firstItem.score.toFixed(1)} priority`);
    expect(first).toHaveAttribute('aria-pressed', 'true');
    const zones = screen.getByRole('list', { name: /Deformation zones/ });
    expect(within(zones).getAllByRole('listitem')).toHaveLength(fixtures.hotspots.features.length);

    const evidence = await screen.findByRole('region', { name: firstItem.asset_name });
    expect(within(evidence).getByText(/This is not a damage assessment/)).toBeInTheDocument();
    expect(await within(evidence).findByRole('img', { name: /Line-of-sight profile/ })).toBeInTheDocument();
    expect(within(evidence).getByText(`${firstItem.score.toFixed(1)} / 100 · rank 1`)).toBeInTheDocument();

    const map = screen.getByTestId('map');
    await waitFor(() => expect(map).toHaveAttribute('data-raster', 'yes'));
    expect(map).toHaveAttribute('data-selected', firstItem.id);
    expect(screen.getByText(/The map shows 2 deformation zones/)).toHaveClass('sr-only');
  });

  it('selecting a zone updates the evidence strip and focuses the map', async () => {
    const user = userEvent.setup();
    renderApp(`/events/${SYN}`);
    const zones = await screen.findByRole('list', { name: /Deformation zones/ });
    await user.click(within(zones).getAllByRole('button')[0]!);
    expect(await screen.findByRole('region', { name: 'Zone Z01' })).toBeInTheDocument();
    expect(screen.getByTestId('map')).toHaveAttribute('data-zone', 'Z01');
    expect(screen.getByText('Not ranked: no road within reach')).toBeInTheDocument();
  });

  it('opens the full evidence with the score audit, then closes it', async () => {
    const user = userEvent.setup();
    renderApp(`/events/${SYN}`);
    await user.click(await screen.findByRole('button', { name: /Review evidence/ }));
    const dialog = await screen.findByRole('dialog', { name: `Evidence: ${firstItem.asset_name}` });
    expect(within(dialog).getByRole('heading', { name: /Rank 1/ })).toHaveFocus();
    expect(within(dialog).getByText('90th percentile |LOS|')).toBeInTheDocument();
    await user.click(within(dialog).getByText('Why is this ranked #1?'));
    expect(
      within(within(dialog).getByRole('table', { name: /Score factors/ })).getAllByRole('row'),
    ).toHaveLength(8);
    await user.click(within(dialog).getByRole('button', { name: /Close evidence/ }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: /Evidence/ })).not.toBeInTheDocument());
  });

  it('says plainly when no road is ranked and selects the first zone instead', async () => {
    mockApi({
      [`/api/v1/events/${SYN}/inspection-queue`]: { body: { ...fixtures.queue, total: 0, items: [] } },
    });
    renderApp(`/events/${SYN}`);
    expect(await screen.findByText('No road is ranked.')).toBeInTheDocument();
    expect(screen.getByText(/not a statement that roads are undamaged/)).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: /Inspection queue/ })).not.toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Zone Z01' })).toBeInTheDocument();
  });

  it('shows "not computed" and no observations when the fixture is not built', async () => {
    renderApp(`/events/${REAL}`);
    expect(await screen.findByRole('heading', { name: 'No NISAR observations loaded' })).toBeInTheDocument();
    expect(
      screen.getByText(/python scripts\/build_demo_fixture.py --event venezuela-2026-06-24/),
    ).toBeInTheDocument();
    expect(screen.getByText(/not computed/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Headline figures' })).not.toBeInTheDocument();
    expect(screen.getByTestId('map')).toHaveAttribute('data-raster', 'no');
    expect(screen.getByRole('combobox', { name: 'Motion layer' })).toBeDisabled();
  });

  it('offers the whole queue and the zones as text tables without the map', async () => {
    renderApp(`/events/${SYN}/queue`);
    const [table, zoneTable] = await screen.findAllByRole('table');
    expect(within(table!).getAllByRole('row')).toHaveLength(fixtures.queue.items.length + 1);
    expect(within(zoneTable!).getAllByRole('row')).toHaveLength(fixtures.hotspots.features.length + 1);
    expect(within(zoneTable!).getByRole('columnheader', { name: 'Nearest road' })).toBeInTheDocument();
    expect(screen.queryByTestId('map')).not.toBeInTheDocument();
  });
});

describe('map controls', () => {
  it('switches the motion layer, basemap and extra layers with native controls', async () => {
    const user = userEvent.setup();
    renderApp(`/events/${SYN}`);
    const motion = await screen.findByRole('combobox', { name: 'Motion layer' });
    await waitFor(() => expect(motion).toBeEnabled());
    await user.selectOptions(motion, 'local');
    expect(screen.getByTestId('map')).toHaveAttribute('data-motion', 'local');
    expect(screen.getByText('Local motion (LOS)', { selector: 'summary' })).toBeInTheDocument();
    const basemap = screen.getByRole('group', { name: 'Basemap' });
    await user.click(within(basemap).getByRole('button', { name: 'Satellite' }));
    expect(within(basemap).getByRole('button', { name: 'Satellite' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByTestId('map')).toHaveAttribute('data-basemap', 'satellite');
    const quality = screen.getByRole('checkbox', { name: 'Show uncertainty (quality)' });
    expect(quality).toBeChecked();
    await user.click(quality);
    expect(quality).not.toBeChecked();
    expect(screen.getByText(/diagonal hatching marks EXCLUDED pixels/)).toHaveClass('sr-only');
  });
});

describe('small screens', () => {
  it('opens the menu from the top bar, closes it with Escape and on navigation', async () => {
    const user = userEvent.setup();
    const { container } = renderApp(`/events/${SYN}`);
    const open = await screen.findByRole('button', { name: 'Open menu' });
    expect(open).toHaveAttribute('aria-expanded', 'false');
    expect(open).toHaveAttribute('aria-controls', 'app-menu');
    await user.click(open);
    expect(open).toHaveAttribute('aria-expanded', 'true');
    expect(container.querySelector('#app-menu')).toHaveClass('open');
    await user.keyboard('{Escape}');
    expect(container.querySelector('#app-menu')).not.toHaveClass('open');
    await user.click(open);
    await user.click(
      within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', { name: 'Case studies' }),
    );
    expect(
      await screen.findByRole('heading', { level: 1, name: /Earthquakes observed by NISAR/ }),
    ).toBeInTheDocument();
    expect(container.querySelector('#app-menu')).not.toHaveClass('open');
  });

  it('reveals a long queue twenty items at a time', async () => {
    const user = userEvent.setup();
    const base = fixtures.queue.items[0]!;
    const many = Array.from({ length: 45 }, (_, i) => ({
      ...base,
      id: `${SYN}--z01-r${String(i + 1).padStart(3, '0')}`,
      rank: i + 1,
    }));
    mockApi({
      [`/api/v1/events/${SYN}/inspection-queue`]: { body: { ...fixtures.queue, total: 45, items: many } },
    });
    renderApp(`/events/${SYN}`);
    const queue = await screen.findByRole('list', { name: /Inspection queue/ });
    expect(within(queue).getAllByRole('listitem')).toHaveLength(20);
    await user.click(screen.getByRole('button', { name: /Show 20 more \(20 of 45 shown\)/ }));
    expect(within(queue).getAllByRole('listitem')).toHaveLength(40);
    await user.click(screen.getByRole('button', { name: /Show 5 more/ }));
    expect(within(queue).getAllByRole('listitem')).toHaveLength(45);
    expect(screen.queryByRole('button', { name: /Show \d+ more \(/ })).not.toBeInTheDocument();
  });
});

describe('error states', () => {
  it('explains when the API cannot be reached', async () => {
    mockApi({ '/api/v1/events': new TypeError('Failed to fetch') });
    renderApp(`/events/${SYN}`);
    expect(await screen.findByRole('alert', {}, { timeout: 5000 })).toHaveTextContent(/could not be reached/);
  });

  it('reports an unknown event', async () => {
    renderApp('/events/nope');
    expect(await screen.findByRole('alert')).toHaveTextContent(/no event called “nope”/);
  });

  it('surfaces a server-side analysis error with its message', async () => {
    mockApi({
      [`/api/v1/events/${SYN}`]: {
        status: 500,
        body: { error: { code: 'fixture_invalid', message: 'The fixture could not be read.', hint: null } },
      },
    });
    renderApp(`/events/${SYN}`);
    expect(
      await screen.findByText(/The fixture could not be read/, {}, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it('has a not-found page', () => {
    renderApp('/nothing/here');
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});

describe('methodology, limitations and provenance', () => {
  it('renders the methodology from the API', async () => {
    renderApp('/methodology');
    expect(await screen.findByText(fixtures.methodology.equation)).toBeInTheDocument();
    expect(screen.getByText(fixtures.methodology.score_formula)).toBeInTheDocument();
    expect(screen.getByText('TriageSAR does not detect structural damage.')).toBeInTheDocument();
  });

  it('renders the limitations page', async () => {
    renderApp('/limitations');
    expect(screen.getByRole('heading', { name: 'What this tool cannot tell you' })).toBeInTheDocument();
    expect(await screen.findByText(fixtures.methodology.limitations[0]!)).toBeInTheDocument();
  });

  it('opens the provenance drawer from the sidebar', async () => {
    const user = userEvent.setup();
    renderApp(`/events/${SYN}`);
    await user.click(
      within(screen.getByRole('navigation', { name: 'Main' })).getByRole('button', { name: 'Provenance' }),
    );
    const dialog = await screen.findByRole('dialog', { name: 'Provenance' });
    expect(
      await within(dialog).findByText('TEST_ONLY_SYNTHETIC_GUNW_NOT_A_NASA_PRODUCT'),
    ).toBeInTheDocument();
    expect(within(dialog).getByText('All layer files match their recorded SHA-256.')).toBeInTheDocument();
    expect(within(dialog).getAllByText(/Real-data fixture not built on this machine/).length).toBe(4);
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Provenance' })).not.toBeInTheDocument());
  });
});

describe('keyboard navigation', () => {
  it('starts with a skip link and reaches the queue and the full evidence by keyboard alone', async () => {
    const user = userEvent.setup();
    renderApp(`/events/${SYN}`);
    const zones = await screen.findByRole('list', { name: /Deformation zones/ });
    await user.tab();
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveFocus();
    const zoneButton = within(zones).getAllByRole('button')[0]!;
    for (let i = 0; i < 60 && document.activeElement !== zoneButton; i += 1) await user.tab();
    expect(zoneButton).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(zoneButton).toHaveAttribute('aria-pressed', 'true');
    const review = screen.getByRole('button', { name: /Review evidence/ });
    review.focus();
    await user.keyboard('{Enter}');
    const dialog = await screen.findByRole('dialog', { name: 'Evidence: zone Z01' });
    expect(within(dialog).getByRole('heading', { name: 'Zone Z01' })).toBeInTheDocument();
    expect(new RegExp(esc('Zone Z01')).test(dialog.textContent ?? '')).toBe(true);
  });
});

import { expect, test } from '@playwright/test';

const SYN = '/events/synthetic-test-event';
const REAL_EVENTS = ['venezuela-2026-06-24', 'kumamoto-2026-07-28', 'panama-2026-10-09', 'flores-2026-08-14'];

test('dashboard happy path on the synthetic event: queue -> evidence -> layers -> provenance', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto(SYN);
  await expect(page.getByRole('heading', { level: 1, name: 'Infrastructure intelligence' })).toBeVisible();
  await expect(page.getByText('SYNTHETIC TEST DATA ENABLED')).toBeVisible();
  await expect(page.getByRole('region', { name: 'Headline figures' })).toBeVisible();
  const queue = page.getByRole('list', { name: /Inspection queue/ });
  await expect(queue.getByRole('button').first()).toContainText(/TEST Road (Alpha|Charlie)/);
  await expect(page.getByRole('list', { name: /Deformation zones/ }).getByRole('listitem')).toHaveCount(2);
  await expect(page.locator('.map canvas')).toBeVisible();
  await expect(page.getByRole('button', { name: /^Rank 1:/ })).toBeVisible(); // keyboard-focusable map marker

  // Evidence strip with a real profile chart and thumbnail.
  await expect(page.getByRole('img', { name: /Line-of-sight profile/ })).toBeVisible();
  const thumb = page.locator('.ev-head img');
  await expect(thumb).toBeVisible();
  expect(await thumb.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);

  // A zone, then the full evidence drawer.
  await page
    .getByRole('list', { name: /Deformation zones/ })
    .getByRole('button')
    .first()
    .click();
  await expect(page.getByRole('region', { name: 'Zone Z01' })).toBeVisible();
  await page.getByRole('button', { name: /Review evidence/ }).click();
  await expect(page.getByRole('dialog', { name: 'Evidence: zone Z01' })).toBeVisible();
  await page.keyboard.press('Escape');

  // Layers.
  await page.getByRole('combobox', { name: 'Motion layer' }).selectOption('local');
  await page.getByRole('group', { name: 'Basemap' }).getByRole('button', { name: 'Plain' }).click();

  // Provenance from the sidebar.
  await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: 'Provenance' }).click();
  const drawer = page.getByRole('dialog', { name: 'Provenance' });
  await expect(drawer.getByText('All layer files match their recorded SHA-256.').first()).toBeVisible();
  await page.keyboard.press('Escape');

  // Text alternative and methodology.
  await page.getByRole('link', { name: /Full queue and zones as a text table/ }).click();
  await expect(page.getByRole('table').first()).toContainText('TEST Road Alpha');
  await page.getByRole('link', { name: 'Methodology' }).click();
  await expect(
    page.getByText('Inspection priority score = 100 x sum(weight x factor)', { exact: false }),
  ).toBeVisible();

  expect(errors).toEqual([]);
});

for (const id of REAL_EVENTS) {
  test(`real case study ${id} shows real observations or nothing, never placeholders`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(`/events/${id}`);
    const notBuilt = page.getByRole('heading', { name: 'No NISAR observations loaded' });
    const kpis = page.getByRole('region', { name: 'Headline figures' });
    await expect(notBuilt.or(kpis)).toBeVisible({ timeout: 30_000 });
    if (await notBuilt.isVisible()) {
      await expect(page.getByText(/not computed/)).toBeVisible();
      await expect(page.getByRole('list', { name: /Inspection queue/ })).toHaveCount(0);
    } else {
      await expect(page.getByText(/NASA-ISRO NISAR L2 GUNW observations/).first()).toBeVisible();
      await expect(page.locator('.map canvas')).toBeVisible();
      const queue = page.getByRole('list', { name: /Inspection queue/ });
      await expect(queue.or(page.getByText('No road is ranked.')).first()).toBeVisible();
      await page
        .getByRole('navigation', { name: 'Main' })
        .getByRole('button', { name: 'Provenance' })
        .click();
      await expect(
        page
          .getByRole('dialog')
          .getByText(/NISAR_L2_PR_GUNW_/)
          .first(),
      ).toBeVisible();
    }
    expect(errors).toEqual([]);
  });
}

for (const [label, width, height] of [
  ['phone', 375, 812],
  ['tablet', 768, 1024],
] as const) {
  test(`no horizontal scrolling and a working menu on a ${label}`, async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width, height }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    for (const path of [
      '/events',
      '/events/kumamoto-2026-07-28',
      '/events/kumamoto-2026-07-28/queue',
      '/methodology',
    ]) {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      const [scrollW, innerW] = await page.evaluate(() => [
        document.documentElement.scrollWidth,
        window.innerWidth,
      ]);
      expect(scrollW, `horizontal overflow on ${path}`).toBeLessThanOrEqual(innerW);
    }
    await page.goto('/events/kumamoto-2026-07-28');
    const menu = page.getByRole('button', { name: 'Open menu' });
    await expect(menu).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeHidden();
    await menu.click();
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
    await page.getByRole('link', { name: 'Methodology' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'How the science works' })).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeHidden();
    await expect(page.locator('.map canvas')).toHaveCount(0);
    await ctx.close();
  });
}

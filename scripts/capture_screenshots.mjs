// Capture README screenshots from a running app (default http://localhost:8000).
//   make start               # in one terminal
//   node scripts/capture_screenshots.mjs [baseUrl]
// Only real case studies are captured; nothing is drawn or edited afterwards.
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'apps/web/package.json'));
const { chromium } = require('@playwright/test');

const base = process.argv[2] ?? 'http://localhost:8000';
const out = path.join(root, 'docs/screenshots');
const browser = await chromium.launch();
// A tall viewport captures the whole dashboard without full-page stitching (which blanks WebGL canvases).
const page = await browser.newPage({ viewport: { width: 1600, height: 1480 }, deviceScaleFactor: 1 });
const shot = async (name, wait = 2500) => {
  await page.waitForTimeout(wait);
  await page.screenshot({ path: path.join(out, name) });
  console.log('wrote', name);
};
const dashboard = async (id) => {
  await page.goto(`${base}/events/${id}`);
  await page.getByRole('region', { name: 'Headline figures' }).waitFor({ timeout: 60000 });
  await page.getByRole('img', { name: /Line-of-sight profile/ }).waitFor({ timeout: 60000 });
};

await page.goto(base + '/about');
await page.getByRole('heading', { level: 1 }).waitFor();
await page.getByText('ANALYSIS READY').first().waitFor();
await shot('08-about.png', 800);

await page.goto(base + '/events');
await page.getByText('ANALYSIS READY').first().waitFor();
await shot('01-case-studies.png', 1000);

await dashboard('kumamoto-2026-07-28');
await shot('02-kumamoto-dashboard.png', 6000);

await page.getByRole('button', { name: /Review evidence/ }).click();
await page.getByRole('dialog').getByText('Why is this ranked #1?').click();
await shot('03-kumamoto-evidence.png', 1000);
await page.keyboard.press('Escape');

await dashboard('venezuela-2026-06-24');
await page.getByRole('combobox', { name: 'Motion layer' }).selectOption('local');
await shot('04-venezuela-no-road-ranked.png', 6000);

await dashboard('panama-2026-10-09');
await shot('05-panama-dashboard.png', 6000);

await page.getByRole('navigation', { name: 'Main' }).getByRole('button', { name: 'Provenance' }).click();
await page.getByRole('dialog').getByText(/NISAR_L2_PR_GUNW/).first().waitFor();
await shot('06-provenance.png', 800);

// Phone layout (375 × 812): top bar, collapsible legend, map controls rearranged.
const phone = await browser.newPage({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
await phone.goto(`${base}/events/kumamoto-2026-07-28`);
await phone.getByRole('region', { name: 'Headline figures' }).waitFor({ timeout: 60000 });
await phone.waitForTimeout(5000);
await phone.screenshot({ path: path.join(out, '07-phone-dashboard.png') });
console.log('wrote 07-phone-dashboard.png');

await browser.close();

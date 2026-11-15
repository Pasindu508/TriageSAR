import { defineConfig, devices } from '@playwright/test';

// The end-to-end test runs the real API + built web app against the TEST ONLY synthetic event,
// so it needs no network access and no NASA credentials.
const python = process.env.TRIAGESAR_PYTHON ?? '.venv/bin/python';
const port = 8010;

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: { baseURL: `http://127.0.0.1:${port}`, trace: 'retain-on-failure', viewport: { width: 1440, height: 900 } },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: {
    command: `bash -c "cd ../.. && ${python} scripts/make_synthetic_fixture.py && TRIAGESAR_INCLUDE_SYNTHETIC=1 ${python} -m uvicorn app.main:app --app-dir apps/api --port ${port}"`,
    url: `http://127.0.0.1:${port}/health`,
    reuseExistingServer: false,
    timeout: 90_000,
  },
});

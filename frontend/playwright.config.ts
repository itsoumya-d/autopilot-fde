import { defineConfig } from '@playwright/test';
import path from 'node:path';

// This suite starts a NEW synthetic checkout's own loopback services. It never
// reuses, exposes, tunnels to, or connects to another machine's running app.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  timeout: 30_000,
  globalTimeout: 10 * 60_000,
  expect: { timeout: 8_000 },
  outputDir: 'browser-test-results',
  reporter: [['list'], ['json', { outputFile: 'browser-report/results.json' }]],
  use: {
    browserName: 'chromium',
    baseURL: 'http://127.0.0.1:3000',
    viewport: { width: 1440, height: 1000 },
    colorScheme: 'dark',
    serviceWorkers: 'block',
    reducedMotion: 'reduce',
    launchOptions: { chromiumSandbox: true },
    screenshot: 'only-on-failure',
    trace: 'off',
    video: 'off',
    actionTimeout: 8_000,
  },
  webServer: [
    {
      command: 'python scripts/run_browser_test_backend.py',
      cwd: path.resolve(__dirname, '..'),
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: false,
      timeout: 60_000,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
      env: {
        AUTOPILOT_API_KEY: '', AUTOPILOT_LLM_ENHANCE: '0',
        AUTOPILOT_MCP_ALLOW_MUTATIONS: '0', SLACK_BOT_TOKEN: '',
        IMAP_HOST: '', IMAP_USER: '', IMAP_PASSWORD: '',
        LLM_API_KEY: '', OTEL_EXPORTER_OTLP_ENDPOINT: '',
      },
    },
    {
      command: 'npm run start -- --hostname 127.0.0.1',
      url: 'http://127.0.0.1:3000',
      reuseExistingServer: false,
      timeout: 60_000,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5_000 },
      env: { NEXT_TELEMETRY_DISABLED: '1', NEXT_PUBLIC_API_URL: 'http://127.0.0.1:8000/api' },
    },
  ],
});

import { defineConfig } from '@playwright/test';
import process from 'node:process';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  timeout: 180_000,
  expect: { timeout: 15_000 },
  retries: 0,
  workers: 4,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'visual/out/e2e-report' }]],
  outputDir: 'visual/out/e2e',
  use: {
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    baseURL: process.env.VISUAL_APP_URL ?? 'http://localhost:8080',
    channel: process.env.VISUAL_BROWSER,
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'on',
    reducedMotion: 'reduce',
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile', testMatch: '**/01-*.e2e.ts', use: { viewport: { width: 375, height: 812 } } },
  ],
});

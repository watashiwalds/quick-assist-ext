/**
 * E2E extension thật trên Chromium (N07, C05, R05, H05). Cần backend chạy sẵn với
 * ENABLE_DEV_LOGIN=true, AI_PROVIDER=mock + worker (xem e2e/README.md). Chạy: npm run test:e2e
 */
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1, // dùng chung 1 profile Chromium + 1 backend
  reporter: [['list'], ['html', { open: 'never' }], ['json', { outputFile: 'test-results/e2e.json' }]],
  use: { trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: { command: 'node e2e/serve.mjs', url: 'http://127.0.0.1:4173/article.html', reuseExistingServer: true },
})

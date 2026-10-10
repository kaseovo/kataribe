import { defineConfig, devices } from '@playwright/test'

// Checks a deployed service rather than a local one: no web servers to start,
// the real URL, and the team password the console sits behind. `make smoke`
// fills both in. The password is applied in the spec, not here: see there.
const url = process.env.KATARIBE_URL
if (!url || !process.env.KATARIBE_TEAM_PASSWORD) {
  throw new Error('Set KATARIBE_URL and KATARIBE_TEAM_PASSWORD — `make smoke` does both.')
}

export default defineConfig({
  testDir: './smoke',
  globalSetup: './e2e/generate-speech.ts',
  timeout: 240_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: url,
    permissions: ['microphone'],
  },
})

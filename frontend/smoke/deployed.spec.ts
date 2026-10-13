import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

import { expect, request as fresh, test, type BrowserContext } from '@playwright/test';

import { HEARD_EN, SAMPLE, SAMPLE_EN } from '../e2e/generate-speech';

/**
 * The deployed service, end to end: what the local suite cannot reach. That a
 * conversation lands in Cloud Storage and Firestore, and that it is read after
 * the upload has returned — on Cloud Run, which starves the CPU once a response
 * is sent unless the service is told not to.
 *
 * It makes people of its own and forgets them afterwards, recordings and all,
 * so the live data is left as it was found.
 */

const base = process.env.KATARIBE_URL!;
const authorization =
  'Basic ' + Buffer.from(`team:${process.env.KATARIBE_TEAM_PASSWORD}`).toString('base64');

const made: string[] = [];

test.afterAll(() => {
  for (const seniorId of made) {
    execFileSync('uv', ['run', 'python', 'forget.py', '--senior-id', seniorId], {
      cwd: '../backend',
      stdio: 'inherit',
    });
  }
});

/** The microphone replaced by a recording, played once: as soon as it opens,
 *  or, `onCue`, when the test calls `window.answer()`. */
async function speak(context: BrowserContext, sample: string, { onCue = false } = {}) {
  const wav = readFileSync(sample).toString('base64');
  await context.addInitScript(
    ({ b64, onCue }: { b64: string; onCue: boolean }) => {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      navigator.mediaDevices.getUserMedia = async () => {
        const ctx = new AudioContext();
        const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0) as ArrayBuffer);
        const destination = ctx.createMediaStreamDestination();
        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(destination);
        if (onCue) Object.assign(window, { answer: () => source.start() });
        else source.start();
        return destination.stream;
      };
    },
    { b64: wav, onCue },
  );
}

test('a stranger reaches the start page and a family page, and nothing else', async () => {
  const stranger = await fresh.newContext({ baseURL: base });

  expect((await stranger.get('/')).status()).toBe(200);
  expect((await stranger.get('/api/try')).status()).toBe(200);
  expect((await stranger.get('/console')).status()).toBe(401);
  expect((await stranger.get('/api/sessions')).status()).toBe(401);
  expect((await stranger.get('/api/seniors')).status()).toBe(401);
  expect((await stranger.post('/api/sessions', { data: {} })).status()).toBe(401);
  expect((await stranger.get('/family/someone')).status()).toBe(200);

  await stranger.dispose();
});

test('a conversation is kept in the cloud and read', async ({ page, context }) => {
  // The password goes on our own requests only. Playwright's httpCredentials
  // left headless Chrome's first load of this service hanging with no
  // response, and extraHTTPHeaders would hand the password to Google as well.
  await context.route(
    (url) => url.origin === new URL(base).origin,
    (route) => route.continue({ headers: { ...route.request().headers(), authorization } }),
  );
  const request = await fresh.newContext({ baseURL: base, extraHTTPHeaders: { authorization } });

  await speak(context, SAMPLE);

  const created = await request.post('/api/seniors', {
    data: { name: 'Smoke test', birthplace: '長野', family: [], language: 'ja' },
  });
  expect(created.ok()).toBe(true);
  const seniorId = (await created.json()).id as string;
  made.push(seniorId);

  await page.goto('/console');
  await page.locator('.interviewee select').selectOption(seniorId);

  const [started] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/api/sessions') && r.request().method() === 'POST'),
    page.getByRole('button', { name: /start conversation/i }).click(),
  ]);
  const sessionId = (await started.json()).session_id as string;

  await expect(page.locator('.transcript article.senior')).toContainText('長野', { timeout: 60_000 });
  await expect(page.locator('.transcript article.ai')).toBeVisible({ timeout: 90_000 });
  await page.getByRole('button', { name: /^stop$/i }).click();
  await expect(page.locator('.status')).toContainText('Saved', { timeout: 60_000 });

  // Read after the upload returned, which is the part Cloud Run can starve.
  const read = async () => (await (await request.get(`/api/sessions/${sessionId}`)).json());
  await expect
    .poll(async () => (await read()).status, { timeout: 120_000, intervals: [3_000] })
    .toBe('processed');

  const session = await read();
  expect(session.turns).toBeGreaterThan(1);
  expect(session.stories.length).toBeGreaterThan(0);
  expect(session.has_audio).toBe(true);

  // The recording comes back out of the bucket.
  const recording = await request.get(`/api/sessions/${sessionId}/audio`);
  expect(recording.ok()).toBe(true);
  const body = await recording.body();
  expect(body.subarray(0, 4).toString()).toBe('RIFF');
  expect(body.length).toBeGreaterThan(100_000);

  await request.dispose();
});

test('a judge tries it from the start page, with nothing to sign in to', async ({
  page,
  context,
}) => {
  // No password anywhere in this test: it is a stranger's whole path. They
  // answer the greeting rather than talk over it; see e2e/visitor.spec.ts.
  await speak(context, SAMPLE_EN, { onCue: true });

  await page.goto('/');
  await page.getByLabel('Your name').fill('Smoke test');
  await page.getByRole('button', { name: 'Start talking' }).click();
  await expect(page).toHaveURL(/\/talk\/[\w-]{22,}$/);
  made.push(new URL(page.url()).pathname.split('/').pop()!);

  await page.getByRole('button', { name: 'Talk', exact: true }).click();
  await expect(page.locator('.talk-caption')).not.toBeEmpty({ timeout: 60_000 });
  await expect(page.locator('.talk-phase')).toHaveText('Listening', { timeout: 60_000 });
  await page.evaluate(() => (window as unknown as { answer: () => void }).answer());
  await expect(page.locator('.talk-caption')).toContainText(HEARD_EN, { timeout: 90_000 });
  await page.getByRole('button', { name: 'Finish' }).click();
  await page.getByRole('button', { name: 'End now' }).click();

  // Written up after the upload returned, on Cloud Run, then asked on screen.
  await expect(page.getByText('Before you go: may your family read these?')).toBeVisible({
    timeout: 150_000,
  });
  await page.getByRole('button', { name: 'Let my family read them' }).click();
  await page.getByRole('link', { name: 'Open your family page' }).click();
  await expect(page.locator('.told blockquote').first()).toBeVisible();

  // Each quote plays their own voice, cut from the recording in the bucket,
  // and reachable without the password.
  const familyApi = new URL(page.url()).pathname.replace('/family/', '/api/family/');
  const view = await (await page.request.get(familyApi)).json();
  const audio: string = view.chapters[0].stories[0].quotes[0].audio;
  const clip = await page.request.get(audio);
  expect(clip.ok()).toBe(true);
  expect((await clip.body()).subarray(0, 4).toString()).toBe('RIFF');
});

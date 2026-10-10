import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';

import { SAMPLE } from './generate-speech';

/**
 * The senior's own screen, through a real conversation: one button to start,
 * the interviewer's words in large type, one button to finish, and what was
 * said kept on the server like any other session.
 */
test('a conversation from the senior’s own screen', async ({ page, context, request }) => {
  const wav = readFileSync(SAMPLE).toString('base64');
  await context.addInitScript((b64: string) => {
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    navigator.mediaDevices.getUserMedia = async () => {
      const ctx = new AudioContext();
      const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0) as ArrayBuffer);
      const destination = ctx.createMediaStreamDestination();
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(destination);
      source.start();
      return destination.stream;
    };
  }, wav);

  const created = await request.post('/api/seniors', {
    data: { name: '田中ハル', birthplace: '長野', family: [], language: 'ja' },
  });
  const seniorId = (await created.json()).id as string;

  await page.goto(`/talk/${seniorId}`);
  await expect(page.getByRole('heading')).toHaveText('田中ハルさん');
  // Nothing of the console reaches this screen.
  await expect(page.getByText('Pause before replying')).toHaveCount(0);

  const [started] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith(`/api/talk/${seniorId}/sessions`)),
    page.getByRole('button', { name: 'お話しする' }).click(),
  ]);
  const sessionId = (await started.json()).session_id as string;

  // The interviewer speaks first, and its words appear in large type.
  await expect(page.locator('.talk-phase')).toBeVisible();
  await expect(page.locator('.talk-caption')).toContainText(/[぀-ヿ一-鿿]/, { timeout: 60_000 });

  await page.getByRole('button', { name: 'おわる' }).click();
  await expect(page.locator('.talk-thanks')).toHaveText('ありがとうございました。', {
    timeout: 60_000,
  });
  await expect(page.locator('.talk-unsaved')).toHaveCount(0);

  const session = await (await request.get(`/api/sessions/${sessionId}`)).json();
  expect(session.turns).toBeGreaterThan(0);
  expect(session.has_audio).toBe(true);
});

test('a screen for no one says so, in both languages', async ({ page }) => {
  await page.goto('/talk/nobody');

  await expect(page.getByText('このページは開けません。')).toBeVisible();
  await expect(page.getByText('This page is not available.')).toBeVisible();
});

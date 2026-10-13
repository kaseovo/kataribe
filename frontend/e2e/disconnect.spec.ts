import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';

import { SAMPLE } from './generate-speech';

/**
 * A connection that drops mid-conversation must not cost what was said. Until
 * the upload succeeds the browser holds the only copy, and a lost connection
 * used to leave it there — with the microphone still listening to the room.
 *
 * The socket is proxied to the real service, so the conversation is genuine
 * until the moment it is cut, and then closed with 1011 the way a keepalive
 * timeout arrives.
 */
test('keeps the conversation when the connection drops', async ({ page, context }) => {
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
      // Kept where the test can see whether it was let go.
      (window as unknown as { mic: MediaStream }).mic = destination.stream;
      return destination.stream;
    };
  }, wav);

  let cut: (() => Promise<void>) | undefined;
  await page.routeWebSocket(/generativelanguage\.googleapis\.com/, (ws) => {
    const server = ws.connectToServer();
    cut = async () => {
      await ws.close({ code: 1011, reason: 'connection dropped by the test' });
      await server.close();
    };
  });

  await page.goto('/console');
  await page.getByRole('button', { name: /start conversation/i }).click();
  await expect(page.locator('.transcript article.senior')).toContainText('長野', {
    timeout: 60_000,
  });

  await cut!();

  const status = page.locator('.status');
  await expect(status).toContainText('Saved', { timeout: 30_000 });
  await expect(status).toContainText('Connection lost (Closed 1011');
  await expect(page.getByRole('link', { name: /download recording/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /start conversation/i })).toBeEnabled();

  // Not left listening to the room.
  const released = await page.evaluate(() =>
    (window as unknown as { mic: MediaStream }).mic
      .getTracks()
      .every((track) => track.readyState === 'ended'),
  );
  expect(released).toBe(true);

  // And what was said is on the server, not only in this tab.
  await page.getByRole('button', { name: /past sessions/i }).click();
  const latest = page.locator('.session').first();
  await expect(latest.locator('.facts')).toContainText(/[1-9]\d* turns/);
  await latest.locator('.summary').click();
  await expect(latest.locator('.detail audio')).toBeVisible();
  await expect(latest.locator('.line.senior')).toContainText('長野');
});

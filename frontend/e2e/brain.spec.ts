import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';

import { addPerson } from './people';
import { SAMPLE } from './generate-speech';

test('records a session against a person and extracts a story from it', async ({
  page,
  context,
}) => {
  test.setTimeout(180_000);

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

  await page.goto('/console');

  await addPerson(page, {
    name: '田中ハル',
    reading: 'たなかはる',
    birthYear: 1947,
    birthplace: '長野',
  });

  await page.getByRole('button', { name: /start conversation/i }).click();
  await expect(page.locator('.transcript article.senior')).toContainText('長野', {
    timeout: 60_000,
  });
  // Not asserting that the greeting uses her name: whether it does is the
  // model's choice from one run to the next. That the name reaches the prompt
  // at all is covered by test_context_gives_the_name_so_it_is_not_transcribed.
  await expect(page.locator('.transcript article.ai')).toBeVisible({ timeout: 90_000 });

  await page.getByRole('button', { name: /^stop$/i }).click();
  await expect(page.locator('.status')).toContainText(/saved|finished/i, { timeout: 30_000 });

  await page.getByRole('button', { name: /past sessions/i }).click();
  const first = page.locator('.session').first();
  await first.locator('.summary').click();

  // Extraction runs behind the upload, so the story arrives after the page does.
  await expect(first.locator('.story')).toBeVisible({ timeout: 90_000 });
  await expect(first.locator('.story blockquote').first()).toContainText('長野');
  // A quote must point back at the turn it came from.
  await expect(first.locator('.line.quoted')).toHaveCount(1);
});

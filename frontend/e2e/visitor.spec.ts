import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';

import { SAMPLE_EN } from './generate-speech';

/**
 * A judge trying it from the start page, the path the live URL exists for
 * during judging: a persona of their own, a short conversation, and their story
 * on their own family page.
 *
 * It ends with End now straight after Finish, before the interviewer can ask
 * about sharing, or before anyone could reply, so the end screen has to ask
 * instead. Without that, a judge who ends early sees an empty page.
 */
test('a visitor goes from the start page to their own family page', async ({ page, context }) => {
  test.setTimeout(240_000);

  const wav = readFileSync(SAMPLE_EN).toString('base64');
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

  await page.goto('/');
  await page.getByLabel('Your name').fill('Alex');
  // The family question is filled in already, so pressing Start is enough.
  await expect(page.getByLabel('Their question')).not.toBeEmpty();
  await page.getByRole('button', { name: 'Start talking' }).click();

  // A persona of their own, behind an id nobody could guess.
  await expect(page).toHaveURL(/\/talk\/[\w-]{22,}$/);
  await expect(page.getByRole('heading')).toHaveText('Alex');

  await page.getByRole('button', { name: 'Talk', exact: true }).click();
  await expect(page.locator('.talk-caption')).not.toBeEmpty({ timeout: 60_000 });
  // Heard: the interviewer asks after something they said.
  await expect(page.locator('.talk-caption')).toContainText(
    /Brittany|grandfather|boat|fish|sea|town|summer|dawn/i,
    { timeout: 90_000 },
  );

  // Finish asks the interviewer to wrap up rather than hanging up.
  await page.getByRole('button', { name: 'Finish' }).click();
  await expect(page.getByRole('button', { name: 'End now' })).toBeVisible();
  await page.getByRole('button', { name: 'End now' }).click();

  await expect(page.locator('.talk-thanks')).toHaveText('Thank you.', { timeout: 60_000 });
  await expect(page.getByText('Writing up your story…')).toBeVisible();

  // No answer about sharing aloud, so asked here, naming the story.
  await expect(page.getByText('Before you go: may your family read these?')).toBeVisible({
    timeout: 120_000,
  });
  await expect(page.locator('.talk-titles li').first()).not.toBeEmpty();
  await page.getByRole('button', { name: 'Let my family read them' }).click();
  await expect(page.getByText(/now on your family page/)).toBeVisible();

  await page.getByRole('link', { name: 'Open your family page' }).click();
  await expect(page.locator('.told').first()).toBeVisible();
  await expect(page.locator('.told blockquote').first()).toContainText(
    /Brittany|grandfather|boat|fishing|sea/i,
  );
  await expect(page.getByRole('link', { name: 'Talk again' })).toBeVisible();
});

import { readFileSync } from 'node:fs';

import { expect, test, type BrowserContext, type Page } from '@playwright/test';

import { HEARD_EN, SAMPLE_EN } from './generate-speech';

/**
 * A judge trying it from the start page, the path the live URL exists for
 * during judging: a persona of their own, a short conversation, and their story
 * on their own family page.
 *
 * Both end before anyone could answer the interviewer's question about sharing
 * aloud: one with the buttons shown while it closes, one by ending it and
 * choosing afterwards. Without either, a judge who ends early sees an empty page.
 */

/** As far as the interviewer asking after what they said, then Finish. */
async function talkThenFinish(page: Page, context: BrowserContext) {
  // The microphone is replaced by a recording that starts when the test says,
  // since a judge listens to the greeting before answering it. Played the
  // moment the microphone opened, it could start with the greeting itself and
  // be lost, leaving the interviewer waiting for an answer that had been given.
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
      Object.assign(window, { answer: () => source.start() });
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
  await expect(page.locator('.talk-phase')).toHaveText('Listening', { timeout: 60_000 });
  await page.evaluate(() => (window as unknown as { answer: () => void }).answer());
  // Heard: the interviewer asks after something they said.
  await expect(page.locator('.talk-caption')).toContainText(HEARD_EN, { timeout: 90_000 });

  // Finish asks the interviewer to wrap up rather than hanging up, and the
  // question it asks aloud is on screen too.
  await page.getByRole('button', { name: 'Finish' }).click();
  await expect(page.getByText('May your family read today’s story?')).toBeVisible();
}

async function storyOnTheirFamilyPage(page: Page) {
  await page.getByRole('link', { name: 'Open your family page' }).click();
  await expect(page.locator('.told').first()).toBeVisible();
  await expect(page.locator('.told blockquote').first()).toContainText(
    /Brittany|grandfather|boat|fishing|sea/i,
  );
  await expect(page.getByRole('link', { name: 'Talk again' })).toBeVisible();
}

test('a visitor shares with a button while it closes', async ({ page, context }) => {
  test.setTimeout(240_000);
  await talkThenFinish(page, context);

  await page.getByRole('button', { name: 'Share with my family' }).click();

  await expect(page.locator('.talk-thanks')).toHaveText('Thank you.', { timeout: 60_000 });
  // Chosen already, so not asked again once it is written up.
  await expect(page.getByText(/now on your family page/)).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText('Before you go: may your family read these?')).toHaveCount(0);
  await storyOnTheirFamilyPage(page);
});

test('a visitor who ends without choosing is asked afterwards', async ({ page, context }) => {
  test.setTimeout(240_000);
  await talkThenFinish(page, context);

  await page.getByRole('button', { name: 'End now, choose later' }).click();

  await expect(page.locator('.talk-thanks')).toHaveText('Thank you.', { timeout: 60_000 });
  await expect(page.getByText('Writing up your story…')).toBeVisible();
  // No answer about sharing, so asked here, naming the story.
  await expect(page.getByText('Before you go: may your family read these?')).toBeVisible({
    timeout: 120_000,
  });
  await expect(page.locator('.talk-titles li').first()).not.toBeEmpty();
  await page.getByRole('button', { name: 'Let my family read them' }).click();
  await expect(page.getByText(/now on your family page/)).toBeVisible();
  await storyOnTheirFamilyPage(page);
});

import { execFileSync } from 'node:child_process';

import { expect, test, type APIRequestContext } from '@playwright/test';

/**
 * The family page shows only what the person agreed to share.
 *
 * Tested from the page rather than from the API. Whatever the filtering does
 * upstream, what matters is that nothing private appears on the screen a
 * relative actually opens.
 */
async function seed(
  request: APIRequestContext,
  visibility: 'family' | 'private',
  title: string,
  question?: string,
) {
  const senior = await (
    await request.post('/api/seniors', {
      data: {
        name: '田中ハル',
        name_reading: 'たなかはる',
        birth_year: 1947,
        birthplace: '長野',
        family: [],
        language: 'ja',
      },
    })
  ).json();

  execFileSync(
    'uv',
    [
      'run',
      'python',
      'seed_story.py',
      '--senior-id',
      senior.id,
      '--title',
      title,
      '--summary',
      '父が村で小さな織物の工場をやっていた。',
      '--quote',
      '父は村で小さな織物の工場をやっておりました。',
      '--visibility',
      visibility,
      // Recorded as asked, with this story as the answer, as processing would.
      ...(question ? ['--asked-by', '孫のゆか', '--question', question] : []),
    ],
    { cwd: '../backend' },
  );
  return senior.id as string;
}

test('a shared story reaches the family, with her voice behind it', async ({ page, request }) => {
  const seniorId = await seed(request, 'family', '織物工場のこと');

  await page.goto(`/family/${seniorId}`);

  await expect(page.locator('h1')).toContainText('田中ハル');
  await expect(page.locator('.chapter h2')).toContainText('子供時代');
  await expect(page.locator('.told h3')).toContainText('織物工場のこと');
  await expect(page.locator('.told blockquote')).toContainText('織物の工場');
  await expect(page.locator('.withheld')).toHaveCount(0);

  // Her own voice one tap away is the whole claim — her voice saying this,
  // not the session it came from.
  const [clip] = await Promise.all([
    page.waitForResponse(/\/stories\/[\w-]+\/quotes\/0\/audio$/),
    page.locator('.listen').click(),
  ]);
  expect(clip.status()).toBe(200);
  expect(clip.headers()['content-type']).toBe('audio/wav');
  // The whole recording also holds whatever she kept private. Nothing on the
  // page may lead to it.
  expect(await page.content()).not.toContain('/api/sessions/');
});

test('a story she did not agree to share never appears', async ({ page, request }) => {
  const seniorId = await seed(request, 'private', '話したくないこと');

  await page.goto(`/family/${seniorId}`);

  await expect(page.locator('.withheld')).toContainText('kept private');
  await expect(page.locator('.told')).toHaveCount(0);
  // Not the title, not the summary, not a word of it.
  await expect(page.locator('body')).not.toContainText('話したくないこと');
  await expect(page.locator('body')).not.toContainText('織物');
});

test('a relative can send a question, and sees it waiting', async ({ page, request }) => {
  const seniorId = await seed(request, 'family', '織物工場のこと');

  await page.goto(`/family/${seniorId}`);
  await page.getByLabel('Who is asking').fill('孫のゆか');
  await page.getByLabel('Your question').fill('結婚式のときのお着物は、どんなものでしたか?');
  await page.getByRole('button', { name: 'Send question' }).click();

  const question = page.locator('.question');
  await expect(question).toContainText('孫のゆか');
  await expect(question).toContainText('お着物');
  await expect(question).toContainText('Waiting to be asked');

  // Kept, not just shown.
  await page.reload();
  await expect(page.locator('.question')).toContainText('お着物');
});

test('her answer comes back to the one who asked', async ({ page, request }) => {
  const seniorId = await seed(request, 'family', '織物工場のこと', 'お父さんの工場のことを教えて');

  await page.goto(`/family/${seniorId}`);

  const question = page.locator('.question');
  await expect(question).toContainText('Answered in');
  await expect(question.getByRole('link', { name: '織物工場のこと' })).toBeVisible();
  // And on the story itself, who it answered.
  await expect(page.locator('.told .asked-for')).toContainText('孫のゆか asked');
});

test('an answer she kept private stays private, even from the one who asked', async ({
  page,
  request,
}) => {
  const seniorId = await seed(request, 'private', '話したくないこと', '子どものころのことを教えて');

  await page.goto(`/family/${seniorId}`);

  // They learn it was asked, and nothing about whether or what she answered.
  await expect(page.locator('.question')).toContainText('No reply has been shared');
  await expect(page.locator('.question a')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText('話したくないこと');
  await expect(page.locator('body')).not.toContainText('織物');
});

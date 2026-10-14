import { execFileSync } from 'node:child_process';

import { expect, test, type APIRequestContext } from '@playwright/test';

/**
 * The family page shows only what the person agreed to share.
 *
 * Tested from the page rather than from the API. Whatever the filtering does
 * upstream, what matters is that nothing private appears on the screen a
 * relative actually opens.
 */
// A Japanese family's browser, so the page opens on the words as told. The
// first test switches to English, as a judge's browser would open it.
test.use({ locale: 'ja-JP' });

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
  // A Japanese page throughout, its own words included.
  await expect(page.locator('.chapter h2')).toContainText('第1章');
  await expect(page.locator('.chapter h2')).toContainText('子供時代');
  await expect(page.locator('.told h3')).toContainText('織物工場のこと');
  // Read as text; the quotes, with her voice, are a press away.
  await expect(page.locator('.told blockquote')).toHaveCount(0);
  await page.getByRole('button', { name: /ご本人の言葉/ }).click();
  await expect(page.locator('.told blockquote')).toContainText('織物の工場');
  await expect(page.locator('.told blockquote .translation')).toHaveCount(0);

  // In English, once it is translated: the story in English, and the quote
  // still in her words, with the English beneath.
  await page.getByRole('button', { name: 'English' }).click({ timeout: 60_000 });
  await expect(page.locator('.told h3')).toContainText(/factory|mill/i);
  await expect(page.locator('.chapter h2')).toContainText('Chapter 1');
  await expect(page.locator('.chapter h2')).toContainText('Childhood');
  await expect(page.locator('.told blockquote')).toContainText('織物の工場');
  await expect(page.locator('.told blockquote .translation')).toContainText(/factory|mill/i);

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

  await expect(page.locator('.told')).toHaveCount(0);
  // Not even that it exists: the page reads as if nothing had been told.
  await expect(page.locator('.empty')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('private');
  // Not the title, not the summary, not a word of it.
  await expect(page.locator('body')).not.toContainText('話したくないこと');
  await expect(page.locator('body')).not.toContainText('織物');
});

test('a relative can send a question, and sees it waiting', async ({ page, request }) => {
  const seniorId = await seed(request, 'family', '織物工場のこと');

  await page.goto(`/family/${seniorId}`);
  // Asking is a press away from anywhere in the book, and opens the
  // questions' tab.
  await page.getByRole('button', { name: /さんに質問する/ }).click();
  await expect(page.getByRole('tab', { name: /ご家族からのご質問/ })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  // Who they are, by group and then exactly, as the interviewer will say it:
  // 孫のゆか.
  await page
    .getByRole('group', { name: /さんとのご関係/ })
    .getByRole('button', { name: '孫', exact: true })
    .click();
  await page.getByRole('group', { name: '孫' }).getByRole('button', { name: '孫', exact: true }).click();
  await page.getByLabel('お名前').fill('ゆか');
  await page.getByLabel('何を聞いてみたいですか？').fill('結婚式のときのお着物は、どんなものでしたか?');
  await expect(page.locator('.preview')).toContainText('孫のゆかさんが');
  await page.getByRole('button', { name: '質問を送る' }).click();

  const question = page.locator('.question');
  await expect(question).toContainText('孫のゆか');
  await expect(question).toContainText('お着物');
  await expect(question).toContainText('まだお尋ねしていません');

  // Kept, not just shown.
  await page.reload();
  await page.getByRole('button', { name: /さんに質問する/ }).click();
  await expect(page.locator('.question')).toContainText('お着物');
});

test('her answer comes back to the one who asked', async ({ page, request }) => {
  const seniorId = await seed(request, 'family', '織物工場のこと', 'お父さんの工場のことを教えて');

  await page.goto(`/family/${seniorId}`);
  await page.getByRole('button', { name: /さんに質問する/ }).click();

  const question = page.locator('.question');
  await expect(question.locator('.stamp')).toHaveText('お答えあり');
  // The answer leads back to the story, which says who it answered.
  await question.getByRole('link', { name: /織物工場のこと/ }).click();
  await expect(page.locator('.told .asked-for')).toContainText('孫のゆかさんからのご質問');
});

test('an answer she kept private stays private, even from the one who asked', async ({
  page,
  request,
}) => {
  const seniorId = await seed(request, 'private', '話したくないこと', '子どものころのことを教えて');

  await page.goto(`/family/${seniorId}`);
  await page.getByRole('button', { name: /さんに質問する/ }).click();

  // They learn it was asked, and nothing about whether or what she answered.
  await expect(page.locator('.question')).toContainText('共有されたお答えは、まだありません');
  await expect(page.locator('.question a')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText('話したくないこと');
  await expect(page.locator('body')).not.toContainText('織物');
});

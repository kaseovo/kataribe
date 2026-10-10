import { afterEach, describe, expect, it, vi } from 'vitest';

import { keep, partsOf } from './upload';

describe('partsOf', () => {
  it('covers every byte once, in parts no bigger than asked', () => {
    expect(partsOf(10, 4)).toEqual([
      [0, 4],
      [4, 8],
      [8, 10],
    ]);
    expect(partsOf(8, 4)).toEqual([
      [0, 4],
      [4, 8],
    ]);
  });
});

describe('keep', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('sends the recording in parts, then the transcript with how many', async () => {
    const sent: { url: string; method: string; body: string }[] = [];
    vi.stubGlobal('fetch', async (url: string, init: RequestInit) => {
      const body =
        init.body instanceof Blob ? await init.body.text() : String((init.body as FormData).get('audio_parts'));
      sent.push({ url, method: init.method ?? 'GET', body });
      return new Response(null, { status: 204 });
    });

    const outcome = await keep('s1', new Blob(['RIFFfake!!']), [], 12, 'microphone', { part: 4 });

    expect(outcome).toEqual({ saved: true, message: 'Saved' });
    expect(sent).toEqual([
      { url: '/api/sessions/s1/recording/parts/0', method: 'PUT', body: 'RIFF' },
      { url: '/api/sessions/s1/recording/parts/1', method: 'PUT', body: 'fake' },
      { url: '/api/sessions/s1/recording/parts/2', method: 'PUT', body: '!!' },
      { url: '/api/sessions/s1/recording', method: 'POST', body: '3' },
    ]);
  });

  it('tries a dropped part again rather than losing the recording', async () => {
    vi.useFakeTimers();
    let calls = 0;
    vi.stubGlobal('fetch', async () => {
      calls++;
      if (calls === 1) throw new TypeError('Failed to fetch');
      return new Response(null, { status: 204 });
    });

    const outcome = keep('s1', new Blob(['RIFF']), [], 1, 'microphone', { part: 4 });
    await vi.runAllTimersAsync();

    expect((await outcome).saved).toBe(true);
    expect(calls).toBe(3);
    vi.useRealTimers();
  });

  it('says so when the server refuses, without trying in vain', async () => {
    let calls = 0;
    vi.stubGlobal('fetch', async () => {
      calls++;
      return new Response('Session s1 is already kept', { status: 409 });
    });

    const outcome = await keep('s1', new Blob(['RIFF']), [], 1, 'microphone', { part: 4 });

    expect(outcome.saved).toBe(false);
    expect(outcome.message).toMatch(/^Saved locally only — upload failed \(409/);
    expect(calls).toBe(1);
  });
});

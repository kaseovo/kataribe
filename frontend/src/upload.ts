/** Cloud Run refuses a request over 32 MiB, and ten minutes of conversation is
 *  close to 60 MB, so a recording goes up in parts well under that and the
 *  server joins them when the transcript follows. */
export const PART_BYTES = 16 * 1024 * 1024;

/** Byte ranges covering `size` in parts of at most `part`. */
export function partsOf(size: number, part = PART_BYTES): [number, number][] {
  const ranges: [number, number][] = [];
  for (let start = 0; start < size; start += part) {
    ranges.push([start, Math.min(size, start + part)]);
  }
  return ranges;
}

export interface Kept {
  saved: boolean;
  /** What to tell whoever is at the console. */
  message: string;
}

/** Uploading must not lose the recording: the browser copy is the only one
 *  until this succeeds, so a failure is reported rather than swallowed.
 *  `api` is where the session lives: the console's `/api`, or a senior's own
 *  screen, `/api/talk/{id}`. */
export async function keep(
  sessionId: string,
  wav: Blob,
  transcript: unknown[],
  seconds: number,
  inputLabel: string,
  { api = '/api', part = PART_BYTES }: { api?: string; part?: number } = {},
): Promise<Kept> {
  try {
    const parts = partsOf(wav.size, part);
    for (const [index, [start, end]] of parts.entries()) {
      await send(`${api}/sessions/${sessionId}/recording/parts/${index}`, {
        method: 'PUT',
        body: wav.slice(start, end),
      });
    }

    const form = new FormData();
    form.append('transcript', JSON.stringify(transcript));
    form.append('duration_seconds', String(seconds));
    form.append('input_label', inputLabel);
    form.append('audio_parts', String(parts.length));
    await send(`${api}/sessions/${sessionId}/recording`, { method: 'POST', body: form });
    return { saved: true, message: 'Saved' };
  } catch (error) {
    return {
      saved: false,
      message:
        `Saved locally only — upload failed (${error instanceof Error ? error.message : error}). ` +
        'Download the recording before starting another session.',
    };
  }
}

/** A request that dropped is tried again, twice, before the upload gives up:
 *  a long session should not be lost to one bad moment on the network. One
 *  the server refused is not, since sending it again changes nothing. */
async function send(url: string, init: RequestInit, attempts = 3): Promise<void> {
  let failure: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    if (attempt > 0) await new Promise((resolve) => setTimeout(resolve, 1000 * attempt));
    let response: Response;
    try {
      response = await fetch(url, init);
    } catch (error) {
      failure = error;
      continue;
    }
    if (response.ok) return;
    failure = new Error(`${response.status} ${await response.text()}`);
    if (response.status < 500) break;
  }
  throw failure;
}

import { describe, expect, it } from 'vitest';

import { CAPTURE_RATE } from './capture';
import { PLAYBACK_RATE } from './playback';
import { buildConversationWav } from './wav';

async function channels(wav: Blob): Promise<{ left: Int16Array; right: Int16Array }> {
  const view = new DataView(await wav.arrayBuffer());
  const frames = (view.byteLength - 44) / 4;
  const left = new Int16Array(frames);
  const right = new Int16Array(frames);
  for (let i = 0; i < frames; i++) {
    left[i] = view.getInt16(44 + i * 4, true);
    right[i] = view.getInt16(46 + i * 4, true);
  }
  return { left, right };
}

const firstSound = (samples: Int16Array) => samples.findIndex((s) => s !== 0) / PLAYBACK_RATE;

describe('buildConversationWav', () => {
  it('puts each side where it happened on the shared timeline', async () => {
    // The interviewer spoke at 0.25 s. The microphone only opened at 1.5 s,
    // once the connection was up, and then heard one second of speech.
    const mic = new Int16Array(CAPTURE_RATE).fill(1000);
    const ai = [{ offsetSec: 0.25, pcm: new Int16Array(PLAYBACK_RATE / 2).fill(2000) }];

    const { left, right } = await channels(buildConversationWav(mic, ai, 1.5));

    expect(firstSound(right)).toBeCloseTo(0.25, 2);
    expect(firstSound(left)).toBeCloseTo(1.5, 2);
    expect(left.length / PLAYBACK_RATE).toBeCloseTo(2.5, 2);
  });
});

import { GoogleGenAI, type LiveServerMessage, type Session } from '@google/genai';

import { CAPTURE_RATE, microphone, recording, startCapture, type Capture } from './audio/capture';
import { Playback } from './audio/playback';
import { buildConversationWav } from './audio/wav';

export type Speaker = 'senior' | 'ai';

export interface Tuning {
  voice: string;
  silenceDurationMs: number;
  endOfSpeechSensitivity: 'LOW' | 'HIGH';
}

/** Nothing reaches the screen while someone is still talking — transcripts only
 *  arrive once the model accepts the turn has ended, which the patience setting
 *  delays on purpose. Without a live level and a phase, a working session is
 *  indistinguishable from a broken one for several seconds. */
export type Phase = 'listening' | 'thinking' | 'speaking';

export interface InterviewCallbacks {
  onTranscript: (speaker: Speaker, delta: string) => void;
  onStatus: (status: string) => void;
  onLevel: (level: number) => void;
  onPhase: (phase: Phase) => void;
  /** The connection ended without stop() being called. What was said is kept
   *  regardless: `saved` settles once the upload has been tried, with the
   *  recording to offer for download. */
  onClosed: (reason: string, saved: Promise<Blob>) => void;
}

export interface Interview {
  sessionId: string;
  stop: () => Promise<Blob>;
}

interface SessionResponse {
  session_id: string;
  token: string;
  model: string;
  resuming: boolean;
  opening: string;
}

export async function startInterview(
  tuning: Tuning,
  callbacks: InterviewCallbacks,
  replay?: File,
  seniorId?: string | null,
): Promise<Interview> {
  callbacks.onStatus('Requesting a session token');

  const response = await fetch('/api/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      senior_id: seniorId ?? null,
      voice: tuning.voice,
      silence_duration_ms: tuning.silenceDurationMs,
      end_of_speech_sensitivity: tuning.endOfSpeechSensitivity,
    }),
  });
  if (!response.ok) {
    throw new Error(`Could not start a session (${response.status}): ${await response.text()}`);
  }
  const {
    session_id: sessionId,
    token,
    model,
    resuming,
    opening,
  }: SessionResponse = await response.json();

  const playback = new Playback();
  const ai = new GoogleGenAI({ apiKey: token, httpOptions: { apiVersion: 'v1alpha' } });

  callbacks.onStatus('Connecting to Gemini Live');

  let session: Session | undefined;
  let capture: Capture | undefined;
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  let playedAnything = false;
  // Set once the session is being wound down. A close after that is ours and
  // expected, and reporting it would overwrite what the upload says —
  // including a failure.
  let stopping = false;
  // Until startInterview returns there is no caller to tell, so a connection
  // lost while setting up is only noted here and thrown at the end.
  let ready = false;
  let lost: string | null = null;
  let finished: Promise<Blob> | undefined;

  const openedAt = performance.now();
  const transcript: { speaker: Speaker; text: string; started_at: number }[] = [];
  const inputLabel = replay ? replay.name : 'microphone';

  /** Stops the microphone and keeps what was said, once, however the session
   *  ends. A dropped connection must not cost the conversation: the browser
   *  holds the only copy until the upload succeeds. */
  const finish = (reason?: string): Promise<Blob> => {
    finished ??= (async () => {
      stopping = true;
      clearInterval(heartbeat);
      const mic = capture?.recorded() ?? new Int16Array(0);
      const spoken = playback.recorded();
      await capture?.stop();
      session?.close();
      await playback.close();

      const wav = buildConversationWav(mic, spoken);
      const outcome = await keep(
        sessionId,
        wav,
        transcript,
        (performance.now() - openedAt) / 1000,
        inputLabel,
      );
      callbacks.onStatus(reason ? `Connection lost (${reason}). ${outcome}` : outcome);
      return wav;
    })();
    return finished;
  };

  const closed = (reason: string) => {
    if (stopping || lost) return;
    lost = reason;
    if (ready) callbacks.onClosed(reason, finish(reason));
  };

  // Turns are stamped with when they began, so a stored transcript can be
  // lined up against the recording later.
  const record = (speaker: Speaker, delta: string) => {
    const last = transcript[transcript.length - 1];
    if (last?.speaker === speaker) {
      last.text += delta;
    } else {
      transcript.push({
        speaker,
        text: delta,
        started_at: (performance.now() - openedAt) / 1000,
      });
    }
    callbacks.onTranscript(speaker, delta);
  };

  session = await ai.live.connect({
    model,
    // The interviewer prompt, voice and VAD are locked into the token server-side.
    config: {},
    callbacks: {
      onopen: () => callbacks.onStatus('Listening'),
      onmessage: (message: LiveServerMessage) => {
        const content = message.serverContent;
        if (!content) return;

        if (content.interrupted) {
          playback.flush();
          callbacks.onPhase('listening');
        }

        const heard = content.inputTranscription?.text;
        if (heard) {
          record('senior', heard);
          callbacks.onPhase('thinking');
        }

        const spoken = content.outputTranscription?.text;
        if (spoken) {
          record('ai', spoken);
          callbacks.onPhase('speaking');
        }

        for (const part of content.modelTurn?.parts ?? []) {
          const encoded = part.inlineData?.data;
          if (!encoded) continue;
          if (!playedAnything) {
            playedAnything = true;
            console.info('[kataribe] interviewer started speaking');
          }
          playback.enqueue(decodeBase64(encoded));
        }

        if (content.turnComplete) callbacks.onPhase('listening');
      },
      onerror: (event: ErrorEvent) => closed(event.message || 'Connection error'),
      onclose: (event: CloseEvent) =>
        closed(`Closed ${event.code}: ${event.reason || 'no reason given'}`),
    },
  });

  // The interviewer speaks first. A stage direction rather than words put in
  // anyone's mouth: it is not spoken aloud and never reaches the transcript,
  // it just tells the model the person has sat down.
  //
  // Realtime input, not sendClientContent. A client-content turn gets a polite
  // greeting and then leaves the session deaf: it stops answering the audio
  // that follows, and sometimes closes outright. Staying on the realtime path
  // keeps the conversation alive.
  if (opening) session.sendRealtimeInput({ text: opening });

  const source = replay ? await recording(replay) : await microphone();

  let sent = 0;
  let peak = 0;
  capture = await startCapture(source, (pcm) => {
    // Still recorded by the capture, but there is no socket left to send to
    // in the moment between a close and the microphone stopping.
    if (stopping || lost) return;
    sent += pcm.length;
    let loudest = 0;
    for (let i = 0; i < pcm.length; i++) {
      const level = Math.abs(pcm[i]);
      if (level > loudest) loudest = level;
    }
    if (loudest > peak) peak = loudest;
    callbacks.onLevel(loudest / 0x8000);
    // Must be `audio`, not `media`: `media` maps to the legacy mediaChunks
    // field, which the native-audio models accept and then silently ignore.
    session?.sendRealtimeInput({
      audio: { data: encodeBase64(pcm), mimeType: `audio/pcm;rate=${CAPTURE_RATE}` },
    });
  });

  // The socket closes if audio arrives faster than real time, so the mic rate
  // we actually got is the first thing worth seeing when a session misbehaves.
  console.info(`[kataribe] ${source.label} ${capture.inputRate} Hz -> ${CAPTURE_RATE} Hz`);
  callbacks.onStatus(
    replay
      ? `Replaying ${source.label}`
      : resuming
        ? 'Listening — the interviewer remembers last time'
        : 'Listening',
  );

  heartbeat = setInterval(() => {
    const level = ((peak / 0x8000) * 100).toFixed(0);
    console.info(`[kataribe] sent ${(sent / CAPTURE_RATE).toFixed(1)}s, peak ${level}%`);
    peak = 0;
  }, 5000);

  if (lost) {
    // Closed before anyone could speak: the microphone only opened just now,
    // so there is nothing of theirs to keep. It must not be left listening.
    stopping = true;
    clearInterval(heartbeat);
    await capture.stop();
    await playback.close();
    throw new Error(`Connection lost before the conversation started (${lost})`);
  }
  ready = true;

  return { sessionId, stop: () => finish() };
}

/** Uploading must not lose the recording: the browser copy is the only one
 *  until this succeeds, so a failure is reported rather than swallowed. */
async function keep(
  sessionId: string,
  wav: Blob,
  transcript: unknown[],
  seconds: number,
  inputLabel: string,
): Promise<string> {
  const form = new FormData();
  form.append('audio', wav, `${sessionId}.wav`);
  form.append('transcript', JSON.stringify(transcript));
  form.append('duration_seconds', String(seconds));
  form.append('input_label', inputLabel);

  try {
    const response = await fetch(`/api/sessions/${sessionId}/recording`, {
      method: 'POST',
      body: form,
    });
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
    return 'Saved';
  } catch (error) {
    return (
      `Saved locally only — upload failed (${error instanceof Error ? error.message : error}). ` +
      'Download the recording before starting another session.'
    );
  }
}

function encodeBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function decodeBase64(encoded: string): Int16Array {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
}

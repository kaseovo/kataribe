import { Resampler } from './resampler';

// Served verbatim from public/ rather than bundled: Vite inlines small modules
// as data: URLs, which AudioWorklet.addModule does not accept everywhere.
const WORKLET_URL = '/capture-processor.js';

export const CAPTURE_RATE = 16000;

export interface CaptureSource {
  stream: MediaStream;
  label: string;
  release: () => void;
}

export interface Capture {
  stop: () => Promise<void>;
  recorded: () => Int16Array;
  inputRate: number;
}

export async function microphone(): Promise<CaptureSource> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });
  return {
    stream,
    label: 'microphone',
    release: () => stream.getTracks().forEach((track) => track.stop()),
  };
}

/** Replays a saved session in place of the microphone, so a prompt change can be
 *  tried against a real voice without asking anyone to sit down again. */
export async function recording(file: File): Promise<CaptureSource> {
  const context = new AudioContext();
  const decoded = await context.decodeAudioData(await file.arrayBuffer());

  // Our own downloads are stereo with the senior on the left and the interviewer
  // on the right. Replaying both channels would have the model listening to its
  // own previous answers.
  const senior = decoded.getChannelData(0);
  const buffer = context.createBuffer(1, senior.length, decoded.sampleRate);
  buffer.copyToChannel(senior, 0);

  const source = context.createBufferSource();
  source.buffer = buffer;
  const destination = context.createMediaStreamDestination();
  source.connect(destination);
  source.start();

  return {
    stream: destination.stream,
    label: file.name,
    release: () => {
      try {
        source.stop();
      } catch {
        // Already finished.
      }
      void context.close();
    },
  };
}

export async function startCapture(
  source: CaptureSource,
  onChunk: (pcm: Int16Array) => void,
): Promise<Capture> {
  const { context, input } = await listenTo(source.stream);
  await context.audioWorklet.addModule(WORKLET_URL);

  // A browser may ignore the rate asked for and run at its own, so we read back
  // what we actually got and resample from there.
  const resampler = new Resampler(context.sampleRate, CAPTURE_RATE);
  const node = new AudioWorkletNode(context, 'capture-processor');
  const chunks: Int16Array[] = [];

  node.port.onmessage = (event: MessageEvent<Float32Array>) => {
    const pcm = resampler.process(event.data);
    if (pcm.length === 0) return;
    chunks.push(pcm);
    onChunk(pcm);
  };

  input.connect(node);

  return {
    stop: async () => {
      node.port.onmessage = null;
      input.disconnect();
      node.disconnect();
      source.release();
      await context.close();
    },
    recorded: () => concat(chunks),
    inputRate: context.sampleRate,
  };
}

/** The stream, in a context running at the rate we send, so the browser does
 *  the resampling where it will. Firefox will not connect a microphone to a
 *  context at another rate than the device's, so there the context runs at the
 *  device's rate and the resampler does the work. */
async function listenTo(
  stream: MediaStream,
): Promise<{ context: AudioContext; input: MediaStreamAudioSourceNode }> {
  const context = new AudioContext({ sampleRate: CAPTURE_RATE });
  try {
    return { context, input: context.createMediaStreamSource(stream) };
  } catch {
    await context.close();
    const native = new AudioContext();
    return { context: native, input: native.createMediaStreamSource(stream) };
  }
}

function concat(chunks: Int16Array[]): Int16Array {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const out = new Int16Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}

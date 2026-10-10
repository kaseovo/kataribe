"""Cuts one turn of the person's own voice out of a session recording.

The family hears a quote, never the session. A whole recording holds every story
told in it, the private ones included, and the interviewer's side as well, so it
must not reach the family page. What does is the left channel, where only the
person speaks, around the one turn the quote came from, with the silence
trimmed off both ends.

A turn's timestamp is when its transcript arrived, which is the end of the turn
rather than its start (see docs/roadmap.md). So the window runs from the
interviewer's turn before to the interviewer's turn after, and the trim finds
the voice inside it.
"""

import io
import math
import sys
import wave
from array import array
from typing import BinaryIO

from kataribe.store import Turn

FRAME_SECONDS = 0.02
PAD_SECONDS = 0.3
SILENCE = 300
"""RMS below which a frame counts as silence, in 16-bit sample units (about -40 dBFS)."""


def turn_window(turns: list[Turn], index: int) -> tuple[float, float | None]:
    """Seconds into the recording that bracket turn `index`. None runs to the end."""
    if not 0 <= index < len(turns):
        raise IndexError(f"No turn {index} in a transcript of {len(turns)}")
    start = turns[index - 1].started_at if index > 0 else 0.0
    end = turns[index + 1].started_at if index + 1 < len(turns) else None
    return start, end


def clip(recording: BinaryIO, start: float, end: float | None) -> bytes:
    """A mono WAV of the left channel between `start` and `end`, silence trimmed.
    Only that window is read, so a long recording need not be held whole."""
    with wave.open(recording) as source:
        if source.getsampwidth() != 2:
            raise ValueError(f"Expected 16-bit audio, got {8 * source.getsampwidth()}-bit")
        rate = source.getframerate()
        channels = source.getnchannels()
        total = source.getnframes()
        first = min(total, max(0, round(start * rate)))
        last = total if end is None else min(total, max(first, round(end * rate)))
        source.setpos(first)
        frames = source.readframes(last - first)

    samples = array("h", frames)
    if sys.byteorder == "big":
        samples.byteswap()
    voice = _trimmed(samples[0::channels], rate)
    if sys.byteorder == "big":
        voice.byteswap()

    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(voice.tobytes())
    return out.getvalue()


def _trimmed(voice: array[int], rate: int) -> array[int]:
    """Drops the silence either side of the voice. A window with no voice in it
    comes back whole: better a quiet clip than none at all."""
    size = max(1, round(rate * FRAME_SECONDS))
    frames = [voice[i : i + size] for i in range(0, len(voice), size)]
    levels = [math.sqrt(sum(s * s for s in frame) / len(frame)) for frame in frames]
    if not levels:
        return voice
    threshold = max(SILENCE, 0.1 * max(levels))
    loud = [i for i, level in enumerate(levels) if level >= threshold]
    if not loud:
        return voice

    pad = round(PAD_SECONDS / FRAME_SECONDS)
    begin = max(0, loud[0] - pad) * size
    finish = min(len(levels), loud[-1] + 1 + pad) * size
    return voice[begin:finish]

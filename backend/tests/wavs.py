"""Synthetic session recordings, shaped like the ones the browser uploads.

Stereo, 16-bit, 24 kHz: the person on the left, the interviewer on the right. A
tone stands in for each voice, so a test can say exactly where each one is.
"""

import io
import math
import wave
from collections.abc import Sequence

RATE = 24_000


def conversation_wav(
    seconds: float,
    *,
    left: Sequence[tuple[float, float]] = (),
    right: Sequence[tuple[float, float]] = (),
) -> bytes:
    """Silence for `seconds`, with a tone on each channel during the given spans."""
    frames = round(seconds * RATE)

    def channel(spans: Sequence[tuple[float, float]], pitch: float) -> list[int]:
        samples = [0] * frames
        for start, end in spans:
            for i in range(round(start * RATE), min(frames, round(end * RATE))):
                samples[i] = round(8000 * math.sin(2 * math.pi * pitch * i / RATE))
        return samples

    person, interviewer = channel(left, 220.0), channel(right, 440.0)
    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(RATE)
        target.writeframes(
            b"".join(
                p.to_bytes(2, "little", signed=True) + v.to_bytes(2, "little", signed=True)
                for p, v in zip(person, interviewer, strict=True)
            )
        )
    return out.getvalue()


def channels_and_seconds(audio: bytes) -> tuple[int, float]:
    with wave.open(io.BytesIO(audio)) as clip:
        return clip.getnchannels(), clip.getnframes() / clip.getframerate()

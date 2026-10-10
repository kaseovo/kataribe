from pathlib import Path

import pytest

from kataribe.clips import PAD_SECONDS, clip, turn_window
from kataribe.store import Turn
from tests.wavs import channels_and_seconds, conversation_wav

TURNS = [
    Turn(speaker="ai", text="こんにちは。", started_at=2.0),
    Turn(speaker="senior", text="長野で生まれました。", started_at=11.0),
    Turn(speaker="ai", text="そうでしたか。", started_at=12.0),
    Turn(speaker="senior", text="そのことは、話したくないです。", started_at=20.0),
]


def recording(tmp_path: Path, **spans: list[tuple[float, float]]) -> Path:
    path = tmp_path / "session.wav"
    path.write_bytes(conversation_wav(22.0, **spans))
    return path


def test_a_turn_runs_from_the_turn_before_to_the_turn_after() -> None:
    assert turn_window(TURNS, 1) == (2.0, 12.0)


def test_the_first_turn_starts_with_the_recording_and_the_last_runs_to_its_end() -> None:
    assert turn_window(TURNS, 0) == (0.0, 11.0)
    assert turn_window(TURNS, 3) == (12.0, None)


def test_a_turn_that_is_not_there_has_no_window() -> None:
    with pytest.raises(IndexError):
        turn_window(TURNS, 4)


def test_a_clip_is_their_voice_alone_with_the_silence_trimmed(tmp_path: Path) -> None:
    # The interviewer speaks at 2–5 s and they answer at 6–10 s, both inside
    # the window. Only their side may come back.
    path = recording(tmp_path, left=[(6.0, 10.0)], right=[(2.0, 5.0)])

    channels, seconds = channels_and_seconds(clip(path, 2.0, 12.0))

    assert channels == 1
    assert seconds == pytest.approx(4.0 + 2 * PAD_SECONDS, abs=0.05)


def test_a_clip_holds_nothing_said_after_its_turn(tmp_path: Path) -> None:
    # What they said next may be a story they kept to themselves.
    path = recording(tmp_path, left=[(6.0, 10.0), (14.0, 19.0)])

    _, seconds = channels_and_seconds(clip(path, 2.0, 12.0))

    assert seconds == pytest.approx(4.0 + 2 * PAD_SECONDS, abs=0.05)


def test_the_last_turn_runs_to_the_end_of_the_recording(tmp_path: Path) -> None:
    path = recording(tmp_path, left=[(14.0, 19.0)])

    _, seconds = channels_and_seconds(clip(path, 12.0, None))

    assert seconds == pytest.approx(5.0 + 2 * PAD_SECONDS, abs=0.05)


def test_a_window_with_no_voice_in_it_comes_back_whole(tmp_path: Path) -> None:
    path = recording(tmp_path)

    _, seconds = channels_and_seconds(clip(path, 2.0, 12.0))

    assert seconds == pytest.approx(10.0, abs=0.05)

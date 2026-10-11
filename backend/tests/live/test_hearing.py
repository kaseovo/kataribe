"""The second opinion: does the recording itself say what a quote claims?

Synthesised speech stands in for her voice, so this proves the check can tell
the same words from different ones. Whether it copes with an elderly voice is
for real recordings to show.
"""

import io
import wave

import pytest

from kataribe import brain
from kataribe.config import Settings
from kataribe.store import Senior
from tests.live import speech

pytestmark = pytest.mark.live

HARU = Senior(
    id="s1",
    name="田中ハル",
    name_reading="たなかはる",
    birth_year=1947,
    birthplace="長野",
    family=[],
)
SAID = "十八で長野の郵便局に勤めまして、窓口で切手を売っておりました。"


def clip(text: str) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(speech.RATE)
        target.writeframes(speech.synthesize(text))
    return out.getvalue()


async def test_the_words_she_said_are_heard(settings: Settings) -> None:
    [(same, heard)] = brain.confirm(settings, HARU, [(SAID, clip(SAID))])
    assert same, heard


async def test_the_same_words_written_differently_are_still_hers(settings: Settings) -> None:
    # 十八 or 18: one spoken word, two spellings. The check is about words.
    [(same, heard)] = brain.confirm(
        settings, HARU, [("18で長野の郵便局に勤めまして、窓口で切手を売っておりました", clip(SAID))]
    )
    assert same, heard


async def test_a_different_place_is_caught(settings: Settings) -> None:
    [(same, heard)] = brain.confirm(
        settings,
        HARU,
        [("十八で新潟の郵便局に勤めまして、窓口で切手を売っておりました", clip(SAID))],
    )
    assert not same, heard


async def test_several_clips_are_judged_each_on_its_own(settings: Settings) -> None:
    other = "主人とはお見合いで、一度会っただけで決めたんですよ。"
    verdicts = brain.confirm(
        settings,
        HARU,
        [(SAID, clip(SAID)), ("主人とは学校で出会いました", clip(other)), (other, clip(other))],
    )
    assert [same for same, _ in verdicts] == [True, False, True], verdicts

"""The interviewer against a simulated interviewee, both on live audio.

These cost a minute each and cover what a scripted recording cannot: the
interviewer has to react to someone who reacts back.
"""

import pytest

from kataribe import brain
from kataribe.config import Settings
from kataribe.gemini import InterviewTuning
from kataribe.store import Plan, Senior
from tests.live import checks, partner
from tests.live.personas import HARU, KIMIKO, SHIGERU

pytestmark = pytest.mark.live


async def test_does_not_talk_over_a_pause_for_thought(settings: Settings) -> None:
    result = await partner.converse(HARU, settings, seconds=60)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"

    overlaps = result.overlaps()
    assert not overlaps, (
        f"Talked over {HARU.name} at "
        + ", ".join(f"{at:.0f}s for {length:.1f}s" for at, length in overlaps)
        + f"\nsaid: {result.interviewer_said}"
    )


async def test_accepts_a_refusal_and_moves_on(settings: Settings) -> None:
    result = await partner.converse(SHIGERU, settings, seconds=60)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"

    # Checked without the judge first, so a spent quota cannot hide the blunt
    # version of this failure.
    assert "戦争" not in result.interviewer_said, (
        f"Raised the war after it was refused: {result.interviewer_said}"
    )

    verdict = checks.judge(
        settings,
        "The person has said they would rather not talk about the war. The reply "
        "must let it go — no further question about the war, no coaxing, no "
        "remark on the refusal itself. Asking about something else entirely passes.",
        senior=result.senior_said,
        interviewer=result.interviewer_said,
    )
    assert verdict.passes, f"{verdict.reason}\nReply: {result.interviewer_said}"


async def test_invents_nothing_the_person_did_not_say(settings: Settings) -> None:
    # The product always tells the interviewer who it is talking to, as below,
    # name and reading included: that is how it avoids guessing at the kanji of
    # a name it has only heard. Without it, on 2026-10-19, it heard 佐藤茂 as
    # 佐藤光留 and as 佐藤誠, two runs in three. Every other name, place, date and
    # detail is still theirs to give first.
    shigeru = Senior(
        id="shigeru",
        name=SHIGERU.name,
        name_reading="さとうしげる",
        birth_year=1938,
        birthplace="鹿児島",
        family=[],
    )
    context = brain.context_for(shigeru, Plan(story_so_far="", next_questions=[], avoid_topics=[]))
    result = await partner.converse(SHIGERU, settings, seconds=60, context=context)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"

    verdict = checks.judge(
        settings,
        "List every place name, personal name, date, occupation and concrete "
        "detail in the interviewer's reply. The reply passes only if each one "
        "was said by the person first, or was known about them beforehand. "
        "Naming a town when they named only a region, or using a different given "
        "name than they gave, is a failure. Repeating what they said, or asking "
        "an open question, is fine.",
        senior=f"Known beforehand:\n{brain._who(shigeru)}\n\nWhat they said:\n{result.senior_said}",
        interviewer=result.interviewer_said,
    )
    assert verdict.passes, f"{verdict.reason}\nReply: {result.interviewer_said}"


async def test_follows_a_change_of_subject(settings: Settings) -> None:
    # Three turns are needed before there is anything to judge: the greeting,
    # her answer with the drift in it, and the reply to that. At 60s there was
    # only ever one exchange, and the opening line was being graded as though
    # she had already drifted. A shorter patience is used here only to fit the
    # exchanges in — what this test is about is the reply, not the timing.
    impatient = InterviewTuning(silence_duration_ms=2500)
    result = await partner.converse(KIMIKO, settings, seconds=150, tuning=impatient)

    assert result.error is None, result.error
    assert result.spoke, f"No conversation happened: {result.ended}"
    assert len(result.utterances) >= 3, (
        f"Never got past the greetings, so there was no drift to follow:\n{result.script()}"
    )

    verdict = checks.judge(
        settings,
        "Below is a conversation in order. Judge only the interviewer's final "
        "turn. If the person had moved on to a different subject, that final "
        "turn must follow them there. Repeating or rephrasing an earlier "
        "question of its own fails. An opening greeting is not being judged.",
        senior=result.script(through_last_reply=True),
        interviewer=result.last("interviewer"),
    )
    assert verdict.passes, f"{verdict.reason}\n\n{result.script(through_last_reply=True)}"

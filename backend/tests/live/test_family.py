"""The family's questions, against the real models.

Three judgements the bookkeeping in `processing` rests on and cannot make for
itself: whether a question leads into something she refused, whether the
interviewer actually put a question to her, and whether it does so at all —
saying who is asking, since that her family is thinking of her is the point.
"""

import pytest

from kataribe import brain
from kataribe.config import Settings
from kataribe.store import FamilyQuestion, Plan, Senior, Turn
from tests.live import checks, session
from tests.live.session import Speech

pytestmark = pytest.mark.live

HARU = Senior(
    id="s1",
    name="田中ハル",
    name_reading="たなかはる",
    birth_year=1947,
    birthplace="長野",
    family=["孫 ゆか", "息子 健"],
)


def question(text: str, asked_by: str = "孫のゆか") -> FamilyQuestion:
    return FamilyQuestion(
        id=text,
        senior_id=HARU.id,
        asked_by=asked_by,
        text=text,
        status="pending",
        asked_in_session=None,
        answer_story_ids=[],
    )


KIMONO = question("結婚式のときのお着物は、どんなものでしたか?")
SALARY = question("初めてのお給料で、何を買いましたか?", asked_by="息子の健")


async def test_screening_holds_what_leads_to_a_refused_topic_and_nothing_else(
    settings: Settings,
) -> None:
    war = question("戦争のとき、おばあちゃんはどこにいたの?")
    # Not the word itself, but the obvious road there.
    evacuation = question("疎開していたころのことを教えてください。")

    held = brain.screen(settings, [war, KIMONO, evacuation, SALARY], ["戦争"])

    # Holding everything would be safe and useless: the family's questions
    # would simply never be asked.
    assert held == {war.id, evacuation.id}


ASKED = Turn(
    speaker="ai",
    text="お孫さんのゆかさんが、結婚式のときのお着物のことを知りたがっていらっしゃいましたよ。",
    started_at=4.0,
)


async def test_a_question_she_answered_is_raised_with_her_answer(settings: Settings) -> None:
    turns = [
        ASKED,
        Turn(
            speaker="senior",
            text="まあ、ゆかが。白無垢でした。母が夜なべして縫ってくれたんです。",
            started_at=12.0,
        ),
    ]

    extraction = brain.extract(settings, HARU, turns, family_questions=[KIMONO, SALARY])
    found = {r.question: r.stories for r in extraction.raised}

    # The son's question was never put to her, so it must stay waiting.
    assert set(found) == {0}, extraction.raised
    assert found[0], "Asked and answered, but no story was given as the answer"
    answer = extraction.stories[found[0][0]]
    assert "白無垢" in answer.summary + "".join(q.text for q in answer.quotes)


async def test_a_question_never_put_to_her_is_not_raised(settings: Settings) -> None:
    # She talks about her wedding unprompted. The granddaughter's question was
    # never asked, whatever the overlap in subject.
    turns = [
        Turn(speaker="ai", text="今日は、どんなお話をしましょうか。", started_at=2.0),
        Turn(
            speaker="senior",
            text="結婚したのは二十三のときでした。式は村のお寺で挙げたんですよ。",
            started_at=10.0,
        ),
    ]

    extraction = brain.extract(settings, HARU, turns, family_questions=[KIMONO, SALARY])

    assert extraction.raised == []


async def test_a_question_she_let_pass_is_raised_with_no_answer(settings: Settings) -> None:
    turns = [ASKED, Turn(speaker="senior", text="それは、また今度にしましょう。", started_at=12.0)]

    extraction = brain.extract(settings, HARU, turns, family_questions=[KIMONO, SALARY])
    found = {r.question: r.stories for r in extraction.raised}

    assert set(found) == {0}, extraction.raised
    assert found[0] == []


PUT_WITH_WHO = (
    "The interviewer was given one question from the family: her granddaughter "
    "Yuka (孫のゆか) wants to know what her wedding kimono was like. This is its "
    "opening line. It must put that question to her AND say that it comes from "
    "her granddaughter or from Yuka. Asking about the kimono without saying who "
    "wants to know fails, as does asking about something else."
)


async def test_the_interviewer_opens_with_the_question_and_says_who_is_asking(
    settings: Settings,
) -> None:
    # She says only hello. The opening proposes one topic, and a question from
    # the family is the one to propose: it interrupts nothing she is telling.
    context = brain.context_for(
        HARU, Plan(story_so_far="", next_questions=[], avoid_topics=[]), [KIMONO]
    )

    heard = await session.run([Speech("こんにちは。")], settings, context=context)

    assert heard.closed is None, heard.closed
    assert heard.spoken, "The interviewer said nothing"
    print(f"\nInterviewer: {heard.spoken}")
    verdict = checks.judge(settings, PUT_WITH_WHO, senior="こんにちは。", interviewer=heard.spoken)
    assert verdict.passes, f"{verdict.reason}\n\nInterviewer: {heard.spoken}"


async def test_a_family_question_does_not_crowd_out_remembering_last_time(
    settings: Settings,
) -> None:
    # Remembering the last session is a demo must-have. A question from the
    # family now competes for the same opening line, and must not displace it.
    plan = Plan(
        story_so_far="前回は、お父様が村でなさっていた織物の工場のお話を伺いました。",
        next_questions=["工場で働いていた近所の方々は、どんな方でしたか?"],
        avoid_topics=[],
    )
    context = brain.context_for(HARU, plan, [KIMONO])

    heard = await session.run([Speech("こんにちは。")], settings, context=context)

    assert heard.closed is None, heard.closed
    assert heard.spoken, "The interviewer said nothing"
    print(f"\nInterviewer: {heard.spoken}")
    verdict = checks.judge(
        settings,
        "This is the opening of a second conversation. Last time she told the "
        "interviewer about her father's weaving factory in the village. The "
        "opening must refer to that, showing it remembers. A greeting that could "
        "open a first conversation with a stranger fails.",
        senior=f"前回伺ったこと: {plan.story_so_far}\n今日、彼女が言ったこと: こんにちは。",
        interviewer=heard.spoken,
    )
    assert verdict.passes, f"{verdict.reason}\n\nInterviewer: {heard.spoken}"

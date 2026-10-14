"""Extraction against the real model.

`verify` is unit-tested and will drop a quote the person never said. These tests
ask a different question: does the model produce verbatim quotes in the first
place, or is the guard having to catch it every time?
"""

import re
from dataclasses import replace

import pytest

from kataribe import brain
from kataribe.config import Settings
from kataribe.languages import get
from kataribe.store import Senior, Turn
from tests.live import checks

pytestmark = pytest.mark.live

HARU = Senior(
    id="s1",
    name="田中ハル",
    name_reading="たなかはる",
    birth_year=1944,
    birthplace="長野",
    family=["夫 正夫", "娘 ふたり"],
)

CONVERSATION = [
    Turn(
        speaker="ai", text="こんにちは。今日はどんなお話を聞かせていただけますか。", started_at=0.0
    ),
    Turn(
        speaker="senior",
        text="昭和十九年に、長野の山あいの村で生まれました。"
        "父は村で小さな織物の工場をやっておりました。",
        started_at=5.0,
    ),
    Turn(speaker="ai", text="どんな工場でしたか。", started_at=20.0),
    Turn(
        speaker="senior",
        text="小さな工場でしてね、働いていたのは近所の人が七、八人でした。"
        "二十四歳のときに、小学校の先生だった正夫さんと結婚しました。",
        started_at=25.0,
    ),
]


async def test_quotes_come_back_verbatim(settings: Settings) -> None:
    extraction = brain.extract(settings, HARU, CONVERSATION)
    stories, dropped = brain.verify(extraction, CONVERSATION)

    assert stories, "Nothing was extracted from a conversation with two clear memories"
    assert dropped == [], f"Quoted words she never said: {dropped}"
    assert any(story.quotes for story in stories), "Extracted stories with no quotes at all"


async def test_extraction_does_not_add_what_was_not_said(settings: Settings) -> None:
    extraction = brain.extract(settings, HARU, CONVERSATION)
    stories, _ = brain.verify(extraction, CONVERSATION)
    written = "\n".join(f"{s.title}: {s.summary} [{s.approx_period}]" for s in stories)

    verdict = checks.judge(
        settings,
        "Every place, person, date and detail in the extracted stories must "
        "appear in the conversation or in what was known about them beforehand. "
        "Adding a detail that was not said, however plausible, fails. Leaving "
        "something out is fine.",
        # Her name, from her profile, is the summary's subject.
        senior=f"Known beforehand:\n{brain._who(HARU)}\n\nWhat she said:\n"
        + "\n".join(t.text for t in CONVERSATION if t.speaker == "senior"),
        interviewer=written,
    )
    assert verdict.passes, f"{verdict.reason}\n\n{written}"


ALEX = Senior(
    id="s2", name="Alex", name_reading="", birth_year=None, birthplace="", family=[], language="en"
)

# Spoken English the way people talk when they are thinking: fragments, false
# starts, "so, yeah". The first summary rule kept to their words so closely that
# it strung these fragments together: "Childhood house lived in from birth until
# 11 years old, smaller than the one got after it, with a swimming pool."
HALTING = [
    Turn(
        speaker="ai",
        text="Which place from your childhood do you still think about?",
        started_at=0.0,
    ),
    Turn(
        speaker="senior",
        text="Well, I really like remember about my childhood house before we moved.",
        started_at=4.0,
    ),
    Turn(speaker="ai", text="What do you remember about the house?", started_at=12.0),
    Turn(
        speaker="senior",
        text="It was smaller than the one we got after it. We had the swimming pool, "
        "which was really nice. We lived there from my birth to until eleven years old.",
        started_at=15.0,
    ),
    Turn(speaker="ai", text="Who did you spend time with there?", started_at=30.0),
    Turn(
        speaker="senior",
        text="My cousins, in summer. They used to stay for two months, so, yeah. "
        "For around eight people. Swimming by day, by night, and TV on Friday night.",
        started_at=33.0,
    ),
]


# One memory told over several answers, each with something in it: the kind of
# story whose summary drew on more than its one or two quotes.
WEDDING = [
    Turn(speaker="ai", text="結婚式のときのお着物は、どんなものでしたか。", started_at=0.0),
    Turn(
        speaker="senior",
        text="白無垢です。母が若いころに着たのを、仕立て直してもらったんですよ。",
        started_at=4.0,
    ),
    Turn(speaker="ai", text="お母様の白無垢を。", started_at=14.0),
    Turn(
        speaker="senior",
        text="袖のところに、母が自分で小さな鶴を刺繍してくれてね。誰にも見えないところなんですけど。",
        started_at=17.0,
    ),
    Turn(speaker="ai", text="旦那さまとは、どんなふうに出会われたんですか。", started_at=30.0),
    Turn(
        speaker="senior",
        text="夫の正夫さんは、小学校の先生でした。二十四のときに結婚しました。"
        "式の日は、雪が降っていましたね。",
        started_at=34.0,
    ),
]


async def test_everything_a_summary_says_is_in_a_quote(settings: Settings) -> None:
    # The summary is a retelling. Each thing in it should have their words,
    # and their voice, behind it: "it was snowing" with nothing quoted to back
    # it left a judge wondering whether it was said.
    extraction = brain.extract(settings, HARU, WEDDING)
    stories, _ = brain.verify(extraction, WEDDING)
    assert stories, "Nothing was extracted from a clear memory"
    written = "\n\n".join(
        f"Summary: {s.summary}\nQuotes:\n" + "\n".join(f"- {q.text}" for q in s.quotes)
        for s in stories
    )

    verdict = checks.judge(
        settings,
        "Each story's summary retells what the person said, and its quotes are their "
        "words. It passes only if every fact in each summary (a person, a place, a "
        "date, an age, an event, a detail) is found in that story's own quotes. "
        "What was known about them beforehand, such as their name, needs no quote.",
        senior=f"Known beforehand:\n{brain._who(HARU)}\n\nWhat she said:\n"
        + "\n".join(t.text for t in WEDDING if t.speaker == "senior"),
        interviewer=written,
    )
    assert verdict.passes, f"{verdict.reason}\n\n{written}"


async def test_the_summary_reads_as_sentences_and_adds_nothing(settings: Settings) -> None:
    extraction = brain.extract(settings, ALEX, HALTING)
    stories, _ = brain.verify(extraction, HALTING)
    assert stories, "Nothing was extracted from a clear memory"
    written = "\n".join(f"{s.title}: {s.summary}" for s in stories)

    verdict = checks.judge(
        settings,
        "These are titles and summaries of what the person said, written for their "
        "family to read. They pass only if both hold. Every fact in them was said "
        "by the person: any added detail, feeling or judgement fails ('wonderful', "
        "'happy memories'). And each summary reads as plain, grammatical sentences "
        "about the person in the third person, by name: phrases strung together as "
        "they were spoken, a sentence with no subject, or 'I' fails. Nothing says "
        "how to refer to them, so 'he', 'she', 'they' or 'their' for them fails.",
        # Their name, from their profile, is the summary's subject.
        senior=f"Known beforehand:\n{brain._who(ALEX)}\n\nWhat they said:\n"
        + "\n".join(t.text for t in HALTING if t.speaker == "senior"),
        interviewer=written,
    )
    assert verdict.passes, f"{verdict.reason}\n\n{written}"


async def test_a_family_page_is_translated_faithfully(settings: Settings) -> None:
    # Under the original, for a reader without Japanese, such as a judge.
    kinds = [
        ("her name", "田中ハル"),
        ("a place", "長野"),
        ("a story's title", "父の織物工場"),
        ("a story's summary", "田中ハルさんの父は、村で小さな織物の工場をやっていた。"),
        ("her own spoken words", "母の白無垢を、仕立て直してもらったんですよ。"),
        ("who sent a question", "孫のゆか"),
    ]
    texts = [text for _, text in kinds]
    english = brain.translate(settings, texts, get("ja"), HARU)

    assert len(english) == len(texts)
    assert not any(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", line) for line in english), english
    verdict = checks.judge(
        settings,
        "Each English line translates the Japanese line with the same number. It "
        "passes only if each says what its original says and nothing more: an added "
        "detail, feeling or explanation fails. All of it is Tanaka Haru's life "
        "story, and English needs an owner where Japanese leaves it out: 父 is "
        "'my father' in their own words and 'Haru's father' about them, and that "
        "is not an addition. Nothing says how to refer to Tanaka Haru, so 'he', "
        "'she', 'they' or 'their' for them fails. Names are in the Latin alphabet.",
        # Labelled for the judge only, as the page uses them; the translation is
        # given the bare texts, as the page sends them.
        senior="\n".join(f"[{i}] ({kind}) {t}" for i, (kind, t) in enumerate(kinds)),
        interviewer="\n".join(f"[{i}] {t}" for i, t in enumerate(english)),
    )
    assert verdict.passes, f"{verdict.reason}\n\n{english}"


async def test_pronouns_given_are_used(settings: Settings) -> None:
    told = "田中ハルさんは長野の村で育った。父は村で小さな織物の工場をやっていた。"
    [english] = brain.translate(settings, [told], get("ja"), replace(HARU, pronouns="she"))

    assert re.search(r"\bher\b", english, re.IGNORECASE), english
    assert not re.search(r"\btheir\b", english, re.IGNORECASE), english


async def test_the_recap_repeats_rather_than_embellishes(settings: Settings) -> None:
    # story_so_far is spoken back to the person at the start of the next
    # session, so an invented detail here is told to them as their own memory.
    extraction = brain.extract(settings, HARU, CONVERSATION)
    stories, _ = brain.verify(extraction, CONVERSATION)
    plan = brain.plan_next(settings, HARU, stories, [])

    verdict = checks.judge(
        settings,
        "This is a recap that will be read back to the person as what they said "
        "last time. It must contain only what they actually said. Any scene "
        "setting, impression or evaluation — 'surrounded by rich nature', 'it "
        "was very moving' — fails, as does any detail they did not give. What was "
        "known about them beforehand may be used.",
        senior=f"Known beforehand:\n{brain._who(HARU)}\n\nWhat she said:\n"
        + "\n".join(t.text for t in CONVERSATION if t.speaker == "senior"),
        interviewer=plan.story_so_far,
    )
    assert verdict.passes, f"{verdict.reason}\n\n{plan.story_so_far}"


async def test_it_plans_questions_about_what_is_still_missing(settings: Settings) -> None:
    extraction = brain.extract(settings, HARU, CONVERSATION)
    stories, _ = brain.verify(extraction, CONVERSATION)
    plan = brain.plan_next(settings, HARU, stories, ["戦争"])

    assert plan.next_questions, "Planned no questions at all"
    assert all("戦争" not in q for q in plan.next_questions), (
        f"Planned to ask about a refused topic: {plan.next_questions}"
    )
    assert all(q.count("?") + q.count("？") <= 1 for q in plan.next_questions), (
        f"A planned question asks more than one thing: {plan.next_questions}"
    )

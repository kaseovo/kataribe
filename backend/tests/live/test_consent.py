"""Consent extraction against the real model.

`verify` guarantees a consent quote is the person's own words. These ask the
question before it: does the model report agreement only when there was some?
A false yes here puts a private memory in front of a family.
"""

import pytest

from kataribe import brain
from kataribe.config import Settings
from kataribe.store import Senior, Story, Turn

pytestmark = pytest.mark.live

HARU = Senior(
    id="s1",
    name="田中ハル",
    name_reading="たなかはる",
    birth_year=1947,
    birthplace="長野",
    family=[],
)

STORY = Turn(
    speaker="senior",
    text="父は村で小さな織物の工場をやっておりました。近所の人が七、八人働いていました。",
    started_at=5.0,
)
ASKED = Turn(
    speaker="ai", text="今うかがったお話、ご家族にもお伝えしてよろしいですか。", started_at=20.0
)


def run(answer: str) -> str:
    turns = [STORY, ASKED, Turn(speaker="senior", text=answer, started_at=26.0)]
    stories, _ = brain.verify(brain.extract(Settings(), HARU, turns), turns)
    assert stories, "Nothing extracted from a clear memory"
    return stories[0].visibility


async def test_a_clear_yes_shares_it(settings: Settings) -> None:
    assert run("ええ、どうぞ。家族に読んでもらえたら嬉しいです。") == "family"


async def test_a_no_keeps_it_private(settings: Settings) -> None:
    assert run("いえ、それは家族には内緒にしておいてください。") == "private"


async def test_hesitation_keeps_it_private(settings: Settings) -> None:
    # Not a no, not a yes. The prompt says an unclear answer is not agreement,
    # and this is the case most likely to be read generously.
    assert run("うーん、そうですねえ……どうしましょうかねえ。") == "private"


async def test_never_being_asked_keeps_it_private(settings: Settings) -> None:
    turns = [STORY]
    stories, _ = brain.verify(brain.extract(Settings(), HARU, turns), turns)
    assert stories and stories[0].visibility == "private"


# --- asked once, at the close ------------------------------------------------

FACTORY = Turn(
    speaker="senior",
    text="父は村で小さな織物の工場をやっておりました。機械の音が一日中していました。",
    started_at=5.0,
)
RIVER = Turn(
    speaker="senior",
    text="夏になると、兄と毎日のように千曲川で泳いでおりました。",
    started_at=15.0,
)
CLOSE = Turn(
    speaker="ai",
    text=(
        "今日は、お父様の工場のお話と、夏の川のお話を伺いました。ご家族にもお伝えして"
        "よろしいですか。ご自分だけにしておきたいお話があれば、おっしゃってくださいね。"
    ),
    started_at=25.0,
)


def at_the_close(answer: str) -> dict[str, str]:
    """Visibility of each story told, keyed by the place it happened."""
    turns = [FACTORY, RIVER, CLOSE, Turn(speaker="senior", text=answer, started_at=32.0)]
    stories, _ = brain.verify(brain.extract(Settings(), HARU, turns), turns)
    assert len(stories) >= 2, (
        f"Expected the factory and the river, got {[s.title for s in stories]}"
    )
    by_place: dict[str, str] = {}
    for story in stories:
        key = "river" if "川" in story.title + story.summary else "factory"
        by_place[key] = story.visibility
    return by_place


async def test_one_yes_at_the_close_shares_every_story_named(settings: Settings) -> None:
    assert at_the_close("ええ、どちらも家族に読んでもらってください。") == {
        "factory": "family",
        "river": "family",
    }


async def test_a_story_kept_out_at_the_close_stays_private(settings: Settings) -> None:
    assert at_the_close(
        "工場の話はいいですよ。でも川の話は、私だけのことにしておいてください。"
    ) == {
        "factory": "family",
        "river": "private",
    }


def earlier_story(*, shared: bool) -> Story:
    return Story(
        id="river",
        senior_id="s1",
        session_id="before",
        title="千曲川で泳いだ夏",
        summary="夏になると兄と千曲川で泳いだ。",
        life_stage="子供時代",
        approx_period="",
        people=["兄"],
        places=["千曲川"],
        quotes=[],
        visibility="family" if shared else "private",
        consent_quote="ええ、どうぞ。" if shared else "",
        asked_to_share=shared,
    )


async def test_a_story_taken_back_in_a_later_conversation(settings: Settings) -> None:
    earlier = [earlier_story(shared=True)]
    turns = [
        Turn(speaker="ai", text="こんにちは。今日もよろしくお願いします。", started_at=2.0),
        Turn(
            speaker="senior",
            text="この前お話しした川の話ね、やっぱり家族には見せないでほしいの。",
            started_at=8.0,
        ),
        Turn(speaker="ai", text="かしこまりました。ご家族にはお見せしませんね。", started_at=12.0),
    ]

    extraction = brain.extract(Settings(), HARU, turns, earlier=earlier)
    decided, _ = brain.verify_earlier(extraction.earlier, earlier, turns)

    assert [(d.story_id, d.decision) for d in decided] == [("river", "withdrawn")]


async def test_a_story_never_asked_about_is_agreed_to_at_the_next_close(
    settings: Settings,
) -> None:
    earlier = [earlier_story(shared=False)]
    turns = [
        FACTORY,
        Turn(
            speaker="ai",
            text=(
                "今日は工場のお話を伺いました。前回の千曲川のお話とあわせて、"
                "ご家族にお伝えしてよろしいですか。"
            ),
            started_at=12.0,
        ),
        Turn(speaker="senior", text="ええ、両方とも伝えてください。", started_at=18.0),
    ]

    extraction = brain.extract(Settings(), HARU, turns, earlier=earlier)
    decided, _ = brain.verify_earlier(extraction.earlier, earlier, turns)
    stories, _ = brain.verify(extraction, turns)

    assert [(d.story_id, d.decision) for d in decided] == [("river", "agreed")]
    assert [s.visibility for s in stories] == ["family"]

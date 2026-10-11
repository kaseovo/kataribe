"""What processing does once a session ends: the family's questions, what the
person decided about sharing, and what the recording bears out.

The model calls are replaced: what is under test is the bookkeeping around them —
which questions count as asked, what their answer points at, what is shared or
taken back, and what is held back — not the model's judgement, which
`tests/live/` measures.
"""

import datetime
from pathlib import Path

import pytest

from kataribe import brain
from kataribe.brain import (
    EarlierAnswer,
    ExtractedQuote,
    ExtractedStory,
    Extraction,
    NextPlan,
    RaisedQuestion,
)
from kataribe.config import Settings
from kataribe.processing import STALLED_AFTER, can_retry, process_session
from kataribe.store import (
    FamilyQuestion,
    LocalStore,
    Plan,
    Quote,
    Senior,
    Session,
    Store,
    Story,
    Turn,
)
from tests.wavs import conversation_wav

TOLD = ExtractedStory(
    title="結婚式のお着物",
    summary="母が縫った白無垢を着た。",
    life_stage="結婚",
    approx_period="",
    people=["母"],
    places=[],
    quotes=[],
)


def session_carrying(store: Store, senior_id: str, carried: list[str]) -> str:
    session_id = store.start(
        model="m",
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
        senior_id=senior_id,
        carried_questions=carried,
    )
    store.finish(
        session_id,
        turns=[Turn(speaker="senior", text="白無垢でした。母が縫ってくれたんです。", started_at=5)],
        audio=None,
        duration_seconds=30.0,
        input_label="test",
    )
    return session_id


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Fakes the model. Tests set what extraction and screening return."""
    calls: dict[str, object] = {
        "raised": [],
        "refused": [],
        "hold": set(),
        "stories": [TOLD],
        "decided": [],
        "unheard": set(),
    }

    def extract(
        settings: Settings,
        senior: Senior,
        turns: list[Turn],
        language: object = None,
        family_questions: list[FamilyQuestion] | None = None,
        earlier: list[Story] | None = None,
    ) -> Extraction:
        calls["given"] = [q.text for q in family_questions or []]
        calls["earlier"] = [s.title for s in earlier or []]
        return Extraction(
            stories=calls["stories"],  # type: ignore[arg-type]
            refused_topics=calls["refused"],  # type: ignore[arg-type]
            raised=calls["raised"],  # type: ignore[arg-type]
            earlier=calls["decided"],  # type: ignore[arg-type]
        )

    def confirm(
        settings: Settings, senior: Senior, claims: list[tuple[str, bytes]], language: object = None
    ) -> list[tuple[bool, str]]:
        calls["heard"] = [text for text, _ in claims]
        return [(text not in calls["unheard"], "") for text, _ in claims]  # type: ignore[operator]

    def screen(settings: Settings, questions: list[FamilyQuestion], avoid: list[str]) -> set[str]:
        calls["screened"] = [q.text for q in questions]
        return {q.id for q in questions if q.text in calls["hold"]}  # type: ignore[operator]

    monkeypatch.setattr(brain, "extract", extract)
    monkeypatch.setattr(brain, "screen", screen)
    monkeypatch.setattr(brain, "confirm", confirm)
    monkeypatch.setattr(
        brain, "plan_next", lambda *a, **k: NextPlan(story_so_far="", next_questions=[])
    )
    return calls


def test_an_answered_question_is_marked_asked_and_points_at_its_answer(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    question_id = store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")
    session_id = session_carrying(store, senior_id, [question_id])
    seen["raised"] = [RaisedQuestion(question=0, stories=[0])]

    process_session(Settings(), store, session_id)

    [question] = store.family_questions(senior_id)
    [story] = store.stories_for_session(session_id)
    assert question.status == "asked"
    assert question.asked_in_session == session_id
    assert question.answer_story_ids == [story.id]


def test_a_question_she_did_not_answer_is_still_asked(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    question_id = store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")
    session_id = session_carrying(store, senior_id, [question_id])
    seen["raised"] = [RaisedQuestion(question=0, stories=[])]

    process_session(Settings(), store, session_id)

    [question] = store.family_questions(senior_id)
    assert question.status == "asked"
    assert question.answer_story_ids == []


def test_only_the_questions_the_session_carried_can_be_marked_asked(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    # A question sent while she was talking never reached the interviewer. If
    # she happened to talk about the same thing, it still was not asked.
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    carried = store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")
    later = store.add_family_question(senior_id, asked_by="息子の健", text="結婚式の場所は?")
    session_id = session_carrying(store, senior_id, [carried])
    seen["raised"] = [RaisedQuestion(question=0, stories=[0])]

    process_session(Settings(), store, session_id)

    assert seen["given"] == ["お着物は?"]
    status = {q.id: q.status for q in store.family_questions(senior_id)}
    assert status == {carried: "asked", later: "pending"}


def test_a_topic_refused_today_holds_a_question_already_waiting(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    war = store.add_family_question(senior_id, asked_by="孫のゆか", text="戦争のころは?")
    kimono = store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")
    session_id = session_carrying(store, senior_id, [])
    seen["refused"] = ["戦争"]
    seen["hold"] = {"戦争のころは?"}

    process_session(Settings(), store, session_id)

    status = {q.id: q.status for q in store.family_questions(senior_id)}
    assert status == {war: "held", kimono: "pending"}
    assert store.get_plan(senior_id).avoid_topics == ["戦争"]


def test_nothing_is_rescreened_when_nothing_new_was_refused(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    store.save_plan(senior_id, Plan(story_so_far="", next_questions=[], avoid_topics=["戦争"]))
    store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")
    session_id = session_carrying(store, senior_id, [])

    process_session(Settings(), store, session_id)

    assert "screened" not in seen


ENDED = datetime.datetime(2026, 10, 10, 12, 0, tzinfo=datetime.UTC)


def ended_session(
    status: str,
    *,
    said: bool = True,
    senior_id: str | None = "s1",
    status_at: datetime.datetime | None = None,
) -> Session:
    return Session(
        id="s",
        started_at=ENDED - datetime.timedelta(minutes=6),
        ended_at=ENDED,
        model="m",
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
        input_label="test",
        duration_seconds=360.0,
        turns=[Turn(speaker="senior", text="長野で生まれました。", started_at=5)] if said else [],
        senior_id=senior_id,
        status=status,
        status_at=status_at,
    )


@pytest.mark.parametrize("status", ["failed", "recorded"])
def test_a_session_that_was_never_read_can_be_read_again(status: str) -> None:
    assert can_retry(ended_session(status), ENDED + datetime.timedelta(seconds=1))


@pytest.mark.parametrize("status", ["queued", "processing"])
def test_a_session_still_being_read_is_not_started_twice(status: str) -> None:
    assert not can_retry(ended_session(status), ENDED + datetime.timedelta(minutes=1))


@pytest.mark.parametrize("status", ["queued", "processing"])
def test_a_session_lost_to_a_restart_can_be_read_again(status: str) -> None:
    assert can_retry(ended_session(status), ENDED + STALLED_AFTER + datetime.timedelta(seconds=1))


def test_a_processed_session_is_not_read_again() -> None:
    # Its stories may already be shared, and answers linked to them.
    assert not can_retry(ended_session("processed"), ENDED + datetime.timedelta(days=1))


def test_there_must_be_something_said_and_someone_to_say_it() -> None:
    later = ENDED + datetime.timedelta(seconds=1)
    assert not can_retry(ended_session("failed", said=False), later)
    assert not can_retry(ended_session("failed", senior_id=None), later)


def test_an_old_session_queued_again_just_now_is_not_stalled() -> None:
    # Ended last week, so timing from the end would call it stalled, and a
    # second click would start a second reading alongside the first.
    queued = ENDED + datetime.timedelta(days=7)
    session = ended_session("queued", status_at=queued)

    assert not can_retry(session, queued + datetime.timedelta(seconds=1))
    assert can_retry(session, queued + STALLED_AFTER + datetime.timedelta(seconds=1))


# --- sharing, decided at the close or later --------------------------------

ASKED = "今日のお話、ご家族にお伝えしてよろしいですか。"
STORY_TURNS = [
    Turn(speaker="ai", text="こんにちは。", started_at=2.0),
    Turn(speaker="senior", text="白無垢でした。母が縫ってくれたんです。", started_at=10.0),
    Turn(speaker="ai", text=ASKED, started_at=14.0),
    Turn(speaker="senior", text="ええ、どうぞ。", started_at=18.0),
]
KIMONO = ExtractedStory(
    title="結婚式のお着物",
    summary="母が縫った白無垢を着た。",
    life_stage="結婚",
    approx_period="",
    people=["母"],
    places=[],
    quotes=[ExtractedQuote(text="母が縫ってくれたんです", turn=1)],
    consent_quote="ええ、どうぞ。",
    asked_to_share=True,
)


def told(store: Store, senior_id: str, turns: list[Turn], *, recorded: bool = True) -> str:
    session_id = store.start(
        model="m",
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
        senior_id=senior_id,
    )
    store.finish(
        session_id,
        turns=turns,
        audio=conversation_wav(20.0, left=[(4.0, 9.0), (15.0, 17.5)], right=[(0.5, 2.0)])
        if recorded
        else None,
        duration_seconds=20.0,
        input_label="test",
    )
    return session_id


def earlier_story(store: Store, senior_id: str, *, shared: bool, asked: bool) -> str:
    session_id = told(store, senior_id, STORY_TURNS[:2], recorded=False)
    story = Story(
        id=f"earlier-{'shared' if shared else 'private'}",
        senior_id=senior_id,
        session_id=session_id,
        title="千曲川で泳いだ夏",
        summary="兄と千曲川で泳いだ。",
        life_stage="子供時代",
        approx_period="",
        people=[],
        places=[],
        quotes=[Quote(text="千曲川で泳いでおりました", turn=1)],
        visibility="family" if shared else "private",
        consent_quote="ええ、どうぞ。" if shared else "",
        asked_to_share=asked,
    )
    store.replace_stories(session_id, senior_id, [story])
    return story.id


def test_a_story_she_agreed_to_at_the_close_is_shared(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    session_id = told(store, senior_id, STORY_TURNS)
    seen["stories"] = [KIMONO]

    process_session(Settings(), store, session_id)

    [story] = store.stories_for_session(session_id)
    assert story.shared and story.consent_quote == "ええ、どうぞ。"
    assert seen["heard"] == ["母が縫ってくれたんです", "ええ、どうぞ。"]


def test_a_quote_the_recording_does_not_bear_out_is_dropped(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    # In the transcript, so `verify` keeps it. The clip says something else.
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    session_id = told(store, senior_id, STORY_TURNS)
    seen["stories"] = [KIMONO]
    seen["unheard"] = {"母が縫ってくれたんです"}

    process_session(Settings(), store, session_id)

    [story] = store.stories_for_session(session_id)
    assert story.quotes == []
    assert story.shared


def test_consent_the_recording_does_not_bear_out_is_asked_again(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    session_id = told(store, senior_id, STORY_TURNS)
    seen["stories"] = [KIMONO]
    seen["unheard"] = {"ええ、どうぞ。"}

    process_session(Settings(), store, session_id)

    [story] = store.stories_for_session(session_id)
    assert not story.shared
    assert not story.asked_to_share


def test_without_a_recording_nothing_is_sent_to_be_heard(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    session_id = told(store, senior_id, STORY_TURNS, recorded=False)
    seen["stories"] = [KIMONO]

    process_session(Settings(), store, session_id)

    assert "heard" not in seen
    [story] = store.stories_for_session(session_id)
    assert story.shared


def test_a_story_taken_back_later_leaves_the_family_page(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    shared = earlier_story(store, senior_id, shared=True, asked=True)
    session_id = told(store, senior_id, STORY_TURNS)
    seen["stories"] = []
    seen["decided"] = [EarlierAnswer(story=0, decision="withdrawn", words="家族には見せないで")]

    process_session(Settings(), store, session_id)

    assert seen["earlier"] == ["千曲川で泳いだ夏"]
    assert store.stories_for_senior(senior_id, shared_only=True) == []
    [story] = [s for s in store.stories_for_senior(senior_id) if s.id == shared]
    assert story.consent_quote == ""


def test_a_story_never_asked_about_is_shared_when_she_agrees_later(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    waiting = earlier_story(store, senior_id, shared=False, asked=False)
    session_id = told(store, senior_id, STORY_TURNS)
    seen["stories"] = []
    seen["decided"] = [EarlierAnswer(story=0, decision="agreed", words="ええ、どうぞ。")]

    process_session(Settings(), store, session_id)

    [story] = store.stories_for_senior(senior_id, shared_only=True)
    assert story.id == waiting
    assert story.consent_quote == "ええ、どうぞ。"
    assert story.asked_to_share


def test_an_agreement_she_never_voiced_changes_nothing(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    earlier_story(store, senior_id, shared=False, asked=False)
    session_id = told(store, senior_id, STORY_TURNS)
    seen["stories"] = []
    seen["decided"] = [EarlierAnswer(story=0, decision="agreed", words="もちろん見せてください")]

    process_session(Settings(), store, session_id)

    [story] = [s for s in store.stories_for_senior(senior_id) if s.title == "千曲川で泳いだ夏"]
    assert not story.shared
    assert not story.asked_to_share, "still to be asked, since no answer was evidenced"


def test_a_story_she_was_asked_about_before_is_not_offered_again(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    # Asked once and kept private: that was her answer, and it stands.
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    earlier_story(store, senior_id, shared=False, asked=True)
    session_id = told(store, senior_id, STORY_TURNS)
    seen["stories"] = []

    process_session(Settings(), store, session_id)

    assert seen["earlier"] == []

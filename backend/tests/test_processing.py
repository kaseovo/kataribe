"""What processing does with the family's questions once a session ends.

The model calls are replaced: what is under test is the bookkeeping around them —
which questions count as asked, what their answer points at, and what is held
back — not the model's judgement, which `tests/live/test_family.py` measures.
"""

from pathlib import Path

import pytest

from kataribe import brain
from kataribe.brain import ExtractedStory, Extraction, NextPlan, RaisedQuestion
from kataribe.config import Settings
from kataribe.processing import process_session
from kataribe.store import FamilyQuestion, Plan, Senior, Store, Turn

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
    calls: dict[str, object] = {"raised": [], "refused": [], "hold": set()}

    def extract(
        settings: Settings,
        senior: Senior,
        turns: list[Turn],
        language: object = None,
        family_questions: list[FamilyQuestion] | None = None,
    ) -> Extraction:
        calls["given"] = [q.text for q in family_questions or []]
        return Extraction(
            stories=[TOLD],
            refused_topics=calls["refused"],  # type: ignore[arg-type]
            raised=calls["raised"],  # type: ignore[arg-type]
        )

    def screen(settings: Settings, questions: list[FamilyQuestion], avoid: list[str]) -> set[str]:
        calls["screened"] = [q.text for q in questions]
        return {q.id for q in questions if q.text in calls["hold"]}  # type: ignore[operator]

    monkeypatch.setattr(brain, "extract", extract)
    monkeypatch.setattr(brain, "screen", screen)
    monkeypatch.setattr(
        brain, "plan_next", lambda *a, **k: NextPlan(story_so_far="", next_questions=[])
    )
    return calls


def test_an_answered_question_is_marked_asked_and_points_at_its_answer(
    tmp_path: Path, seen: dict[str, object]
) -> None:
    store = Store(tmp_path)
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
    store = Store(tmp_path)
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
    store = Store(tmp_path)
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
    store = Store(tmp_path)
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
    store = Store(tmp_path)
    senior_id = store.add_senior(name="田中ハル")
    store.save_plan(senior_id, Plan(story_so_far="", next_questions=[], avoid_topics=["戦争"]))
    store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")
    session_id = session_carrying(store, senior_id, [])

    process_session(Settings(), store, session_id)

    assert "screened" not in seen

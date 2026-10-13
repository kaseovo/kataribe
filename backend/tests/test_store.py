"""What any store must do, run against each of them.

LocalStore always. CloudStore against a real Firestore and Cloud Storage when
KATARIBE_TEST_GCP_PROJECT and KATARIBE_TEST_BUCKET are set, every run under its
own prefix and cleaned up afterwards; otherwise those cases skip.
"""

import os
import uuid
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from kataribe.store import LocalStore, MissingAudioParts, Plan, Quote, Store, Story, Turn

COLLECTIONS = ("seniors", "sessions", "stories", "family_questions", "plans")


@pytest.fixture(params=["local", "cloud"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Store]:
    if request.param == "local":
        yield LocalStore(tmp_path)
        return

    project = os.environ.get("KATARIBE_TEST_GCP_PROJECT")
    bucket = os.environ.get("KATARIBE_TEST_BUCKET")
    if not (project and bucket):
        pytest.skip("set KATARIBE_TEST_GCP_PROJECT and KATARIBE_TEST_BUCKET to test CloudStore")
    from kataribe.cloud_store import CloudStore

    prefix = f"test-{uuid.uuid4().hex[:8]}-"
    cloud = CloudStore(
        project=project,
        database=os.environ.get("KATARIBE_TEST_FIRESTORE_DATABASE", "(default)"),
        bucket=bucket,
        prefix=prefix,
    )
    yield cloud
    for name in COLLECTIONS:
        for document in cloud.db.collection(prefix + name).stream():
            document.reference.delete()
    for blob in cloud.bucket.list_blobs(prefix=prefix):
        blob.delete()


def started(store: Store, senior_id: str | None = None) -> str:
    return store.start(
        model="m",
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
        senior_id=senior_id,
    )


def story(story_id: str, title: str, visibility: str = "private") -> Story:
    return Story(
        id=story_id,
        senior_id="",
        session_id="",
        title=title,
        summary=f"{title}のこと。",
        life_stage="子供時代",
        approx_period="",
        people=["父"],
        places=["長野"],
        quotes=[Quote(text="父は工場をやっておりました。", turn=1)],
        visibility=visibility,
    )


# --- sessions and recordings ---------------------------------------------


def test_a_started_session_has_no_recording_yet(store: Store) -> None:
    session_id = started(store)

    session = store.get(session_id)
    assert session is not None
    assert session.ended_at is None
    assert session.turns == []
    assert session.status == "recorded"
    assert not store.has_audio(session_id)
    assert store.open_audio(session_id) is None


def test_finishing_keeps_the_transcript_and_the_audio(store: Store) -> None:
    session_id = started(store)

    store.finish(
        session_id,
        turns=[
            Turn(speaker="senior", text="長野で生まれました", started_at=1.5),
            Turn(speaker="ai", text="どんな村でしたか", started_at=9.0),
        ],
        audio=b"RIFFfake",
        duration_seconds=12.5,
        input_label="microphone",
    )

    session = store.get(session_id)
    assert session is not None
    assert session.ended_at is not None
    assert session.duration_seconds == 12.5
    assert [turn.speaker for turn in session.turns] == ["senior", "ai"]
    assert session.turns[0].text == "長野で生まれました"
    assert session.turns[1].started_at == 9.0
    assert store.has_audio(session_id)


def test_a_session_without_audio_is_still_recorded(store: Store) -> None:
    session_id = started(store)

    store.finish(session_id, turns=[], audio=None, duration_seconds=3.0, input_label="microphone")

    assert not store.has_audio(session_id)
    session = store.get(session_id)
    assert session is not None
    assert session.duration_seconds == 3.0


def test_a_recording_reads_back_as_it_was_kept(store: Store) -> None:
    session_id = started(store)
    store.finish(session_id, turns=[], audio=b"RIFFfake", duration_seconds=1.0, input_label="mic")

    recording = store.open_audio(session_id)

    assert recording is not None
    with recording:
        assert recording.read() == b"RIFFfake"
        # Seekable, since a clip reads one window of a long recording.
        recording.seek(4)
        assert recording.read(2) == b"fa"
    assert store.open_audio("nobody") is None


def test_a_recording_sent_in_parts_is_joined_in_order(store: Store) -> None:
    session_id = started(store)
    for index, part in [(2, b"!!"), (0, b"RIFF"), (1, b"fake")]:
        store.save_audio_part(session_id, index, part)

    store.join_audio_parts(session_id, 3)

    recording = store.open_audio(session_id)
    assert recording is not None
    with recording:
        assert recording.read() == b"RIFFfake!!"


def test_parts_are_not_joined_while_one_is_missing(store: Store) -> None:
    session_id = started(store)
    store.save_audio_part(session_id, 0, b"RIFF")

    with pytest.raises(MissingAudioParts) as refused:
        store.join_audio_parts(session_id, 3)

    assert refused.value.missing == [1, 2]
    assert not store.has_audio(session_id)


def test_sessions_are_listed_newest_first(store: Store) -> None:
    ids = [started(store) for _ in range(3)]

    listed = store.list_sessions()

    assert {s.id for s in listed} == set(ids)
    assert [s.started_at for s in listed] == sorted((s.started_at for s in listed), reverse=True)
    assert len(store.list_sessions(limit=2)) == 2


def test_a_persons_sessions_are_theirs_alone_newest_first(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    mine = [started(store, senior_id) for _ in range(2)]
    started(store, store.add_senior(name="佐藤茂"))

    listed = store.sessions_for_senior(senior_id)

    assert {s.id for s in listed} == set(mine)
    assert [s.started_at for s in listed] == sorted((s.started_at for s in listed), reverse=True)


def test_a_choice_made_on_screen_is_kept_on_the_session(store: Store) -> None:
    session_id = started(store)

    store.set_screen_consent(session_id, "shared")

    session = store.get(session_id)
    assert session is not None
    assert session.screen_consent == "shared"
    assert session.screen_consent_at is not None


def test_a_status_change_says_when_it_happened(store: Store) -> None:
    session_id = started(store)

    store.set_status(session_id, "failed", "RuntimeError: quota")

    session = store.get(session_id)
    assert session is not None
    assert (session.status, session.processing_error) == ("failed", "RuntimeError: quota")
    assert session.status_at is not None


def test_a_session_remembers_who_it_was_with_and_what_it_carried(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    session_id = store.start(
        model="m",
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
        senior_id=senior_id,
        carried_questions=["q1", "q2"],
    )

    session = store.get(session_id)
    assert session is not None
    assert session.senior_id == senior_id
    assert session.carried_questions == ["q1", "q2"]


# --- seniors ---------------------------------------------------------------


def test_a_senior_reads_back_as_entered(store: Store) -> None:
    senior_id = store.add_senior(
        name="田中ハル",
        name_reading="たなかはる",
        birth_year=1947,
        birthplace="長野",
        family=["孫のゆか"],
        language="ja",
        pronouns="she",
    )

    senior = store.get_senior(senior_id)

    assert senior is not None
    assert (senior.name, senior.name_reading, senior.birth_year) == ("田中ハル", "たなかはる", 1947)
    assert (senior.birthplace, senior.family, senior.language) == ("長野", ["孫のゆか"], "ja")
    assert senior.pronouns == "she"
    assert store.get_senior("nobody") is None
    # Nobody said: none is guessed.
    unsaid = store.get_senior(store.add_senior(name="佐藤茂"))
    assert unsaid is not None and unsaid.pronouns == ""


def test_a_visitor_persona_reads_back_as_one_with_an_id_nobody_can_guess(store: Store) -> None:
    visitor_id = store.add_senior(name="Alex", language="en", visitor=True)
    person_id = store.add_senior(name="田中ハル")

    visitor = store.get_senior(visitor_id)
    person = store.get_senior(person_id)

    assert visitor is not None and person is not None
    assert (visitor.visitor, person.visitor) == (True, False)
    assert len(visitor_id) >= 22  # 128 random bits: the link is the only key
    assert visitor.created_at is not None and person.created_at is not None


def test_seniors_are_listed_in_the_order_they_were_added(store: Store) -> None:
    first = store.add_senior(name="田中ハル")
    second = store.add_senior(name="Jean Dupont", language="fr")

    assert [s.id for s in store.list_seniors()] == [first, second]


# --- family questions --------------------------------------------------------


def test_family_questions_come_oldest_first_and_filter_by_status(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    other = store.add_senior(name="佐藤茂")
    first = store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")
    held = store.add_family_question(senior_id, asked_by="孫のゆか", text="戦争は?", status="held")
    second = store.add_family_question(senior_id, asked_by="娘", text="初任給は?")
    store.add_family_question(other, asked_by="息子", text="釣りは?")

    assert [q.id for q in store.family_questions(senior_id)] == [first, held, second]
    assert [q.id for q in store.family_questions(senior_id, status="pending")] == [first, second]


def test_a_question_asked_points_at_its_answer(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    question_id = store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")

    store.mark_question_asked(question_id, "session1", ["story1"])

    [question] = store.family_questions(senior_id)
    assert (question.status, question.asked_in_session) == ("asked", "session1")
    assert question.answer_story_ids == ["story1"]


def test_a_question_can_be_held_back(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    question_id = store.add_family_question(senior_id, asked_by="孫のゆか", text="戦争は?")

    store.set_question_status(question_id, "held")

    assert store.family_questions(senior_id, status="pending") == []


# --- stories and plans -----------------------------------------------------


def test_a_sessions_stories_are_replaced_whole_and_keep_their_order(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    session_id = started(store, senior_id)
    store.replace_stories(session_id, senior_id, [story("a", "工場"), story("b", "学校")])

    store.replace_stories(
        session_id, senior_id, [story("c", "結婚式"), story("d", "初任給"), story("e", "引越し")]
    )

    told = store.stories_for_session(session_id)
    assert [s.id for s in told] == ["c", "d", "e"]
    assert told[0].senior_id == senior_id
    assert told[0].session_id == session_id
    assert told[0].quotes == [Quote(text="父は工場をやっておりました。", turn=1)]
    assert (told[0].people, told[0].places) == (["父"], ["長野"])


def test_only_shared_stories_come_back_when_only_shared_are_asked_for(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    other = store.add_senior(name="佐藤茂")
    store.replace_stories(
        started(store, senior_id),
        senior_id,
        [story("a", "工場", "family"), story("b", "話したくないこと", "private")],
    )
    store.replace_stories(started(store, senior_id), senior_id, [story("c", "結婚式", "family")])
    store.replace_stories(started(store, other), other, [story("d", "釣り", "family")])

    assert {s.id for s in store.stories_for_senior(senior_id)} == {"a", "b", "c"}
    shared = store.stories_for_senior(senior_id, shared_only=True)
    assert {s.id for s in shared} == {"a", "c"}
    assert all(s.shared for s in shared)


def test_a_later_decision_changes_who_may_read_a_story(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    session_id = started(store, senior_id)
    waiting = replace(story("a", "工場"), asked_to_share=False)
    store.replace_stories(session_id, senior_id, [waiting, story("b", "学校", "family")])
    assert [s.asked_to_share for s in store.stories_for_session(session_id)] == [False, True]

    store.set_sharing("a", visibility="family", consent_quote="ええ、どうぞ。")
    store.set_sharing("b", visibility="private", consent_quote="")

    a, b = store.stories_for_session(session_id)
    assert (a.visibility, a.consent_quote, a.asked_to_share) == ("family", "ええ、どうぞ。", True)
    assert (b.visibility, b.consent_quote, b.asked_to_share) == ("private", "", True)
    assert [s.id for s in store.stories_for_senior(senior_id, shared_only=True)] == ["a"]


def test_a_plan_is_empty_until_one_is_saved(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    assert store.get_plan(senior_id).is_empty

    store.save_plan(
        senior_id,
        Plan(story_so_far="工場のお話。", next_questions=["初任給は?"], avoid_topics=["戦争"]),
    )

    plan = store.get_plan(senior_id)
    assert plan.story_so_far == "工場のお話。"
    assert (plan.next_questions, plan.avoid_topics) == (["初任給は?"], ["戦争"])


def test_translations_are_kept_per_person_and_added_to(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    other = store.add_senior(name="佐藤茂")
    assert store.translations(senior_id) == {}

    store.save_translations(senior_id, {"工場": "The factory"})
    store.save_translations(senior_id, {"お着物": "The kimono", "工場": "The weaving factory"})

    assert store.translations(senior_id) == {
        "工場": "The weaving factory",
        "お着物": "The kimono",
    }
    assert store.translations(other) == {}


# --- forgetting --------------------------------------------------------------


def test_a_person_can_be_forgotten_entirely(store: Store) -> None:
    senior_id = store.add_senior(name="田中ハル")
    kept = store.add_senior(name="佐藤茂")
    session_id = started(store, senior_id)
    store.finish(session_id, turns=[], audio=b"RIFFfake", duration_seconds=1.0, input_label="mic")
    store.save_audio_part(session_id, 0, b"left over")
    store.replace_stories(session_id, senior_id, [story("a", "工場", "family")])
    store.add_family_question(senior_id, asked_by="孫のゆか", text="お着物は?")
    store.save_plan(
        senior_id, Plan(story_so_far="工場。", next_questions=[], avoid_topics=["戦争"])
    )
    store.save_translations(senior_id, {"工場": "The factory"})
    other_session = started(store, kept)
    store.replace_stories(other_session, kept, [story("b", "釣り")])

    gone = store.forget_senior(senior_id)

    assert gone == {"sessions": 1, "stories": 1, "family_questions": 1, "recordings": 2}
    assert store.get_senior(senior_id) is None
    assert store.get(session_id) is None
    assert not store.has_audio(session_id)
    assert store.stories_for_senior(senior_id) == []
    assert store.family_questions(senior_id) == []
    assert store.get_plan(senior_id).is_empty
    assert store.translations(senior_id) == {}
    # Nobody else is touched.
    assert [s.id for s in store.list_seniors()] == [kept]
    assert [s.id for s in store.stories_for_senior(kept)] == ["b"]

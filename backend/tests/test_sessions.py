import datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from kataribe import brain
from kataribe.config import Settings, get_settings
from kataribe.gemini import InterviewTuning, SessionCredentials, build_live_config
from kataribe.main import create_app
from kataribe.store import FamilyQuestion, Plan, Quote, Store, Story, Turn


def client_with(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def stored(tmp_path: Path, **overrides: object) -> TestClient:
    """A client whose sessions land in a throwaway directory."""
    return client_with(Settings(data_dir=tmp_path, **overrides))  # type: ignore[arg-type]


def test_create_session_without_key_is_unavailable(tmp_path: Path) -> None:
    response = client_with(Settings(gemini_api_key="", data_dir=tmp_path)).post(
        "/api/sessions", json={}
    )

    assert response.status_code == 503


def test_create_session_rejects_unknown_voice(tmp_path: Path) -> None:
    response = client_with(Settings(gemini_api_key="test-key", data_dir=tmp_path)).post(
        "/api/sessions", json={"voice": "Nonexistent"}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("silence_ms", [199, 8001])
def test_create_session_rejects_silence_outside_tunable_range(
    silence_ms: int, tmp_path: Path
) -> None:
    response = client_with(Settings(gemini_api_key="test-key", data_dir=tmp_path)).post(
        "/api/sessions", json={"silence_duration_ms": silence_ms}
    )

    assert response.status_code == 422


def test_voices_are_listed(tmp_path: Path) -> None:
    response = client_with(Settings(data_dir=tmp_path)).get("/api/voices")

    assert response.status_code == 200
    assert "Sulafat" in response.json()


def test_live_config_pins_japanese_and_applies_tuning() -> None:
    config = build_live_config(InterviewTuning(voice="Gacrux", silence_duration_ms=2200))

    assert config.speech_config is not None
    assert config.speech_config.language_code == "ja-JP"
    assert config.response_modalities == [types.Modality.AUDIO]

    detection = config.realtime_input_config.automatic_activity_detection
    assert detection is not None
    assert detection.silence_duration_ms == 2200
    assert detection.end_of_speech_sensitivity == types.EndSensitivity.END_SENSITIVITY_LOW


def test_live_config_asks_for_word_timestamps_even_though_they_do_not_come_back() -> None:
    # The model ignores this today. Kept so offsets arrive free if that changes;
    # see the note in gemini.py before building anything on it.
    config = build_live_config(InterviewTuning())

    assert config.input_audio_transcription is not None
    assert config.input_audio_transcription.word_timestamp is True


def test_live_config_leaves_affective_dialog_off() -> None:
    # Setting it makes any ephemeral-token session reject realtime audio with
    # close code 1007, which is how the browser client connects.
    config = build_live_config(InterviewTuning())

    assert not config.enable_affective_dialog


def fake_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the real token mint; these tests are about storage, not Gemini."""
    monkeypatch.setattr(
        "kataribe.api.sessions.mint_session_credentials",
        lambda settings, tuning, context="": SessionCredentials(
            token="test-token",
            model="gemini-3.8-live",
            expires_at=datetime.datetime.now(datetime.UTC),
        ),
    )


def test_a_session_is_recorded_when_it_starts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_credentials(monkeypatch)
    client = stored(tmp_path, gemini_api_key="k")

    created = client.post("/api/sessions", json={"voice": "Gacrux"}).json()

    listed = client.get("/api/sessions").json()
    assert [s["id"] for s in listed] == [created["session_id"]]
    assert listed[0]["voice"] == "Gacrux"
    assert listed[0]["has_audio"] is False


def test_a_recording_can_be_uploaded_and_read_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_credentials(monkeypatch)
    client = stored(tmp_path, gemini_api_key="k")
    session_id = client.post("/api/sessions", json={}).json()["session_id"]

    upload = client.post(
        f"/api/sessions/{session_id}/recording",
        data={
            "transcript": json.dumps(
                [{"speaker": "senior", "text": "長野で生まれました", "started_at": 1.5}]
            ),
            "duration_seconds": "12.5",
            "input_label": "microphone",
        },
        files={"audio": ("session.wav", b"RIFFfake", "audio/wav")},
    )
    assert upload.status_code == 204

    detail = client.get(f"/api/sessions/{session_id}").json()
    assert detail["duration_seconds"] == 12.5
    assert detail["transcript"] == [
        {"speaker": "senior", "text": "長野で生まれました", "started_at": 1.5}
    ]
    assert client.get(f"/api/sessions/{session_id}/audio").content == b"RIFFfake"


def test_uploading_to_an_unknown_session_is_rejected(tmp_path: Path) -> None:
    response = stored(tmp_path).post(
        "/api/sessions/nope/recording",
        data={"transcript": "[]", "duration_seconds": "1"},
    )

    assert response.status_code == 404


def story_for(store_dir: Path, *, visibility: str) -> tuple[TestClient, str, str]:
    """A senior with one story at the given visibility, plus a session to play."""
    store = Store(store_dir)
    senior_id = store.add_senior(name="田中ハル", birth_year=1947, birthplace="長野")
    session_id = store.start(
        model="m",
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
        senior_id=senior_id,
    )
    store.finish(
        session_id,
        turns=[
            Turn(speaker="ai", text="こんにちは。", started_at=2.0),
            Turn(speaker="senior", text="長野で生まれました。", started_at=11.0),
        ],
        audio=None,
        duration_seconds=12.0,
        input_label="test",
    )
    store.replace_stories(
        session_id,
        senior_id,
        [
            Story(
                id="story1",
                senior_id=senior_id,
                session_id=session_id,
                title="生まれた村",
                summary="長野で生まれた。",
                life_stage="子供時代",
                approx_period="",
                people=[],
                places=["長野"],
                quotes=[Quote(text="長野で生まれました。", turn=1)],
                visibility=visibility,
            )
        ],
    )
    return stored(store_dir, gemini_api_key="k"), senior_id, session_id


def test_the_family_sees_a_story_that_was_agreed(tmp_path: Path) -> None:
    client, senior_id, _ = story_for(tmp_path, visibility="family")

    view = client.get(f"/api/family/{senior_id}").json()

    assert view["withheld"] == 0
    assert [c["life_stage"] for c in view["chapters"]] == ["子供時代"]
    assert view["chapters"][0]["stories"][0]["title"] == "生まれた村"


def test_the_family_never_sees_a_story_that_was_not(tmp_path: Path) -> None:
    client, senior_id, _ = story_for(tmp_path, visibility="private")

    view = client.get(f"/api/family/{senior_id}").json()

    assert view["chapters"] == []
    assert view["withheld"] == 1
    # Not even the title leaks through the count.
    assert "生まれた村" not in json.dumps(view, ensure_ascii=False)


def test_a_quote_carries_where_to_start_playing(tmp_path: Path) -> None:
    client, senior_id, session_id = story_for(tmp_path, visibility="family")

    quote = client.get(f"/api/family/{senior_id}").json()["chapters"][0]["stories"][0]["quotes"][0]

    assert quote["session_id"] == session_id
    # Turn 1 begins roughly where turn 0 ended.
    assert quote["seek_seconds"] == 2.0


def test_a_relative_can_ask_and_sees_it_waiting(tmp_path: Path) -> None:
    client, senior_id, _ = story_for(tmp_path, visibility="family")

    asked = client.post(
        f"/api/family/{senior_id}/questions",
        json={"asked_by": "孫のゆか", "text": "結婚式のときのお着物はどんなものでしたか?"},
    ).json()

    assert asked["status"] == "waiting"
    questions = client.get(f"/api/family/{senior_id}").json()["questions"]
    assert [q["text"] for q in questions] == ["結婚式のときのお着物はどんなものでしたか?"]


def test_a_held_question_looks_exactly_like_a_waiting_one(tmp_path: Path) -> None:
    # Held means it touches something she refused. Saying so to the family would
    # tell them what she refused, so to them it is simply still waiting.
    client, senior_id, _ = story_for(tmp_path, visibility="family")
    store = Store(tmp_path)
    store.add_family_question(senior_id, asked_by="孫のゆか", text="戦争のころは?", status="held")

    question = client.get(f"/api/family/{senior_id}").json()["questions"][0]

    assert question["status"] == "waiting"
    assert "held" not in json.dumps(question)


def test_an_answer_she_shared_comes_back_with_the_question(tmp_path: Path) -> None:
    client, senior_id, session_id = story_for(tmp_path, visibility="family")
    store = Store(tmp_path)
    question_id = store.add_family_question(senior_id, asked_by="孫のゆか", text="生まれた村は?")
    store.mark_question_asked(question_id, session_id, ["story1"])

    question = client.get(f"/api/family/{senior_id}").json()["questions"][0]

    assert question["status"] == "asked"
    assert question["answered_in"] == ["story1"]


def test_an_answer_is_shown_only_if_that_story_was_shared(tmp_path: Path) -> None:
    client, senior_id, session_id = story_for(tmp_path, visibility="private")
    store = Store(tmp_path)
    question_id = store.add_family_question(senior_id, asked_by="孫のゆか", text="生まれた村は?")
    private_story = store.stories_for_senior(senior_id)[0].id
    store.mark_question_asked(question_id, session_id, [private_story])

    question = client.get(f"/api/family/{senior_id}").json()["questions"][0]

    # They learn it was asked, and nothing about whether or what she answered.
    assert question["status"] == "asked"
    assert question["answered_in"] == []


def test_a_question_touching_a_refused_topic_is_held_yet_looks_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, senior_id, _ = story_for(tmp_path, visibility="family")
    store = Store(tmp_path)
    store.save_plan(senior_id, Plan(story_so_far="", next_questions=[], avoid_topics=["戦争"]))
    monkeypatch.setattr(
        brain, "screen", lambda settings, questions, avoid: {q.id for q in questions}
    )

    asked = client.post(
        f"/api/family/{senior_id}/questions",
        json={"asked_by": "孫のゆか", "text": "戦争のころはどこにいたの?"},
    ).json()

    assert asked["status"] == "waiting"
    assert [q.status for q in store.family_questions(senior_id)] == ["held"]


def test_a_question_that_cannot_be_screened_is_not_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Taking it anyway would leave it waiting, unchecked, to be put to her.
    client, senior_id, _ = story_for(tmp_path, visibility="family")
    store = Store(tmp_path)
    store.save_plan(senior_id, Plan(story_so_far="", next_questions=[], avoid_topics=["戦争"]))

    def unreachable(
        settings: Settings, questions: list[FamilyQuestion], avoid: list[str]
    ) -> set[str]:
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(brain, "screen", unreachable)

    response = client.post(
        f"/api/family/{senior_id}/questions",
        json={"asked_by": "孫のゆか", "text": "お着物は?"},
    )

    assert response.status_code == 503
    assert store.family_questions(senior_id) == []


def test_nothing_needs_screening_before_anything_was_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, senior_id, _ = story_for(tmp_path, visibility="family")

    def unexpected(
        settings: Settings, questions: list[FamilyQuestion], avoid: list[str]
    ) -> set[str]:
        raise AssertionError("screened with nothing to screen against")

    monkeypatch.setattr(brain, "screen", unexpected)

    response = client.post(
        f"/api/family/{senior_id}/questions",
        json={"asked_by": "孫のゆか", "text": "お着物は?"},
    )

    assert response.status_code == 200


@pytest.mark.parametrize("field", ["asked_by", "text"])
def test_a_blank_question_or_asker_is_refused(tmp_path: Path, field: str) -> None:
    client, senior_id, _ = story_for(tmp_path, visibility="family")
    question = {"asked_by": "孫のゆか", "text": "お着物は?", field: "   "}

    response = client.post(f"/api/family/{senior_id}/questions", json=question)

    assert response.status_code == 422


def test_a_question_for_nobody_is_refused(tmp_path: Path) -> None:
    response = stored(tmp_path).post(
        "/api/family/nope/questions", json={"asked_by": "孫のゆか", "text": "お着物は?"}
    )

    assert response.status_code == 404


def test_waiting_questions_reach_the_interviewer_with_who_asked() -> None:
    from kataribe.brain import context_for
    from kataribe.store import Senior

    senior = Senior(
        id="s", name="田中ハル", name_reading="", birth_year=None, birthplace="", family=[]
    )
    waiting = [
        FamilyQuestion(
            id=str(i),
            senior_id="s",
            asked_by="孫のゆか",
            text=f"質問{i}",
            status="pending",
            asked_in_session=None,
            answer_story_ids=[],
        )
        for i in range(2)
    ]

    context = context_for(senior, Plan("", [], []), waiting)

    assert "孫のゆかより: 質問0" in context
    assert "孫のゆかより: 質問1" in context


def test_a_session_carries_at_most_the_two_oldest_waiting_questions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A session is five to ten minutes; a queue of relatives' questions would
    # crowd out her own stories.
    seen: dict[str, str] = {}

    def mint(settings: Settings, tuning: InterviewTuning, context: str = "") -> SessionCredentials:
        seen["context"] = context
        return SessionCredentials(
            token="t", model="m", expires_at=datetime.datetime.now(datetime.UTC)
        )

    monkeypatch.setattr("kataribe.api.sessions.mint_session_credentials", mint)
    client, senior_id, _ = story_for(tmp_path, visibility="family")
    store = Store(tmp_path)
    for i in range(3):
        store.add_family_question(senior_id, asked_by="孫のゆか", text=f"質問{i}")
    store.add_family_question(senior_id, asked_by="孫のゆか", text="戦争のころは?", status="held")

    client.post("/api/sessions", json={"senior_id": senior_id})

    assert "質問0" in seen["context"] and "質問1" in seen["context"]
    assert "質問2" not in seen["context"]
    # And never a held one, whatever its age.
    assert "戦争" not in seen["context"]


def test_a_session_remembers_which_questions_it_carried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Processing judges only these, so that "asked" means the interviewer had it.
    fake_credentials(monkeypatch)
    client, senior_id, _ = story_for(tmp_path, visibility="family")
    store = Store(tmp_path)
    ids = [
        store.add_family_question(senior_id, asked_by="孫のゆか", text=f"質問{i}") for i in range(3)
    ]

    session_id = client.post("/api/sessions", json={"senior_id": senior_id}).json()["session_id"]

    session = store.get(session_id)
    assert session is not None
    assert session.carried_questions == ids[:2]

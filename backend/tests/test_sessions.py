import datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from kataribe import brain
from kataribe.clips import PAD_SECONDS
from kataribe.config import Settings, get_settings
from kataribe.gemini import InterviewTuning, SessionCredentials, build_live_config
from kataribe.main import create_app
from kataribe.store import FamilyQuestion, LocalStore, Plan, Quote, Story, Turn
from tests.wavs import channels_and_seconds, conversation_wav


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


def test_a_session_says_when_and_how_to_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The model keeps no clock. The screen tells it when, in the person's language.
    fake_credentials(monkeypatch)
    client = stored(tmp_path, gemini_api_key="k", close_after_seconds=300)

    created = client.post("/api/sessions", json={}).json()

    assert created["close_after_seconds"] == 300
    assert created["closing"].startswith("（そろそろお開きの時間です。")


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


def story_for(
    store_dir: Path, *, visibility: str, audio: bytes | None = None
) -> tuple[TestClient, str, str]:
    """A senior with one story at the given visibility, plus a session to play."""
    store = LocalStore(store_dir)
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
        audio=audio,
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


def test_the_family_page_says_when_a_conversation_is_being_written_up(tmp_path: Path) -> None:
    client, senior_id, session_id = story_for(tmp_path, visibility="family")
    store = LocalStore(tmp_path)

    store.set_status(session_id, "processing")
    writing = client.get(f"/api/family/{senior_id}").json()["writing"]
    store.set_status(session_id, "processed")
    written = client.get(f"/api/family/{senior_id}").json()["writing"]

    assert (writing, written) == (True, False)


def fake_translation(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Every batch sent to be translated, answered with "EN:" before each text."""
    sent: list[list[str]] = []

    def translate(settings: Settings, texts: list[str], language: object) -> list[str]:
        sent.append(texts)
        return [f"EN:{text}" for text in texts]

    monkeypatch.setattr("kataribe.brain.translate", translate)
    return sent


def test_a_family_page_in_japanese_comes_with_english_translated_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # So that someone without Japanese, such as a judge, can follow the page.
    client, senior_id, _ = story_for(tmp_path, visibility="family")
    sent = fake_translation(monkeypatch)

    first = client.get(f"/api/family/{senior_id}/translations").json()
    again = client.get(f"/api/family/{senior_id}/translations").json()

    assert first["長野で生まれました。"] == "EN:長野で生まれました。"
    assert first["生まれた村"] == "EN:生まれた村"
    assert first["田中ハル"] == "EN:田中ハル"
    assert again == first
    # Kept after the first reading, not translated on every one.
    assert len(sent) == 1


def test_only_what_the_page_shows_is_translated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, senior_id, _ = story_for(tmp_path, visibility="private")
    sent = fake_translation(monkeypatch)

    client.get(f"/api/family/{senior_id}/translations")

    # A private story's words never leave for a translation.
    assert "生まれた村" not in json.dumps(sent, ensure_ascii=False)


def test_a_page_that_cannot_be_translated_is_shown_without(tmp_path: Path) -> None:
    # The unit tests' own translation always fails.
    client, senior_id, _ = story_for(tmp_path, visibility="family")

    view = client.get(f"/api/family/{senior_id}").json()
    translations = client.get(f"/api/family/{senior_id}/translations")

    assert view["chapters"][0]["stories"][0]["title"] == "生まれた村"
    assert (translations.status_code, translations.json()) == (200, {})


def test_an_english_page_is_not_translated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent = fake_translation(monkeypatch)
    store = LocalStore(tmp_path)
    senior_id = store.add_senior(name="Alex", language="en", visitor=True)

    client = stored(tmp_path, gemini_api_key="k")
    translations = client.get(f"/api/family/{senior_id}/translations").json()

    assert (translations, sent) == ({}, [])


def test_the_showcase_page_takes_no_questions(tmp_path: Path) -> None:
    # Every visitor sees it: a question sent from it would wait forever, and
    # every visitor would read the others'.
    _, senior_id, _ = story_for(tmp_path, visibility="family")
    client = stored(tmp_path, showcase_senior=senior_id)

    view = client.get(f"/api/family/{senior_id}").json()
    sent = client.post(
        f"/api/family/{senior_id}/questions", json={"asked_by": "Judge", "text": "Hello?"}
    )

    assert view["showcase"] is True
    assert sent.status_code == 403
    assert LocalStore(tmp_path).family_questions(senior_id) == []


def test_a_family_page_knows_whether_it_is_a_visitors_own(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    visitor = store.add_senior(name="Alex", language="en", visitor=True)
    person = store.add_senior(name="田中ハル")
    client = stored(tmp_path)

    assert client.get(f"/api/family/{visitor}").json()["visitor"] is True
    assert client.get(f"/api/family/{person}").json()["visitor"] is False
    assert client.get(f"/api/family/{person}").json()["showcase"] is False


def test_a_quote_plays_their_voice_and_not_the_session(tmp_path: Path) -> None:
    # The interviewer greets at 0.5–2 s; she answers at 4–9 s.
    audio = conversation_wav(12.0, left=[(4.0, 9.0)], right=[(0.5, 2.0)])
    client, senior_id, session_id = story_for(tmp_path, visibility="family", audio=audio)

    view = client.get(f"/api/family/{senior_id}").json()
    quote = view["chapters"][0]["stories"][0]["quotes"][0]
    played = client.get(quote["audio"])

    assert played.status_code == 200
    assert played.headers["content-type"] == "audio/wav"
    channels, seconds = channels_and_seconds(played.content)
    assert channels == 1
    assert seconds == pytest.approx(5.0 + 2 * PAD_SECONDS, abs=0.05)
    # Nothing on the page leads to the whole recording, which also holds
    # whatever she kept to herself.
    assert session_id not in json.dumps(view)


def test_a_story_she_kept_private_has_no_voice_to_play(tmp_path: Path) -> None:
    audio = conversation_wav(12.0, left=[(4.0, 9.0)])
    client, senior_id, _ = story_for(tmp_path, visibility="private", audio=audio)

    played = client.get(f"/api/family/{senior_id}/stories/story1/quotes/0/audio")

    assert played.status_code == 404


def test_a_quote_plays_only_under_its_own_person(tmp_path: Path) -> None:
    audio = conversation_wav(12.0, left=[(4.0, 9.0)])
    client, _, _ = story_for(tmp_path, visibility="family", audio=audio)
    other = client.post("/api/seniors", json={"name": "佐藤茂"}).json()["id"]

    played = client.get(f"/api/family/{other}/stories/story1/quotes/0/audio")

    assert played.status_code == 404


def test_a_quote_with_no_recording_offers_nothing_to_play(tmp_path: Path) -> None:
    client, senior_id, _ = story_for(tmp_path, visibility="family")

    quote = client.get(f"/api/family/{senior_id}").json()["chapters"][0]["stories"][0]["quotes"][0]

    assert quote["audio"] is None
    assert client.get(f"/api/family/{senior_id}/stories/story1/quotes/0/audio").status_code == 404


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
    store = LocalStore(tmp_path)
    store.add_family_question(senior_id, asked_by="孫のゆか", text="戦争のころは?", status="held")

    question = client.get(f"/api/family/{senior_id}").json()["questions"][0]

    assert question["status"] == "waiting"
    assert "held" not in json.dumps(question)


def test_an_answer_she_shared_comes_back_with_the_question(tmp_path: Path) -> None:
    client, senior_id, session_id = story_for(tmp_path, visibility="family")
    store = LocalStore(tmp_path)
    question_id = store.add_family_question(senior_id, asked_by="孫のゆか", text="生まれた村は?")
    store.mark_question_asked(question_id, session_id, ["story1"])

    question = client.get(f"/api/family/{senior_id}").json()["questions"][0]

    assert question["status"] == "asked"
    assert question["answered_in"] == ["story1"]


def test_an_answer_is_shown_only_if_that_story_was_shared(tmp_path: Path) -> None:
    client, senior_id, session_id = story_for(tmp_path, visibility="private")
    store = LocalStore(tmp_path)
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
    store = LocalStore(tmp_path)
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
    store = LocalStore(tmp_path)
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
    store = LocalStore(tmp_path)
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
    store = LocalStore(tmp_path)
    ids = [
        store.add_family_question(senior_id, asked_by="孫のゆか", text=f"質問{i}") for i in range(3)
    ]

    session_id = client.post("/api/sessions", json={"senior_id": senior_id}).json()["session_id"]

    session = store.get(session_id)
    assert session is not None
    assert session.carried_questions == ids[:2]


def test_a_session_whose_reading_failed_can_be_read_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read: list[str] = []
    monkeypatch.setattr(
        "kataribe.api.sessions.process_session",
        lambda settings, store, session_id: read.append(session_id),
    )
    client, _, session_id = story_for(tmp_path, visibility="private")
    LocalStore(tmp_path).set_status(session_id, "failed", "RuntimeError: quota exhausted")
    assert client.get(f"/api/sessions/{session_id}").json()["can_process"] is True

    response = client.post(f"/api/sessions/{session_id}/process")

    assert response.status_code == 202
    assert read == [session_id]
    assert client.get(f"/api/sessions/{session_id}").json()["status"] == "queued"
    # And not a second time while that reading may still be going.
    assert client.post(f"/api/sessions/{session_id}/process").status_code == 409
    assert read == [session_id]


def test_a_session_being_read_is_not_started_twice(tmp_path: Path) -> None:
    client, _, session_id = story_for(tmp_path, visibility="private")
    LocalStore(tmp_path).set_status(session_id, "processing")

    response = client.post(f"/api/sessions/{session_id}/process")

    assert response.status_code == 409
    assert client.get("/api/sessions").json()[0]["can_process"] is False


def started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    fake_credentials(monkeypatch)
    client = stored(tmp_path, gemini_api_key="k")
    monkeypatch.setattr("kataribe.api.sessions.process_session", lambda *a: None)
    return client, client.post("/api/sessions", json={}).json()["session_id"]


def keep(client: TestClient, session_id: str, parts: int) -> int:
    return client.post(
        f"/api/sessions/{session_id}/recording",
        data={"transcript": "[]", "duration_seconds": "600", "audio_parts": str(parts)},
    ).status_code


def test_a_recording_too_big_for_one_request_arrives_in_parts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, session_id = started(tmp_path, monkeypatch)
    recording = conversation_wav(3.0, left=[(0.5, 2.5)])
    cuts = [0, 1000, 70_001, len(recording)]

    # Sent out of order, and one sent twice, as a retry would.
    for index in (2, 0, 1, 1):
        part = recording[cuts[index] : cuts[index + 1]]
        put = client.put(f"/api/sessions/{session_id}/recording/parts/{index}", content=part)
        assert put.status_code == 204

    assert keep(client, session_id, parts=3) == 204
    assert client.get(f"/api/sessions/{session_id}/audio").content == recording


def test_nothing_is_kept_while_a_part_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, session_id = started(tmp_path, monkeypatch)
    client.put(f"/api/sessions/{session_id}/recording/parts/0", content=b"RIFF")

    assert keep(client, session_id, parts=2) == 422
    # Not marked finished: the browser can send the missing part and try again.
    assert client.get(f"/api/sessions/{session_id}").json()["duration_seconds"] is None
    client.put(f"/api/sessions/{session_id}/recording/parts/1", content=b"fake")
    assert keep(client, session_id, parts=2) == 204
    assert client.get(f"/api/sessions/{session_id}/audio").content == b"RIFFfake"


def test_a_kept_recording_takes_no_more_parts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, session_id = started(tmp_path, monkeypatch)
    client.put(f"/api/sessions/{session_id}/recording/parts/0", content=b"RIFFfake")
    keep(client, session_id, parts=1)

    late = client.put(f"/api/sessions/{session_id}/recording/parts/0", content=b"other")

    assert late.status_code == 409
    assert client.get(f"/api/sessions/{session_id}/audio").content == b"RIFFfake"


def test_a_part_over_the_limit_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, session_id = started(tmp_path, monkeypatch)
    monkeypatch.setattr("kataribe.api.sessions.PART_LIMIT", 4)

    put = client.put(f"/api/sessions/{session_id}/recording/parts/0", content=b"RIFFfake")

    assert put.status_code == 413

"""The start page: a stranger, such as a judge, makes a persona of their own.

Each visitor gets their own, since memory is per person: a shared one would greet
the second visitor with the first one's memories. Its id is the only key to it,
so it must not be guessable, and the day's visitors share a limit, since every
conversation is paid for.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from kataribe.config import Settings, get_settings
from kataribe.main import create_app
from kataribe.store import LocalStore

QUESTION = {
    "name": "Alex",
    "language": "en",
    "asked_by": "Your family",
    "question": "Which place from your childhood do you still think about?",
}


def client_for(tmp_path: Path, **overrides: object) -> TestClient:
    settings = Settings(data_dir=tmp_path, **overrides)  # type: ignore[arg-type]
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_the_start_page_offers_what_is_configured(tmp_path: Path) -> None:
    client = client_for(
        tmp_path,
        try_languages="en, ja",
        showcase_senior="showcase1",
        video_url="https://youtu.be/demo",
    )

    start = client.get("/api/try").json()

    assert start["languages"] == [
        {"code": "en", "endonym": "English"},
        {"code": "ja", "endonym": "日本語"},
    ]
    assert (start["showcase"], start["video"], start["open"]) == (
        "showcase1",
        "https://youtu.be/demo",
        True,
    )
    assert start["repo"].startswith("https://github.com/")


def test_japanese_is_not_offered_until_it_is_configured(tmp_path: Path) -> None:
    # It joins once a native speaker has reviewed it.
    client = client_for(tmp_path)

    assert [lang["code"] for lang in client.get("/api/try").json()["languages"]] == ["en"]
    assert client.post("/api/try", json={**QUESTION, "language": "ja"}).status_code == 422
    assert client.post("/api/try", json={**QUESTION, "language": "fr"}).status_code == 422


def test_a_visitor_gets_a_persona_of_their_own_that_cannot_be_guessed(tmp_path: Path) -> None:
    client = client_for(tmp_path)

    made = client.post("/api/try", json=QUESTION)

    assert made.status_code == 200
    persona_id = made.json()["id"]
    assert len(persona_id) >= 22  # 128 random bits
    senior = LocalStore(tmp_path).get_senior(persona_id)
    assert senior is not None
    assert (senior.name, senior.language, senior.visitor) == ("Alex", "en", True)
    # Their screen is theirs to use.
    assert client.get(f"/api/talk/{persona_id}").json()["visitor"] is True


def test_two_visitors_never_share_a_persona(tmp_path: Path) -> None:
    client = client_for(tmp_path)

    first = client.post("/api/try", json=QUESTION).json()["id"]
    second = client.post("/api/try", json=QUESTION).json()["id"]

    assert first != second


def test_their_first_conversation_opens_with_the_family_question(tmp_path: Path) -> None:
    client = client_for(tmp_path)

    persona_id = client.post("/api/try", json=QUESTION).json()["id"]

    [waiting] = LocalStore(tmp_path).family_questions(persona_id, status="pending")
    assert (waiting.asked_by, waiting.text) == (QUESTION["asked_by"], QUESTION["question"])


def test_a_visitor_may_leave_no_question(tmp_path: Path) -> None:
    client = client_for(tmp_path)

    persona_id = client.post(
        "/api/try", json={**QUESTION, "asked_by": "", "question": "  "}
    ).json()["id"]

    assert LocalStore(tmp_path).family_questions(persona_id) == []


def test_a_question_without_anyone_asking_it_is_refused(tmp_path: Path) -> None:
    # The interviewer always says who is asking.
    client = client_for(tmp_path)

    assert client.post("/api/try", json={**QUESTION, "asked_by": " "}).status_code == 422


def test_a_visitor_without_a_name_is_refused(tmp_path: Path) -> None:
    client = client_for(tmp_path)

    assert client.post("/api/try", json={**QUESTION, "name": "  "}).status_code == 422


def test_visitors_share_a_limit_on_new_personas(tmp_path: Path) -> None:
    client = client_for(tmp_path, visitor_personas_per_day=2)

    statuses = [client.post("/api/try", json=QUESTION).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]
    assert client.get("/api/try").json()["open"] is False


def test_the_start_page_says_when_todays_conversations_are_used_up(tmp_path: Path) -> None:
    client = client_for(tmp_path, visitor_sessions_per_day=1)
    store = LocalStore(tmp_path)
    persona_id = client.post("/api/try", json=QUESTION).json()["id"]
    team_person = store.add_senior(name="田中ハル")

    def talk(senior_id: str) -> None:
        store.start(
            model="m",
            voice="Sulafat",
            silence_duration_ms=1500,
            end_of_speech_sensitivity="LOW",
            senior_id=senior_id,
        )

    # Only visitors' conversations count against visitors.
    talk(team_person)
    assert client.get("/api/try").json()["open"] is True
    talk(persona_id)
    assert client.get("/api/try").json()["open"] is False

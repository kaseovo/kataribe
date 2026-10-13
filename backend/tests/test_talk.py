"""Who may use a senior's screen, and how much.

A stranger may talk only to a visitor persona, the kind made from the start page,
and visitors share a few conversations a day. Anyone else's screen asks for the
team password: whoever talks there adds to that person's life story, which their
family reads.

A visitor's screen also waits for the writing-up, and asks on screen about any
story the interviewer never got to ask about.
"""

import base64
import datetime
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kataribe.access import is_public
from kataribe.config import Settings, get_settings
from kataribe.gemini import SessionCredentials
from kataribe.languages import get
from kataribe.main import create_app
from kataribe.store import LocalStore, Quote, Story, Turn
from tests.test_sessions import fake_credentials

TEAM = {"Authorization": "Basic " + base64.b64encode(b"team:pw").decode()}


def deployed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, per_day: int = 20
) -> tuple[TestClient, str, str]:
    """The app as deployed, with one visitor persona and one real person."""
    store = LocalStore(tmp_path)
    demo = store.add_senior(name="Alex", language="en", visitor=True)
    real = store.add_senior(name="佐藤茂")
    settings = Settings(
        data_dir=tmp_path,
        gemini_api_key="k",
        team_password="pw",
        visitor_sessions_per_day=per_day,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    fake_credentials(monkeypatch)
    monkeypatch.setattr("kataribe.api.sessions.process_session", lambda *a: None)
    return TestClient(app), demo, real


def test_the_screen_and_its_api_are_reachable_without_signing_in() -> None:
    assert is_public("/talk/abc")
    assert is_public("/api/talk/abc")
    assert is_public("/api/talk/abc/sessions/s1/recording/parts/0")


def test_a_visitor_can_talk_to_their_own_persona(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)

    assert client.get(f"/api/talk/{demo}").json() == {
        "name": "Alex",
        "language": "en",
        "visitor": True,
    }
    started = client.post(f"/api/talk/{demo}/sessions")

    assert started.status_code == 200
    session = LocalStore(tmp_path).get(started.json()["session_id"])
    assert session is not None and session.senior_id == demo


def test_a_visitor_is_asked_to_sign_in_for_anyone_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, real = deployed(tmp_path, monkeypatch)

    someone = client.get(f"/api/talk/{real}")
    nobody = client.get("/api/talk/nobody")

    assert someone.status_code == 401
    assert someone.headers["WWW-Authenticate"].startswith("Basic")
    # Asked the same way whether or not they exist.
    assert (nobody.status_code, nobody.text) == (someone.status_code, someone.text)
    assert client.post(f"/api/talk/{real}/sessions").status_code == 401


def test_the_team_can_talk_to_anyone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, real = deployed(tmp_path, monkeypatch)

    person = client.get(f"/api/talk/{real}", headers=TEAM).json()
    assert (person["name"], person["visitor"]) == ("佐藤茂", False)
    assert client.post(f"/api/talk/{real}/sessions", headers=TEAM).status_code == 200
    assert client.get("/api/talk/nobody", headers=TEAM).status_code == 404


def test_visitors_share_a_few_conversations_a_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch, per_day=2)
    other = LocalStore(tmp_path).add_senior(name="Sam", language="en", visitor=True)

    statuses = [
        client.post(f"/api/talk/{demo}/sessions").status_code,
        client.post(f"/api/talk/{other}/sessions").status_code,
        client.post(f"/api/talk/{demo}/sessions").status_code,
    ]

    # Counted across every visitor, since each judge has a persona of their own.
    assert statuses == [200, 200, 429]
    # The team is not held back.
    assert client.post(f"/api/talk/{demo}/sessions", headers=TEAM).status_code == 200


def test_a_visitor_is_cued_to_close_sooner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A visitor talks for two or three minutes. At six, the question about
    # sharing would never come, and their family page would stay empty.
    client, demo, real = deployed(tmp_path, monkeypatch)

    visitor = client.post(f"/api/talk/{demo}/sessions").json()
    person = client.post(f"/api/talk/{real}/sessions", headers=TEAM).json()

    assert visitor["close_after_seconds"] == 120
    assert person["close_after_seconds"] == 360


def test_a_visitor_is_asked_whether_to_go_on_then_about_sharing_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A judge lost the question about sharing in the middle of the full close:
    # thanks, the question, next time's topic and goodbye, in one breath. So a
    # visitor's clock asks whether to go on, and the question comes on its own.
    client, demo, real = deployed(tmp_path, monkeypatch)
    prompts: list[str] = []
    monkeypatch.setattr(
        "kataribe.api.sessions.mint_session_credentials",
        lambda settings, tuning, context="": (
            prompts.append(context)
            or SessionCredentials(
                token="t", model="m", expires_at=datetime.datetime.now(datetime.UTC)
            )
        ),
    )

    visitor = client.post(f"/api/talk/{demo}/sessions").json()
    person = client.post(f"/api/talk/{real}/sessions", headers=TEAM).json()

    english, japanese = get("en"), get("ja")
    assert visitor["check_in"] == english.visitor_check_in
    assert visitor["closing"] == english.visitor_finish
    assert english.visitor_rules in prompts[0]
    # A senior's close is the one the native-speaker review is judging.
    assert person["check_in"] == ""
    assert person["closing"] == japanese.closing
    assert japanese.visitor_rules not in prompts[1]


def test_a_conversation_is_kept_only_under_its_own_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, real = deployed(tmp_path, monkeypatch)
    mine = client.post(f"/api/talk/{demo}/sessions").json()["session_id"]
    theirs = client.post("/api/sessions", json={"senior_id": real}, headers=TEAM).json()[
        "session_id"
    ]

    kept = client.put(f"/api/talk/{demo}/sessions/{mine}/recording/parts/0", content=b"RIFFfake")
    finished = client.post(
        f"/api/talk/{demo}/sessions/{mine}/recording",
        data={"transcript": "[]", "duration_seconds": "5", "audio_parts": "1"},
    )
    assert (kept.status_code, finished.status_code) == (204, 204)
    assert client.get(f"/api/sessions/{mine}/audio", headers=TEAM).content == b"RIFFfake"

    # Reaching someone else's session through the demo persona's screen.
    stray = client.put(f"/api/talk/{demo}/sessions/{theirs}/recording/parts/0", content=b"x")
    assert stray.status_code == 404


# --- after the conversation, on a visitor's screen ---------------------------------


def story(story_id: str, *, visibility: str = "private", asked: bool = False) -> Story:
    return Story(
        id=story_id,
        senior_id="",
        session_id="",
        title=f"Story {story_id}",
        summary="",
        life_stage="子供時代",
        approx_period="",
        people=[],
        places=[],
        quotes=[Quote(text="We lived by the river.", turn=1)],
        visibility=visibility,
        consent_quote="Yes, they may." if visibility == "family" else "",
        asked_to_share=asked,
    )


def told(store_dir: Path, senior_id: str, stories: list[Story], status: str) -> str:
    """A conversation that ended, with its stories and where its writing-up is."""
    store = LocalStore(store_dir)
    session_id = store.start(
        model="m",
        voice="Sulafat",
        silence_duration_ms=1500,
        end_of_speech_sensitivity="LOW",
        senior_id=senior_id,
    )
    store.finish(
        session_id,
        turns=[Turn(speaker="senior", text="We lived by the river.", started_at=1.0)],
        audio=None,
        duration_seconds=90,
        input_label="test",
    )
    store.replace_stories(session_id, senior_id, stories)
    store.set_status(session_id, status)
    return session_id


@pytest.mark.parametrize(
    ("status", "state"),
    [
        ("recorded", "writing"),
        ("queued", "writing"),
        ("processing", "writing"),
        ("processed", "written"),
        ("failed", "failed"),
    ],
)
def test_the_end_screen_follows_the_writing_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str, state: str
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)
    session_id = told(tmp_path, demo, [story("a", visibility="family", asked=True)], status)

    seen = client.get(f"/api/talk/{demo}/sessions/{session_id}").json()

    assert seen["state"] == state
    assert seen["shared"] == (1 if state == "written" else 0)


def test_a_writing_up_that_stalled_is_reported_as_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Lost to a restart: it will never finish on its own, so the screen must not
    # say it is still coming.
    client, demo, _ = deployed(tmp_path, monkeypatch)
    session_id = told(tmp_path, demo, [], "processing")
    long_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10)
    with sqlite3.connect(tmp_path / "kataribe.db") as db:
        db.execute(
            "UPDATE sessions SET status_at = ? WHERE id = ?", (long_ago.isoformat(), session_id)
        )

    assert client.get(f"/api/talk/{demo}/sessions/{session_id}").json()["state"] == "failed"


def test_only_stories_never_asked_about_are_offered_on_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)
    stories = [
        story("shared", visibility="family", asked=True),
        story("kept", asked=True),  # asked aloud, and kept private
        story("unasked"),
    ]
    session_id = told(tmp_path, demo, stories, "processed")

    seen = client.get(f"/api/talk/{demo}/sessions/{session_id}").json()

    assert seen["unasked"] == [{"id": "unasked", "title": "Story unasked"}]


def test_sharing_on_screen_reaches_only_the_stories_never_asked_about(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)
    session_id = told(tmp_path, demo, [story("kept", asked=True), story("unasked")], "processed")

    chosen = client.post(f"/api/talk/{demo}/sessions/{session_id}/sharing", json={"share": True})

    assert chosen.json() == {"state": "written", "shared": 1, "unasked": []}
    store = LocalStore(tmp_path)
    visibility = {s.id: s.visibility for s in store.stories_for_session(session_id)}
    # What they said aloud stands, whatever they press.
    assert visibility == {"kept": "private", "unasked": "family"}
    session = store.get(session_id)
    assert session is not None and session.screen_consent == "shared"
    assert session.screen_consent_at is not None


def test_keeping_it_private_on_screen_settles_the_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)
    session_id = told(tmp_path, demo, [story("unasked")], "processed")

    client.post(f"/api/talk/{demo}/sessions/{session_id}/sharing", json={"share": False})

    store = LocalStore(tmp_path)
    [kept] = store.stories_for_session(session_id)
    # Private, and asked: the next conversation does not ask it again.
    assert (kept.visibility, kept.asked_to_share) == ("private", True)
    session = store.get(session_id)
    assert session is not None and session.screen_consent == "private"


def test_keep_it_private_pressed_while_closing_has_the_last_word(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Said yes aloud, then pressed Keep it private before it ended.
    client, demo, _ = deployed(tmp_path, monkeypatch)
    agreed = story("agreed", visibility="family", asked=True)
    session_id = told(tmp_path, demo, [agreed, story("unasked")], "processed")

    client.post(
        f"/api/talk/{demo}/sessions/{session_id}/sharing",
        json={"share": False, "everything": True},
    )

    stories = LocalStore(tmp_path).stories_for_session(session_id)
    assert [s.visibility for s in stories] == ["private", "private"]


def test_share_pressed_while_closing_never_overrides_a_no_said_aloud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)
    declined = story("declined", asked=True)
    session_id = told(tmp_path, demo, [declined, story("unasked")], "processed")

    client.post(
        f"/api/talk/{demo}/sessions/{session_id}/sharing",
        json={"share": True, "everything": True},
    )

    stories = LocalStore(tmp_path).stories_for_session(session_id)
    assert [s.visibility for s in stories] == ["private", "family"]


def test_nothing_is_chosen_before_the_writing_up_is_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)
    session_id = told(tmp_path, demo, [story("unasked")], "processing")

    chosen = client.post(f"/api/talk/{demo}/sessions/{session_id}/sharing", json={"share": True})

    assert chosen.status_code == 409


def test_a_real_persons_screen_has_no_end_screen_to_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # They are asked in their next conversation, as the product means them to be.
    client, _, real = deployed(tmp_path, monkeypatch)
    session_id = told(tmp_path, real, [story("unasked")], "processed")

    seen = client.get(f"/api/talk/{real}/sessions/{session_id}", headers=TEAM)
    chosen = client.post(
        f"/api/talk/{real}/sessions/{session_id}/sharing", json={"share": True}, headers=TEAM
    )

    assert (seen.status_code, chosen.status_code) == (404, 404)


def test_a_visitor_reaches_only_their_own_conversations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)
    other = LocalStore(tmp_path).add_senior(name="Sam", language="en", visitor=True)
    theirs = told(tmp_path, other, [story("unasked")], "processed")

    seen = client.get(f"/api/talk/{demo}/sessions/{theirs}")
    chosen = client.post(f"/api/talk/{demo}/sessions/{theirs}/sharing", json={"share": True})

    assert (seen.status_code, chosen.status_code) == (404, 404)

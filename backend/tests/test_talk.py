"""Who may use a senior's screen, and how much.

A visitor may talk only to a demo persona, and only so often a day. Anyone else's
screen asks for the team password: whoever talks there adds to that person's
life story, which their family reads.
"""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kataribe.access import is_public
from kataribe.config import Settings, get_settings
from kataribe.main import create_app
from kataribe.store import LocalStore
from tests.test_sessions import fake_credentials

TEAM = {"Authorization": "Basic " + base64.b64encode(b"team:pw").decode()}


def deployed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, per_day: int = 20
) -> tuple[TestClient, str, str]:
    """The app as deployed, with one demo persona open to visitors and one real person."""
    store = LocalStore(tmp_path)
    demo = store.add_senior(name="田中ハル")
    real = store.add_senior(name="佐藤茂")
    settings = Settings(
        data_dir=tmp_path,
        gemini_api_key="k",
        team_password="pw",
        visitor_seniors=f" {demo} ,",
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


def test_a_visitor_can_talk_to_a_demo_persona(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch)

    assert client.get(f"/api/talk/{demo}").json() == {"name": "田中ハル", "language": "ja"}
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

    assert client.get(f"/api/talk/{real}", headers=TEAM).json()["name"] == "佐藤茂"
    assert client.post(f"/api/talk/{real}/sessions", headers=TEAM).status_code == 200
    assert client.get("/api/talk/nobody", headers=TEAM).status_code == 404


def test_a_visitor_gets_a_few_conversations_a_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, demo, _ = deployed(tmp_path, monkeypatch, per_day=2)

    statuses = [client.post(f"/api/talk/{demo}/sessions").status_code for _ in range(3)]

    assert statuses == [200, 200, 429]
    # The team is not counted, nor held back.
    assert client.post(f"/api/talk/{demo}/sessions", headers=TEAM).status_code == 200


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

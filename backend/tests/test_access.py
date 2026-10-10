"""What a stranger can reach on the public URL: a family page, and nothing else."""

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kataribe.config import Settings, get_settings
from kataribe.main import create_app
from kataribe.store import LocalStore


def deployed(tmp_path: Path, password: str = "pw") -> tuple[TestClient, str]:
    """A client against the app as deployed: password set, frontend served."""
    pages = tmp_path / "static"
    (pages / "assets").mkdir(parents=True)
    (pages / "index.html").write_text("<html>kataribe</html>")
    (pages / "assets" / "index-abc.js").write_text("console.log('kataribe')")
    (pages / "capture-processor.js").write_text("registerProcessor('capture-processor', class {})")
    (tmp_path / "secret.txt").write_text("not for anyone")

    settings = Settings(data_dir=tmp_path / "data", static_dir=pages, team_password=password)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    senior_id = LocalStore(tmp_path / "data").add_senior(name="田中ハル")
    return TestClient(app), senior_id


def basic(password: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"team:{password}".encode()).decode()}


@pytest.mark.parametrize(
    "path",
    ["/", "/api/sessions", "/api/seniors", "/api/sessions/abc/audio", "/api/voices"],
)
def test_the_console_and_its_data_are_closed_to_strangers(tmp_path: Path, path: str) -> None:
    client, _ = deployed(tmp_path)

    response = client.get(path)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic")


def test_a_session_cannot_be_started_by_a_stranger(tmp_path: Path) -> None:
    client, _ = deployed(tmp_path)

    assert client.post("/api/sessions", json={}).status_code == 401


def test_the_team_gets_in_with_the_password(tmp_path: Path) -> None:
    client, _ = deployed(tmp_path)

    assert client.get("/api/sessions", headers=basic("pw")).status_code == 200
    assert client.get("/", headers=basic("pw")).text == "<html>kataribe</html>"


def test_a_wrong_password_is_a_stranger(tmp_path: Path) -> None:
    client, _ = deployed(tmp_path)

    assert client.get("/api/sessions", headers=basic("guess")).status_code == 401
    assert client.get("/api/sessions", headers={"Authorization": "Basic !!!"}).status_code == 401


def test_a_relative_reaches_the_family_page_with_nothing_to_sign_in_to(tmp_path: Path) -> None:
    client, senior_id = deployed(tmp_path)

    assert client.get(f"/family/{senior_id}").text == "<html>kataribe</html>"
    assert client.get("/assets/index-abc.js").status_code == 200
    # Loaded by the browser without the password, for any page that listens.
    assert client.get("/capture-processor.js").status_code == 200
    assert client.get(f"/api/family/{senior_id}").json()["senior"]["name"] == "田中ハル"


def test_a_relative_can_send_a_question(tmp_path: Path) -> None:
    client, senior_id = deployed(tmp_path)

    sent = client.post(
        f"/api/family/{senior_id}/questions", json={"asked_by": "孫のゆか", "text": "お着物は?"}
    )

    assert sent.status_code == 200


def test_an_unknown_api_path_is_not_answered_with_the_page(tmp_path: Path) -> None:
    client, _ = deployed(tmp_path)

    assert client.get("/api/nothing", headers=basic("pw")).status_code == 404


def test_the_page_never_serves_a_file_from_outside_it(tmp_path: Path) -> None:
    client, _ = deployed(tmp_path)

    response = client.get("/..%2Fsecret.txt", headers=basic("pw"))

    assert "not for anyone" not in response.text


def test_without_a_password_everything_is_open(tmp_path: Path) -> None:
    client, _ = deployed(tmp_path, password="")

    assert client.get("/api/sessions").status_code == 200

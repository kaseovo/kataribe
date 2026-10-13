"""Unit tests never reach Gemini.

A family page in a language other than English translates itself when it is
read, so that call is refused here; a test about translation puts its own in.
"""

import pytest


@pytest.fixture(autouse=True)
def no_translation(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live"):
        return

    def refuse(*_: object, **__: object) -> list[str]:
        raise RuntimeError("No Gemini in unit tests")

    monkeypatch.setattr("kataribe.brain.translate", refuse)

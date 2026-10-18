from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="KATARIBE_", extra="ignore")

    gemini_api_key: str = ""
    live_model: str = "gemini-3.8-live"
    text_model: str = "gemini-3.8-flash"
    storage: Literal["local", "cloud"] = "local"
    """local: SQLite and files under data_dir. cloud: Firestore and Cloud Storage,
    for Cloud Run, whose own disk does not survive a restart."""
    data_dir: Path = Path("var")
    gcp_project: str | None = None
    """For cloud storage. Unset, the project the credentials belong to."""
    firestore_database: str = "(default)"
    recordings_bucket: str = ""
    allowed_origins: list[str] = ["http://localhost:5173"]
    static_dir: Path | None = None
    """The built frontend, served by the API itself when deployed. Unset in
    development, where Vite serves it and proxies /api here."""
    close_after_seconds: int = 360
    """When the screen tells the interviewer it is time to close. Five to ten
    minutes is the session the product means; the close takes a minute more."""
    team_password: str = ""
    """Closes everything but the start page, the family pages and visitors'
    screens. Unset, everything is open."""

    # --- strangers trying it from the start page, such as judges
    try_languages: str = "en"
    """Comma-separated languages a visitor may pick. Japanese joins once a native
    speaker has reviewed it; until then a visitor hearing it does more harm than
    one not hearing it."""
    visitor_sessions_per_day: int = 30
    """Across every visitor, counted in Japan time. Each conversation is paid for,
    about ten US cents."""
    visitor_personas_per_day: int = 100
    """Across every visitor. Making one costs nothing, but nothing else stops a
    script making them forever."""
    visitor_close_after_seconds: int = 120
    """A visitor talks for two or three minutes. Left to the six-minute cue, the
    question about sharing would never come and their family page would stay
    empty. At this point a visitor is asked whether to go on, not closed on, so
    it can come early."""
    showcase_senior: str = ""
    """The persona whose family page the start page shows: stories from the demo
    take, read-only."""
    video_url: str = ""
    repo_url: str = "https://github.com/kaseovo/kataribe"

    @property
    def visitor_languages(self) -> list[str]:
        return [code.strip() for code in self.try_languages.split(",") if code.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

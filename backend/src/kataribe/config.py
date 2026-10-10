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
    team_password: str = ""
    """Closes everything but the family pages. Unset, everything is open."""
    visitor_seniors: str = ""
    """Comma-separated ids of demo personas whose talk screen strangers may use.
    Never a real person: whoever talks there adds to that person's story."""
    visitor_sessions_per_day: int = 20
    """Per persona, counted in Japan time. Each conversation is paid for."""

    @property
    def visitors(self) -> set[str]:
        return {s.strip() for s in self.visitor_seniors.split(",") if s.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

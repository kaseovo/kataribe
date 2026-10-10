"""Where sessions, stories, plans and recordings live.

`Store` is the seam: nothing above this module knows where anything is kept.
`LocalStore`, here, keeps records in SQLite and recordings on disk, for
development and tests. The deployed app keeps them in Firestore and Cloud
Storage, behind the same interface.

Recordings are handed out as open files rather than paths, so they can live
somewhere that is not a disk, and be read a range at a time: a ten-minute
session is close to 60 MB, and a quote needs a few seconds of it.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol

SCHEMA = """
CREATE TABLE IF NOT EXISTS seniors (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    name_reading TEXT NOT NULL DEFAULT '',
    birth_year   INTEGER,
    birthplace   TEXT NOT NULL DEFAULT '',
    family       TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id                        TEXT PRIMARY KEY,
    started_at                TEXT NOT NULL,
    ended_at                  TEXT,
    model                     TEXT NOT NULL,
    voice                     TEXT NOT NULL,
    silence_duration_ms       INTEGER NOT NULL,
    end_of_speech_sensitivity TEXT NOT NULL,
    input_label               TEXT NOT NULL DEFAULT 'microphone',
    duration_seconds          REAL,
    transcript                TEXT
);

CREATE TABLE IF NOT EXISTS stories (
    id            TEXT PRIMARY KEY,
    senior_id     TEXT NOT NULL,
    session_id    TEXT NOT NULL,
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL,
    life_stage    TEXT NOT NULL,
    approx_period TEXT NOT NULL DEFAULT '',
    people        TEXT NOT NULL DEFAULT '[]',
    places        TEXT NOT NULL DEFAULT '[]',
    quotes        TEXT NOT NULL DEFAULT '[]',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS family_questions (
    id               TEXT PRIMARY KEY,
    senior_id        TEXT NOT NULL,
    asked_by         TEXT NOT NULL,
    text             TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',
    asked_in_session TEXT,
    answer_story_ids TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    senior_id      TEXT PRIMARY KEY,
    story_so_far   TEXT NOT NULL DEFAULT '',
    next_questions TEXT NOT NULL DEFAULT '[]',
    avoid_topics   TEXT NOT NULL DEFAULT '[]',
    updated_at     TEXT NOT NULL
);
"""

# Added after the first sessions were recorded, so they arrive by migration.
LATER_COLUMNS = {
    "seniors": {"language": "TEXT NOT NULL DEFAULT 'ja'"},
    # Private unless the person said otherwise, and said so in words we kept.
    "stories": {
        "visibility": "TEXT NOT NULL DEFAULT 'private'",
        "consent_quote": "TEXT NOT NULL DEFAULT ''",
    },
    "sessions": {
        "senior_id": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'recorded'",
        "processing_error": "TEXT",
        # The family questions this session's interviewer was given. Only these
        # can have been put to the person, so only these are judged afterwards.
        "carried_questions": "TEXT NOT NULL DEFAULT '[]'",
        # When the status last changed, so a reading that stalled can be told
        # from one still going.
        "status_at": "TEXT",
    },
}

LIFE_STAGES = ("子供時代", "学校", "仕事", "結婚", "子育て", "晩年")


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str
    started_at: float


@dataclass(frozen=True)
class Quote:
    text: str
    turn: int


@dataclass(frozen=True)
class Story:
    id: str
    senior_id: str
    session_id: str
    title: str
    summary: str
    life_stage: str
    approx_period: str
    people: list[str]
    places: list[str]
    quotes: list[Quote]
    visibility: str = "private"
    consent_quote: str = ""

    @property
    def shared(self) -> bool:
        return self.visibility == "family"


@dataclass(frozen=True)
class Senior:
    id: str
    name: str
    name_reading: str
    birth_year: int | None
    birthplace: str
    family: list[str]
    language: str = "ja"


@dataclass(frozen=True)
class FamilyQuestion:
    """A question a relative wants put to the senior.

    `status` is one of:
      pending — waiting to be asked
      held    — touches a topic the senior has refused, so it is never put to
                them; relatives see it as pending, because saying otherwise
                would reveal what was refused
      asked   — the interviewer raised it in a session
    """

    id: str
    senior_id: str
    asked_by: str
    text: str
    status: str
    asked_in_session: str | None
    answer_story_ids: list[str]


@dataclass(frozen=True)
class Plan:
    story_so_far: str
    next_questions: list[str]
    avoid_topics: list[str]

    @property
    def is_empty(self) -> bool:
        return not (self.story_so_far or self.next_questions)


@dataclass(frozen=True)
class Session:
    id: str
    started_at: datetime
    ended_at: datetime | None
    model: str
    voice: str
    silence_duration_ms: int
    end_of_speech_sensitivity: str
    input_label: str
    duration_seconds: float | None
    turns: list[Turn]
    senior_id: str | None = None
    status: str = "recorded"
    processing_error: str | None = None
    carried_questions: list[str] = field(default_factory=list)
    status_at: datetime | None = None


class MissingAudioParts(ValueError):
    def __init__(self, missing: list[int]) -> None:
        super().__init__(f"Recording parts never arrived: {missing}")
        self.missing = missing


class Store(Protocol):
    # --- seniors
    def add_senior(
        self,
        *,
        name: str,
        name_reading: str = "",
        birth_year: int | None = None,
        birthplace: str = "",
        family: list[str] | None = None,
        language: str = "ja",
    ) -> str: ...
    def get_senior(self, senior_id: str) -> Senior | None: ...
    def list_seniors(self) -> list[Senior]: ...

    # --- sessions
    def start(
        self,
        *,
        model: str,
        voice: str,
        silence_duration_ms: int,
        end_of_speech_sensitivity: str,
        senior_id: str | None = None,
        carried_questions: list[str] | None = None,
    ) -> str: ...
    def finish(
        self,
        session_id: str,
        *,
        turns: list[Turn],
        audio: bytes | None,
        duration_seconds: float,
        input_label: str,
    ) -> None: ...
    def set_status(self, session_id: str, status: str, error: str | None = None) -> None: ...
    def list_sessions(self, limit: int = 100) -> list[Session]: ...
    def get(self, session_id: str) -> Session | None: ...
    def has_audio(self, session_id: str) -> bool: ...
    def open_audio(self, session_id: str) -> BinaryIO | None:
        """The session's recording, open for reading and seekable. The caller closes it."""
        ...

    def save_audio_part(self, session_id: str, index: int, data: bytes) -> None:
        """One piece of a recording too big to arrive in one request."""
        ...

    def join_audio_parts(self, session_id: str, count: int) -> None:
        """Parts 0 to count-1 become the recording, in order, and are discarded.
        Raises MissingAudioParts, and changes nothing, if any never arrived."""
        ...

    # --- family questions
    def add_family_question(
        self, senior_id: str, *, asked_by: str, text: str, status: str = "pending"
    ) -> str: ...
    def family_questions(
        self, senior_id: str, status: str | None = None
    ) -> list[FamilyQuestion]: ...
    def set_question_status(self, question_id: str, status: str) -> None: ...
    def mark_question_asked(
        self, question_id: str, session_id: str, answer_story_ids: list[str]
    ) -> None: ...

    # --- stories and plans
    def replace_stories(self, session_id: str, senior_id: str, stories: list[Story]) -> None:
        """A session's stories are rewritten wholesale, so re-processing is safe."""
        ...

    def stories_for_session(self, session_id: str) -> list[Story]: ...
    def stories_for_senior(self, senior_id: str, shared_only: bool = False) -> list[Story]:
        """With `shared_only`, filtered where they are stored, never by the caller."""
        ...

    def save_plan(self, senior_id: str, plan: Plan) -> None: ...
    def get_plan(self, senior_id: str) -> Plan: ...

    # --- forgetting
    def forget_senior(self, senior_id: str) -> dict[str, int]:
        """Everything kept about one person: their sessions and every recording,
        stories, plan and family questions. Returns how many of each went."""
        ...


class LocalStore:
    """SQLite for the records, plain files for the audio."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.recordings = data_dir / "recordings"
        self.recordings.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)
            for table, columns in LATER_COLUMNS.items():
                present = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                for column, spec in columns.items():
                    if column not in present:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.data_dir / "kataribe.db")
        db.row_factory = sqlite3.Row
        return db

    # --- seniors -------------------------------------------------------

    def add_senior(
        self,
        *,
        name: str,
        name_reading: str = "",
        birth_year: int | None = None,
        birthplace: str = "",
        family: list[str] | None = None,
        language: str = "ja",
    ) -> str:
        senior_id = uuid.uuid4().hex[:12]
        with self._connect() as db:
            db.execute(
                "INSERT INTO seniors (id, name, name_reading, birth_year, birthplace, family,"
                " language, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    senior_id,
                    name,
                    name_reading,
                    birth_year,
                    birthplace,
                    json.dumps(family or [], ensure_ascii=False),
                    language,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return senior_id

    def get_senior(self, senior_id: str) -> Senior | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM seniors WHERE id = ?", (senior_id,)).fetchone()
        if row is None:
            return None
        # `in` on a Row searches values, so the column list is taken explicitly.
        columns = row.keys()
        return Senior(
            id=row["id"],
            name=row["name"],
            name_reading=row["name_reading"],
            birth_year=row["birth_year"],
            birthplace=row["birthplace"],
            family=json.loads(row["family"]),
            language=row["language"] if "language" in columns else "ja",
        )

    def list_seniors(self) -> list[Senior]:
        with self._connect() as db:
            rows = db.execute("SELECT id FROM seniors ORDER BY created_at").fetchall()
        return [s for s in (self.get_senior(row["id"]) for row in rows) if s]

    # --- sessions ------------------------------------------------------

    def start(
        self,
        *,
        model: str,
        voice: str,
        silence_duration_ms: int,
        end_of_speech_sensitivity: str,
        senior_id: str | None = None,
        carried_questions: list[str] | None = None,
    ) -> str:
        session_id = uuid.uuid4().hex[:12]
        with self._connect() as db:
            db.execute(
                "INSERT INTO sessions (id, started_at, model, voice, silence_duration_ms,"
                " end_of_speech_sensitivity, senior_id, carried_questions)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    datetime.now(UTC).isoformat(),
                    model,
                    voice,
                    silence_duration_ms,
                    end_of_speech_sensitivity,
                    senior_id,
                    json.dumps(carried_questions or []),
                ),
            )
        return session_id

    def finish(
        self,
        session_id: str,
        *,
        turns: list[Turn],
        audio: bytes | None,
        duration_seconds: float,
        input_label: str,
    ) -> None:
        if audio:
            (self.recordings / f"{session_id}.wav").write_bytes(audio)
        with self._connect() as db:
            db.execute(
                "UPDATE sessions SET ended_at = ?, duration_seconds = ?, transcript = ?,"
                " input_label = ? WHERE id = ?",
                (
                    datetime.now(UTC).isoformat(),
                    duration_seconds,
                    json.dumps([turn.__dict__ for turn in turns], ensure_ascii=False),
                    input_label,
                    session_id,
                ),
            )

    def set_status(self, session_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE sessions SET status = ?, processing_error = ?, status_at = ? WHERE id = ?",
                (status, error, datetime.now(UTC).isoformat(), session_id),
            )

    def list_sessions(self, limit: int = 100) -> list[Session]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_to_session(row) for row in rows]

    def get(self, session_id: str) -> Session | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _to_session(row) if row else None

    def has_audio(self, session_id: str) -> bool:
        return (self.recordings / f"{session_id}.wav").exists()

    def open_audio(self, session_id: str) -> BinaryIO | None:
        path = self.recordings / f"{session_id}.wav"
        return path.open("rb") if path.exists() else None

    def save_audio_part(self, session_id: str, index: int, data: bytes) -> None:
        (self.recordings / f"{session_id}.part{index}").write_bytes(data)

    def join_audio_parts(self, session_id: str, count: int) -> None:
        parts = [self.recordings / f"{session_id}.part{i}" for i in range(count)]
        missing = [i for i, part in enumerate(parts) if not part.exists()]
        if missing:
            raise MissingAudioParts(missing)
        with (self.recordings / f"{session_id}.wav").open("wb") as recording:
            for part in parts:
                recording.write(part.read_bytes())
        for part in parts:
            part.unlink()

    # --- family questions ----------------------------------------------

    def add_family_question(
        self, senior_id: str, *, asked_by: str, text: str, status: str = "pending"
    ) -> str:
        question_id = uuid.uuid4().hex[:12]
        with self._connect() as db:
            db.execute(
                "INSERT INTO family_questions (id, senior_id, asked_by, text, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (question_id, senior_id, asked_by, text, status, datetime.now(UTC).isoformat()),
            )
        return question_id

    def family_questions(self, senior_id: str, status: str | None = None) -> list[FamilyQuestion]:
        clause = " AND status = ?" if status else ""
        params: tuple[str, ...] = (senior_id, status) if status else (senior_id,)
        with self._connect() as db:
            rows = db.execute(
                f"SELECT * FROM family_questions WHERE senior_id = ?{clause} ORDER BY created_at",
                params,
            ).fetchall()
        return [
            FamilyQuestion(
                id=row["id"],
                senior_id=row["senior_id"],
                asked_by=row["asked_by"],
                text=row["text"],
                status=row["status"],
                asked_in_session=row["asked_in_session"],
                answer_story_ids=json.loads(row["answer_story_ids"]),
            )
            for row in rows
        ]

    def set_question_status(self, question_id: str, status: str) -> None:
        with self._connect() as db:
            db.execute("UPDATE family_questions SET status = ? WHERE id = ?", (status, question_id))

    def mark_question_asked(
        self, question_id: str, session_id: str, answer_story_ids: list[str]
    ) -> None:
        with self._connect() as db:
            db.execute(
                "UPDATE family_questions SET status = 'asked', asked_in_session = ?,"
                " answer_story_ids = ? WHERE id = ?",
                (session_id, json.dumps(answer_story_ids), question_id),
            )

    # --- stories and plans ---------------------------------------------

    def replace_stories(self, session_id: str, senior_id: str, stories: list[Story]) -> None:
        """A session's stories are rewritten wholesale, so re-processing is safe."""
        with self._connect() as db:
            db.execute("DELETE FROM stories WHERE session_id = ?", (session_id,))
            db.executemany(
                "INSERT INTO stories (id, senior_id, session_id, title, summary, life_stage,"
                " approx_period, people, places, quotes, visibility, consent_quote, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        story.id,
                        senior_id,
                        session_id,
                        story.title,
                        story.summary,
                        story.life_stage,
                        story.approx_period,
                        json.dumps(story.people, ensure_ascii=False),
                        json.dumps(story.places, ensure_ascii=False),
                        json.dumps([q.__dict__ for q in story.quotes], ensure_ascii=False),
                        story.visibility,
                        story.consent_quote,
                        datetime.now(UTC).isoformat(),
                    )
                    for story in stories
                ],
            )

    def stories_for_session(self, session_id: str) -> list[Story]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM stories WHERE session_id = ? ORDER BY created_at", (session_id,)
            ).fetchall()
        return [_to_story(row) for row in rows]

    def stories_for_senior(self, senior_id: str, shared_only: bool = False) -> list[Story]:
        clause = " AND visibility = 'family'" if shared_only else ""
        with self._connect() as db:
            rows = db.execute(
                f"SELECT * FROM stories WHERE senior_id = ?{clause} ORDER BY created_at",
                (senior_id,),
            ).fetchall()
        return [_to_story(row) for row in rows]

    def save_plan(self, senior_id: str, plan: Plan) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO plans (senior_id, story_so_far, next_questions, avoid_topics,"
                " updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(senior_id) DO UPDATE SET"
                " story_so_far = excluded.story_so_far,"
                " next_questions = excluded.next_questions,"
                " avoid_topics = excluded.avoid_topics,"
                " updated_at = excluded.updated_at",
                (
                    senior_id,
                    plan.story_so_far,
                    json.dumps(plan.next_questions, ensure_ascii=False),
                    json.dumps(plan.avoid_topics, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get_plan(self, senior_id: str) -> Plan:
        with self._connect() as db:
            row = db.execute("SELECT * FROM plans WHERE senior_id = ?", (senior_id,)).fetchone()
        if row is None:
            return Plan(story_so_far="", next_questions=[], avoid_topics=[])
        return Plan(
            story_so_far=row["story_so_far"],
            next_questions=json.loads(row["next_questions"]),
            avoid_topics=json.loads(row["avoid_topics"]),
        )

    # --- forgetting ----------------------------------------------------

    def forget_senior(self, senior_id: str) -> dict[str, int]:
        gone: dict[str, int] = {}
        with self._connect() as db:
            sessions = [
                row["id"]
                for row in db.execute("SELECT id FROM sessions WHERE senior_id = ?", (senior_id,))
            ]
            for table in ("sessions", "stories", "family_questions"):
                gone[table] = db.execute(
                    f"DELETE FROM {table} WHERE senior_id = ?", (senior_id,)
                ).rowcount
            db.execute("DELETE FROM plans WHERE senior_id = ?", (senior_id,))
            db.execute("DELETE FROM seniors WHERE id = ?", (senior_id,))
        gone["recordings"] = 0
        for session_id in sessions:
            for path in self.recordings.glob(f"{session_id}.*"):
                path.unlink()
                gone["recordings"] += 1
        return gone


def _to_session(row: sqlite3.Row) -> Session:
    keys = row.keys()
    return Session(
        id=row["id"],
        started_at=datetime.fromisoformat(row["started_at"]),
        ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        model=row["model"],
        voice=row["voice"],
        silence_duration_ms=row["silence_duration_ms"],
        end_of_speech_sensitivity=row["end_of_speech_sensitivity"],
        input_label=row["input_label"],
        duration_seconds=row["duration_seconds"],
        turns=[Turn(**turn) for turn in json.loads(row["transcript"] or "[]")],
        senior_id=row["senior_id"] if "senior_id" in keys else None,
        status=(row["status"] if "status" in keys else None) or "recorded",
        processing_error=row["processing_error"] if "processing_error" in keys else None,
        carried_questions=json.loads(row["carried_questions"])
        if "carried_questions" in keys
        else [],
        status_at=datetime.fromisoformat(row["status_at"])
        if "status_at" in keys and row["status_at"]
        else None,
    )


def _to_story(row: sqlite3.Row) -> Story:
    columns = row.keys()
    return Story(
        id=row["id"],
        senior_id=row["senior_id"],
        session_id=row["session_id"],
        title=row["title"],
        summary=row["summary"],
        life_stage=row["life_stage"],
        approx_period=row["approx_period"],
        people=json.loads(row["people"]),
        places=json.loads(row["places"]),
        quotes=[Quote(**q) for q in json.loads(row["quotes"])],
        visibility=row["visibility"] if "visibility" in columns else "private",
        consent_quote=row["consent_quote"] if "consent_quote" in columns else "",
    )


__all__ = [
    "LIFE_STAGES",
    "FamilyQuestion",
    "LocalStore",
    "MissingAudioParts",
    "Plan",
    "Quote",
    "Senior",
    "Session",
    "Store",
    "Story",
    "Turn",
]

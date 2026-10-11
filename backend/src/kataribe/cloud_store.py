"""Firestore for the records, Cloud Storage for the recordings.

The store the deployed app uses, since Cloud Run's own disk does not outlive a
restart. It has the same interface as LocalStore, and the same contract tests
(tests/test_store.py) run against both.

Queries filter on equalities only and sort in Python, so no composite index has
to be created before anything works. The collections are small: one family's
sessions and stories.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, BinaryIO, cast

import google.cloud.storage as storage
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from kataribe.store import (
    FamilyQuestion,
    MissingAudioParts,
    Plan,
    Quote,
    Senior,
    Session,
    Story,
    Turn,
)

READ_CHUNK = 1 << 20
"""Bytes fetched per read of a recording. The library's default is 40 MiB, which
would pull most of a session down just to read its header."""


class CloudStore:
    def __init__(
        self, *, project: str | None, database: str, bucket: str, prefix: str = ""
    ) -> None:
        """`prefix` namespaces every collection and object, so tests can run
        against a real project without touching what is there."""
        self.db = firestore.Client(project=project, database=database)
        self.bucket = storage.Client(project=project).bucket(bucket)
        self.prefix = prefix

    def _collection(self, name: str) -> firestore.CollectionReference:
        return self.db.collection(f"{self.prefix}{name}")

    def _blob(self, name: str) -> Any:
        return self.bucket.blob(f"{self.prefix}recordings/{name}")

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
        self._collection("seniors").document(senior_id).set(
            {
                "name": name,
                "name_reading": name_reading,
                "birth_year": birth_year,
                "birthplace": birthplace,
                "family": family or [],
                "language": language,
                "created_at": _now(),
            }
        )
        return senior_id

    def get_senior(self, senior_id: str) -> Senior | None:
        snapshot = self._collection("seniors").document(senior_id).get()
        return _senior(snapshot.id, _data(snapshot)) if snapshot.exists else None

    def list_seniors(self) -> list[Senior]:
        return [
            _senior(s.id, _data(s))
            for s in self._collection("seniors").order_by("created_at").stream()
        ]

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
        self._collection("sessions").document(session_id).set(
            {
                "started_at": _now(),
                "ended_at": None,
                "model": model,
                "voice": voice,
                "silence_duration_ms": silence_duration_ms,
                "end_of_speech_sensitivity": end_of_speech_sensitivity,
                "input_label": "microphone",
                "duration_seconds": None,
                "turns": [],
                "senior_id": senior_id,
                "status": "recorded",
                "processing_error": None,
                "carried_questions": carried_questions or [],
                "status_at": None,
            }
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
            self._blob(f"{session_id}.wav").upload_from_string(audio, content_type="audio/wav")
        self._collection("sessions").document(session_id).update(
            {
                "ended_at": _now(),
                "duration_seconds": duration_seconds,
                "turns": [turn.__dict__ for turn in turns],
                "input_label": input_label,
            }
        )

    def set_status(self, session_id: str, status: str, error: str | None = None) -> None:
        self._collection("sessions").document(session_id).update(
            {"status": status, "processing_error": error, "status_at": _now()}
        )

    def list_sessions(self, limit: int = 100) -> list[Session]:
        query = (
            self._collection("sessions")
            .order_by("started_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [_session(s.id, _data(s)) for s in query.stream()]

    def get(self, session_id: str) -> Session | None:
        snapshot = self._collection("sessions").document(session_id).get()
        return _session(snapshot.id, _data(snapshot)) if snapshot.exists else None

    def has_audio(self, session_id: str) -> bool:
        return bool(self._blob(f"{session_id}.wav").exists())

    def open_audio(self, session_id: str) -> BinaryIO | None:
        blob = self._blob(f"{session_id}.wav")
        if not blob.exists():
            return None
        return cast(BinaryIO, blob.open("rb", chunk_size=READ_CHUNK))

    def save_audio_part(self, session_id: str, index: int, data: bytes) -> None:
        self._blob(f"{session_id}.part{index}").upload_from_string(data)

    def join_audio_parts(self, session_id: str, count: int) -> None:
        parts = [self._blob(f"{session_id}.part{i}") for i in range(count)]
        missing = [i for i, part in enumerate(parts) if not part.exists()]
        if missing:
            raise MissingAudioParts(missing)
        # Joined where they are stored: nothing passes through this server.
        recording = self._blob(f"{session_id}.wav")
        recording.content_type = "audio/wav"
        recording.compose(parts)
        for part in parts:
            part.delete()

    # --- family questions ----------------------------------------------

    def add_family_question(
        self, senior_id: str, *, asked_by: str, text: str, status: str = "pending"
    ) -> str:
        question_id = uuid.uuid4().hex[:12]
        self._collection("family_questions").document(question_id).set(
            {
                "senior_id": senior_id,
                "asked_by": asked_by,
                "text": text,
                "status": status,
                "asked_in_session": None,
                "answer_story_ids": [],
                "created_at": _now(),
            }
        )
        return question_id

    def family_questions(self, senior_id: str, status: str | None = None) -> list[FamilyQuestion]:
        snapshots = self._where("family_questions", senior_id=senior_id)
        questions = [
            (data["created_at"], _question(s.id, data))
            for s in snapshots
            if (data := _data(s)) and (status is None or data["status"] == status)
        ]
        return [question for _, question in sorted(questions, key=lambda pair: pair[0])]

    def set_question_status(self, question_id: str, status: str) -> None:
        self._collection("family_questions").document(question_id).update({"status": status})

    def mark_question_asked(
        self, question_id: str, session_id: str, answer_story_ids: list[str]
    ) -> None:
        self._collection("family_questions").document(question_id).update(
            {
                "status": "asked",
                "asked_in_session": session_id,
                "answer_story_ids": answer_story_ids,
            }
        )

    # --- stories and plans ---------------------------------------------

    def replace_stories(self, session_id: str, senior_id: str, stories: list[Story]) -> None:
        batch = self.db.batch()
        for old in self._where("stories", session_id=session_id):
            batch.delete(old.reference)
        now = _now()
        for position, story in enumerate(stories):
            batch.set(
                self._collection("stories").document(story.id),
                {
                    "senior_id": senior_id,
                    "session_id": session_id,
                    "title": story.title,
                    "summary": story.summary,
                    "life_stage": story.life_stage,
                    "approx_period": story.approx_period,
                    "people": story.people,
                    "places": story.places,
                    "quotes": [quote.__dict__ for quote in story.quotes],
                    "visibility": story.visibility,
                    "consent_quote": story.consent_quote,
                    "asked_to_share": story.asked_to_share,
                    "created_at": now,
                    # Stories from one session share a timestamp; this keeps
                    # them in the order they were told.
                    "position": position,
                },
            )
        batch.commit()

    def stories_for_session(self, session_id: str) -> list[Story]:
        return _in_order(self._where("stories", session_id=session_id))

    def set_sharing(self, story_id: str, *, visibility: str, consent_quote: str) -> None:
        self._collection("stories").document(story_id).update(
            {"visibility": visibility, "consent_quote": consent_quote, "asked_to_share": True}
        )

    def stories_for_senior(self, senior_id: str, shared_only: bool = False) -> list[Story]:
        if shared_only:
            return _in_order(self._where("stories", senior_id=senior_id, visibility="family"))
        return _in_order(self._where("stories", senior_id=senior_id))

    def save_plan(self, senior_id: str, plan: Plan) -> None:
        self._collection("plans").document(senior_id).set(
            {
                "story_so_far": plan.story_so_far,
                "next_questions": plan.next_questions,
                "avoid_topics": plan.avoid_topics,
                "updated_at": _now(),
            }
        )

    def get_plan(self, senior_id: str) -> Plan:
        snapshot = self._collection("plans").document(senior_id).get()
        if not snapshot.exists:
            return Plan(story_so_far="", next_questions=[], avoid_topics=[])
        data = _data(snapshot)
        return Plan(
            story_so_far=data.get("story_so_far", ""),
            next_questions=list(data.get("next_questions", [])),
            avoid_topics=list(data.get("avoid_topics", [])),
        )

    # --- forgetting ----------------------------------------------------

    def forget_senior(self, senior_id: str) -> dict[str, int]:
        sessions = self._where("sessions", senior_id=senior_id)
        gone: dict[str, int] = {}
        batch = self.db.batch()
        for name in ("sessions", "stories", "family_questions"):
            documents = sessions if name == "sessions" else self._where(name, senior_id=senior_id)
            gone[name] = len(documents)
            for document in documents:
                batch.delete(document.reference)
        batch.delete(self._collection("plans").document(senior_id))
        batch.delete(self._collection("seniors").document(senior_id))
        batch.commit()

        gone["recordings"] = 0
        for session in sessions:
            for blob in self.bucket.list_blobs(prefix=f"{self.prefix}recordings/{session.id}."):
                blob.delete()
                gone["recordings"] += 1
        return gone

    def _where(self, collection: str, **equal: str) -> list[Any]:
        query: Any = self._collection(collection)
        for field, value in equal.items():
            query = query.where(filter=FieldFilter(field, "==", value))
        return list(query.stream())


def _now() -> datetime:
    return datetime.now(UTC)


def _data(snapshot: Any) -> dict[str, Any]:
    return cast(dict[str, Any], snapshot.to_dict() or {})


def _senior(senior_id: str, data: dict[str, Any]) -> Senior:
    return Senior(
        id=senior_id,
        name=data["name"],
        name_reading=data.get("name_reading", ""),
        birth_year=data.get("birth_year"),
        birthplace=data.get("birthplace", ""),
        family=list(data.get("family", [])),
        language=data.get("language", "ja"),
    )


def _session(session_id: str, data: dict[str, Any]) -> Session:
    return Session(
        id=session_id,
        started_at=data["started_at"],
        ended_at=data.get("ended_at"),
        model=data["model"],
        voice=data["voice"],
        silence_duration_ms=data["silence_duration_ms"],
        end_of_speech_sensitivity=data["end_of_speech_sensitivity"],
        input_label=data.get("input_label", "microphone"),
        duration_seconds=data.get("duration_seconds"),
        turns=[Turn(**turn) for turn in data.get("turns", [])],
        senior_id=data.get("senior_id"),
        status=data.get("status") or "recorded",
        processing_error=data.get("processing_error"),
        carried_questions=list(data.get("carried_questions", [])),
        status_at=data.get("status_at"),
    )


def _question(question_id: str, data: dict[str, Any]) -> FamilyQuestion:
    return FamilyQuestion(
        id=question_id,
        senior_id=data["senior_id"],
        asked_by=data["asked_by"],
        text=data["text"],
        status=data["status"],
        asked_in_session=data.get("asked_in_session"),
        answer_story_ids=list(data.get("answer_story_ids", [])),
    )


def _in_order(snapshots: list[Any]) -> list[Story]:
    rows = [(s.id, _data(s)) for s in snapshots]
    rows.sort(key=lambda row: (row[1]["created_at"], row[1].get("position", 0)))
    return [
        Story(
            id=story_id,
            senior_id=data["senior_id"],
            session_id=data["session_id"],
            title=data["title"],
            summary=data["summary"],
            life_stage=data["life_stage"],
            approx_period=data.get("approx_period", ""),
            people=list(data.get("people", [])),
            places=list(data.get("places", [])),
            quotes=[Quote(**quote) for quote in data.get("quotes", [])],
            visibility=data.get("visibility", "private"),
            consent_quote=data.get("consent_quote", ""),
            asked_to_share=data.get("asked_to_share", True),
        )
        for story_id, data in rows
    ]

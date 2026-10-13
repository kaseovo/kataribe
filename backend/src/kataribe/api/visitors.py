"""Strangers on the public URL, such as judges, trying it on their own lives.

The start page makes each of them a persona of their own. Memory is per person:
with one persona shared between visitors, the second would be greeted with the
first one's childhood and asked the first one's family questions. A visitor talks
as themselves, and a second conversation recalls their first.

A visitor persona is flagged as one, and only those may be talked to without the
team password. Its id is the only key to it, so it is long enough that nobody
finds another visitor's by guessing, and nothing public lists people.

Every conversation is paid for, so the day's visitors share a limit.
"""

import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from kataribe.api.sessions import get_store
from kataribe.config import Settings, get_settings
from kataribe.languages import LANGUAGES
from kataribe.store import Store

router = APIRouter(prefix="/api/try", tags=["visitors"])

JAPAN = ZoneInfo("Asia/Tokyo")


def _today() -> datetime.datetime:
    """Midnight in Japan, where the day's limits start again."""
    return datetime.datetime.now(JAPAN).replace(hour=0, minute=0, second=0, microsecond=0)


def visitor_sessions_today(store: Store) -> int:
    visitors = {senior.id for senior in store.list_seniors() if senior.visitor}
    midnight = _today()
    return sum(
        1
        for session in store.list_sessions(limit=500)
        if session.senior_id in visitors and session.started_at >= midnight
    )


def visitor_personas_today(store: Store) -> int:
    midnight = _today()
    return sum(
        1
        for senior in store.list_seniors()
        if senior.visitor and senior.created_at is not None and senior.created_at >= midnight
    )


class LanguageChoice(BaseModel):
    code: str
    endonym: str


class TryView(BaseModel):
    """What the start page needs to know."""

    languages: list[LanguageChoice]
    showcase: str | None
    """The family page to read, already full: stories from the demo take."""
    video: str
    repo: str
    open: bool
    """False once today's conversations are used up."""


class TryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=40)
    language: str
    asked_by: str = Field(default="", max_length=40)
    """Who would ask, as the interviewer should say it: "your daughter Emma"."""
    question: str = Field(default="", max_length=300)


class TryResponse(BaseModel):
    id: str


@router.get("")
def read_start(
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> TryView:
    return TryView(
        languages=[
            LanguageChoice(code=code, endonym=LANGUAGES[code].endonym)
            for code in settings.visitor_languages
            if code in LANGUAGES
        ],
        showcase=settings.showcase_senior or None,
        video=settings.video_url,
        repo=settings.repo_url,
        open=visitor_sessions_today(store) < settings.visitor_sessions_per_day
        and visitor_personas_today(store) < settings.visitor_personas_per_day,
    )


@router.post("")
def make_persona(
    request: TryRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> TryResponse:
    """A persona of their own, and the family question its first conversation
    opens with, if they left one. A question is asked on behalf of someone, and
    the interviewer always says who, so one without an asker is refused."""
    if request.language not in settings.visitor_languages or request.language not in LANGUAGES:
        raise HTTPException(status_code=422, detail=f"Not offered: {request.language}")
    if request.question and not request.asked_by:
        raise HTTPException(status_code=422, detail="Say who would ask the question")
    if visitor_personas_today(store) >= settings.visitor_personas_per_day:
        raise HTTPException(status_code=429, detail="Enough visitors for today")

    senior_id = store.add_senior(name=request.name, language=request.language, visitor=True)
    # Nothing has been refused yet, so there is nothing to screen it against.
    if request.question:
        store.add_family_question(senior_id, asked_by=request.asked_by, text=request.question)
    return TryResponse(id=senior_id)

"""The senior's own screen: one person, one button.

Besides the family pages, this is the only part of the API a stranger may
reach, and only for the people named in KATARIBE_VISITOR_SENIORS: demo
personas, for judges and visitors to try. Anyone else's screen needs the team
password. A stranger able to talk as someone could put invented stories into
that person's life story, and their family would read them.

The work itself is the console's: these routes check who may do it, then call
the same session and upload functions, so the two cannot drift apart.
"""

import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from pydantic import BaseModel

from kataribe.api import sessions
from kataribe.api.sessions import MAX_PARTS, SessionRequest, SessionResponse, get_store
from kataribe.config import Settings, get_settings
from kataribe.store import Senior, Store

router = APIRouter(prefix="/api/talk/{senior_id}", tags=["talk"])

JAPAN = ZoneInfo("Asia/Tokyo")


class TalkView(BaseModel):
    name: str
    language: str


def is_visitor(request: Request) -> bool:
    """Set by the access middleware. With no team password, everyone is team."""
    return not getattr(request.state, "team", True)


def _person(senior_id: str, request: Request, settings: Settings, store: Store) -> Senior:
    if is_visitor(request) and senior_id not in settings.visitors:
        # Someone's own screen: the browser is asked to sign in as the team. It
        # is asked the same way whether or not they exist, so a visitor learns
        # nothing about who does.
        raise HTTPException(
            status_code=401, headers={"WWW-Authenticate": 'Basic realm="kataribe team"'}
        )
    senior = store.get_senior(senior_id)
    if senior is None:
        raise HTTPException(status_code=404, detail="No one to talk to here")
    return senior


def _own_session(senior_id: str, session_id: str, store: Store) -> None:
    session = store.get(session_id)
    if session is None or session.senior_id != senior_id:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")


@router.get("")
def read_person(
    senior_id: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> TalkView:
    senior = _person(senior_id, request, settings, store)
    return TalkView(name=senior.name, language=senior.language)


@router.post("/sessions")
def start_talking(
    senior_id: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> SessionResponse:
    """A conversation with the person's own defaults: their language, voice
    and pause. Visitors get a few a day per persona, since each one is paid for."""
    _person(senior_id, request, settings, store)
    if is_visitor(request):
        midnight = datetime.datetime.now(JAPAN).replace(hour=0, minute=0, second=0, microsecond=0)
        today = [
            s
            for s in store.list_sessions(limit=500)
            if s.senior_id == senior_id and s.started_at >= midnight
        ]
        if len(today) >= settings.visitor_sessions_per_day:
            raise HTTPException(status_code=429, detail="Enough conversations for today")
    return sessions.create_session(SessionRequest(senior_id=senior_id), settings, store)


@router.put("/sessions/{session_id}/recording/parts/{index}", status_code=204)
async def keep_part(
    senior_id: str,
    session_id: str,
    index: int,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> None:
    _person(senior_id, request, settings, store)
    _own_session(senior_id, session_id, store)
    await sessions.upload_recording_part(session_id, index, request, store)


@router.post("/sessions/{session_id}/recording", status_code=204)
async def keep_recording(
    senior_id: str,
    session_id: str,
    request: Request,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
    transcript: Annotated[str, Form()],
    duration_seconds: Annotated[float, Form()],
    input_label: Annotated[str, Form()] = "microphone",
    audio_parts: Annotated[int, Form(ge=0, le=MAX_PARTS)] = 0,
) -> None:
    _person(senior_id, request, settings, store)
    _own_session(senior_id, session_id, store)
    await sessions.upload_recording(
        session_id,
        background,
        settings,
        store,
        transcript,
        duration_seconds,
        input_label,
        None,
        audio_parts,
    )

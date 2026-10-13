"""The senior's own screen: one person, one button.

Besides the start page and the family pages, this is the only part of the API a
stranger may reach, and only for visitor personas: the ones strangers made for
themselves from the start page. Anyone else's screen needs the team password. A
stranger able to talk as someone could put invented stories into that person's
life story, and their family would read them.

The work itself is the console's: these routes check who may do it, then call
the same session and upload functions, so the two cannot drift apart.

A visitor's screen does two things more, after the conversation: it waits for
the writing-up, and it asks about any story that got no answer about sharing,
since a visitor may never come back to be asked next time.
"""

import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from pydantic import BaseModel

from kataribe.api import sessions
from kataribe.api.sessions import MAX_PARTS, SessionRequest, SessionResponse, get_store
from kataribe.api.visitors import visitor_sessions_today
from kataribe.config import Settings, get_settings
from kataribe.processing import can_retry
from kataribe.store import Senior, Store

router = APIRouter(prefix="/api/talk/{senior_id}", tags=["talk"])


class TalkView(BaseModel):
    name: str
    language: str
    visitor: bool


class UnaskedStory(BaseModel):
    id: str
    title: str


class WritingUp(BaseModel):
    """How a visitor's conversation is getting on after it ended."""

    state: Literal["writing", "written", "failed"]
    shared: int
    """Stories their family can now read."""
    unasked: list[UnaskedStory]
    """Stories with no answer about sharing, because the interviewer never asked
    or they never replied, to ask about on screen. Never one they answered about
    aloud: whatever they said then stands."""


class SharingChoice(BaseModel):
    share: bool
    everything: bool = False
    """Kept private, every story of the conversation, even one agreed to aloud.
    Pressed while the conversation was still going, Keep it private is the last
    word, and private is the safe way to be wrong."""


def is_visitor(request: Request) -> bool:
    """Set by the access middleware. With no team password, everyone is team."""
    return not getattr(request.state, "team", True)


def _person(senior_id: str, request: Request, store: Store) -> Senior:
    senior = store.get_senior(senior_id)
    if is_visitor(request) and (senior is None or not senior.visitor):
        # Someone's own screen: the browser is asked to sign in as the team. It
        # is asked the same way whether or not they exist, so a visitor learns
        # nothing about who does.
        raise HTTPException(
            status_code=401, headers={"WWW-Authenticate": 'Basic realm="kataribe team"'}
        )
    if senior is None:
        raise HTTPException(status_code=404, detail="No one to talk to here")
    return senior


def _visitor(senior_id: str, request: Request, store: Store) -> Senior:
    """The end screen's extras are a visitor persona's. A real person is asked
    about sharing in their next conversation, as the product means them to be."""
    senior = _person(senior_id, request, store)
    if not senior.visitor:
        raise HTTPException(status_code=404, detail="Only a visitor's screen does this")
    return senior


def _own_session(senior_id: str, session_id: str, store: Store) -> None:
    session = store.get(session_id)
    if session is None or session.senior_id != senior_id:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")


@router.get("")
def read_person(
    senior_id: str, request: Request, store: Annotated[Store, Depends(get_store)]
) -> TalkView:
    senior = _person(senior_id, request, store)
    return TalkView(name=senior.name, language=senior.language, visitor=senior.visitor)


@router.post("/sessions")
def start_talking(
    senior_id: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> SessionResponse:
    """A conversation with the person's own defaults: their language, voice
    and pause. Visitors share a few a day between them, since each is paid for."""
    _person(senior_id, request, store)
    if is_visitor(request) and visitor_sessions_today(store) >= settings.visitor_sessions_per_day:
        raise HTTPException(status_code=429, detail="Enough conversations for today")
    return sessions.create_session(SessionRequest(senior_id=senior_id), settings, store)


@router.put("/sessions/{session_id}/recording/parts/{index}", status_code=204)
async def keep_part(
    senior_id: str,
    session_id: str,
    index: int,
    request: Request,
    store: Annotated[Store, Depends(get_store)],
) -> None:
    _person(senior_id, request, store)
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
    _person(senior_id, request, store)
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


@router.get("/sessions/{session_id}")
def read_writing_up(
    senior_id: str,
    session_id: str,
    request: Request,
    store: Annotated[Store, Depends(get_store)],
) -> WritingUp:
    _visitor(senior_id, request, store)
    _own_session(senior_id, session_id, store)
    return _writing_up(session_id, store)


@router.post("/sessions/{session_id}/sharing")
def choose_sharing(
    senior_id: str,
    session_id: str,
    choice: SharingChoice,
    request: Request,
    store: Annotated[Store, Depends(get_store)],
) -> WritingUp:
    """What a visitor chose on screen: on the end screen, for the stories with
    no answer about sharing, or with the buttons shown while it was closing.

    Sharing reaches only stories with no answer: one they kept private aloud
    stays private, whatever they press. Keeping private reaches the same ones,
    or, with `everything`, every story of the conversation. The choice is kept
    on the session, apart from consent in their own words, so the two can
    always be told apart."""
    _visitor(senior_id, request, store)
    _own_session(senior_id, session_id, store)
    if _writing_up(session_id, store).state != "written":
        raise HTTPException(status_code=409, detail="Not written up yet")
    for story in store.stories_for_session(session_id):
        unanswered = not story.asked_to_share and not story.shared
        if unanswered or (choice.everything and not choice.share):
            store.set_sharing(
                story.id, visibility="family" if choice.share else "private", consent_quote=""
            )
    store.set_screen_consent(session_id, "shared" if choice.share else "private")
    return _writing_up(session_id, store)


def _writing_up(session_id: str, store: Store) -> WritingUp:
    session = store.get(session_id)
    assert session is not None, "checked by _own_session"
    now = datetime.datetime.now(tz=datetime.UTC)
    if session.status == "processed":
        state: Literal["writing", "written", "failed"] = "written"
    elif session.status in ("failed", "skipped") or (
        session.status in ("queued", "processing") and can_retry(session, now)
    ):
        # A reading that stalled is as lost to them as one that failed; the
        # team can start it again from the console.
        state = "failed"
    else:
        state = "writing"
    stories = store.stories_for_session(session_id) if state == "written" else []
    return WritingUp(
        state=state,
        shared=sum(1 for story in stories if story.shared),
        unasked=[
            UnaskedStory(id=story.id, title=story.title)
            for story in stories
            if not story.asked_to_share and not story.shared
        ],
    )

import datetime
import json
import logging
import wave
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from kataribe import brain, clips
from kataribe.config import Settings, get_settings
from kataribe.gemini import VOICES, InterviewTuning, mint_session_credentials
from kataribe.languages import LANGUAGES, get
from kataribe.processing import can_retry, process_session
from kataribe.store import (
    LIFE_STAGES,
    FamilyQuestion,
    LocalStore,
    MissingAudioParts,
    Senior,
    Store,
    Turn,
)

router = APIRouter(prefix="/api", tags=["sessions"])
log = logging.getLogger(__name__)


@lru_cache
def _store(kind: str, data_dir: str, project: str | None, database: str, bucket: str) -> Store:
    if kind == "cloud":
        # Imported only when used, so local development never loads the clients.
        from kataribe.cloud_store import CloudStore

        return CloudStore(project=project, database=database, bucket=bucket)
    from pathlib import Path

    return LocalStore(Path(data_dir))


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> Store:
    return _store(
        settings.storage,
        str(settings.data_dir),
        settings.gcp_project,
        settings.firestore_database,
        settings.recordings_bucket,
    )


class LanguageView(BaseModel):
    code: str
    label: str
    endonym: str
    voice: str
    silence_duration_ms: int
    measured: bool


class SeniorRequest(BaseModel):
    name: str
    name_reading: str = ""
    birth_year: int | None = None
    birthplace: str = ""
    family: list[str] = Field(default_factory=list)
    language: str = "ja"
    pronouns: Literal["", "she", "he", "they"] = ""
    """How English about them refers to them, as whoever entered them says.
    Left empty, it uses their name."""


class SeniorView(SeniorRequest):
    id: str


class QuoteView(BaseModel):
    text: str
    turn: int


class StoryView(BaseModel):
    id: str
    title: str
    summary: str
    life_stage: str
    approx_period: str
    people: list[str]
    places: list[str]
    quotes: list[QuoteView]
    visibility: str = "private"
    consent_quote: str = ""


class FamilyQuoteView(QuoteView):
    audio: str | None
    """Their voice saying it, and nothing else from the session. Neither the
    session nor its full recording is named anywhere on the family page, since
    the recording also holds whatever they chose not to share."""
    said: str = ""
    """All they said in the answer the quote comes from, which is what the clip
    plays, so a reader can check the quote against it. Not the interviewer's
    words around it: a question can name what they refused to talk about."""


class FamilyStoryView(BaseModel):
    id: str
    title: str
    summary: str
    life_stage: str
    approx_period: str
    people: list[str]
    places: list[str]
    quotes: list[FamilyQuoteView]


class FamilyChapter(BaseModel):
    life_stage: str
    stories: list[FamilyStoryView]


class FamilyQuestionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    asked_by: str = Field(min_length=1, max_length=40)
    """Who is asking, as the interviewer should say it: 孫のゆか, not just ゆか."""
    text: str = Field(min_length=1, max_length=300)


class FamilyQuestionView(BaseModel):
    """What a relative sees of their question.

    `status` is only ever "waiting" or "asked". A question held back because it
    touches something the senior refused is reported as waiting, since telling
    the family otherwise would tell them what was refused.
    """

    id: str
    asked_by: str
    text: str
    status: Literal["waiting", "asked"]
    answered_in: list[str]
    """Ids of shared stories that hold the answer. Never a private one."""


class FamilyView(BaseModel):
    senior: SeniorView
    chapters: list[FamilyChapter]
    withheld: int
    """Stories the person has not agreed to share. Counted, never shown."""
    questions: list[FamilyQuestionView] = Field(default_factory=list)
    writing: bool = False
    """A conversation is still being written up, so more may be on its way."""
    showcase: bool = False
    """The page the start page shows every visitor. Read-only: a question sent
    from it would wait forever, and every visitor would read the others'."""
    visitor: bool = False
    """Their own persona, made from the start page: the page offers to talk again."""


class PlanView(BaseModel):
    story_so_far: str
    next_questions: list[str]
    avoid_topics: list[str]


class SessionRequest(BaseModel):
    """Unset tuning falls back to the language's own defaults, so a value found
    while testing in French never becomes the one a Japanese speaker gets."""

    senior_id: str | None = None
    voice: str | None = None
    silence_duration_ms: int | None = Field(default=None, ge=200, le=8000)
    end_of_speech_sensitivity: Literal["LOW", "HIGH"] = "LOW"


class SessionResponse(BaseModel):
    session_id: str
    senior_id: str | None = None
    resuming: bool = False
    token: str
    model: str
    expires_at: datetime.datetime
    voice: str
    silence_duration_ms: int
    language: str
    opening: str
    closing: str
    """Sent when the clock says, or when a visitor presses Finish."""
    close_after_seconds: int
    check_in: str = ""
    """A visitor's timed cue in place of `closing`, asking whether to go on.
    Empty for everyone else, whose clock sends `closing`."""


class TurnView(BaseModel):
    speaker: str
    text: str
    started_at: float


class SessionSummary(BaseModel):
    id: str
    status: str
    started_at: datetime.datetime
    duration_seconds: float | None
    voice: str
    silence_duration_ms: int
    input_label: str
    turns: int
    has_audio: bool
    can_process: bool
    """Whether reading it may be started again: it failed, or it stalled."""


class SessionDetail(SessionSummary):
    model: str
    end_of_speech_sensitivity: str
    transcript: list[TurnView]
    stories: list[StoryView]
    processing_error: str | None = None
    screen_consent: str | None = None
    """What a visitor chose on the end screen for stories with no answer aloud."""


@router.get("/voices")
def list_voices() -> dict[str, str]:
    return VOICES


@router.get("/languages")
def list_languages() -> list[LanguageView]:
    return [LanguageView(**language.__dict__) for language in LANGUAGES.values()]


@router.get("/seniors")
def list_seniors(store: Annotated[Store, Depends(get_store)]) -> list[SeniorView]:
    return [SeniorView(**senior.__dict__) for senior in store.list_seniors()]


@router.post("/seniors")
def add_senior(request: SeniorRequest, store: Annotated[Store, Depends(get_store)]) -> SeniorView:
    senior_id = store.add_senior(**request.model_dump())
    return SeniorView(id=senior_id, **request.model_dump())


@router.get("/seniors/{senior_id}/plan")
def read_plan(senior_id: str, store: Annotated[Store, Depends(get_store)]) -> PlanView:
    if store.get_senior(senior_id) is None:
        raise HTTPException(status_code=404, detail=f"No senior {senior_id}")
    return PlanView(**store.get_plan(senior_id).__dict__)


@router.post("/sessions")
def create_session(
    request: SessionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> SessionResponse:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="KATARIBE_GEMINI_API_KEY is not configured")
    if request.voice is not None and request.voice not in VOICES:
        raise HTTPException(status_code=422, detail=f"Unknown voice: {request.voice}")

    # What the interviewer already knows about this person, and what it meant to
    # ask today. Locked into the token with everything else.
    context = ""
    plan = None
    senior = None
    waiting: list[FamilyQuestion] = []
    if request.senior_id:
        senior = store.get_senior(request.senior_id)
        if senior is None:
            raise HTTPException(status_code=404, detail=f"No senior {request.senior_id}")
        plan = store.get_plan(senior.id)
        # Oldest first, and only two: a session is five to ten minutes, and a
        # queue of relatives' questions would crowd out her own stories.
        waiting = store.family_questions(senior.id, status="pending")[:2]
        # Stories no one has yet asked whether the family may read, most often
        # because the last conversation ended before its close. The latest few:
        # the question at the close should stay one question.
        told = store.stories_for_senior(senior.id)
        unasked = [story for story in told if not story.asked_to_share][-3:]
        context = brain.context_for(senior, plan, waiting, unasked)

    # A stranger trying it for a few minutes is asked whether to go on, rather
    # than closed on, and asked about sharing on its own.
    spoken = get(senior.language if senior else None)
    trial = bool(senior and senior.visitor and spoken.visitor_rules)
    if trial:
        context = f"{context}\n\n{spoken.visitor_rules}"

    # The person's language decides the prompt, the locale and the defaults.
    base = InterviewTuning.for_language(senior.language if senior else None)
    tuning = InterviewTuning(
        voice=request.voice or base.voice,
        silence_duration_ms=request.silence_duration_ms or base.silence_duration_ms,
        end_of_speech_sensitivity=request.end_of_speech_sensitivity,
        language=base.language,
    )

    credentials = mint_session_credentials(settings, tuning, context)
    session_id = store.start(
        model=credentials.model,
        voice=tuning.voice,
        silence_duration_ms=tuning.silence_duration_ms,
        end_of_speech_sensitivity=tuning.end_of_speech_sensitivity,
        senior_id=request.senior_id,
        carried_questions=[q.id for q in waiting],
    )

    return SessionResponse(
        session_id=session_id,
        senior_id=request.senior_id,
        resuming=bool(plan and not plan.is_empty),
        token=credentials.token,
        model=credentials.model,
        expires_at=credentials.expires_at,
        voice=tuning.voice,
        silence_duration_ms=tuning.silence_duration_ms,
        language=tuning.language,
        opening=spoken.opening,
        closing=spoken.visitor_finish if trial else spoken.closing,
        close_after_seconds=settings.visitor_close_after_seconds
        if senior and senior.visitor
        else settings.close_after_seconds,
        check_in=spoken.visitor_check_in if trial else "",
    )


PART_LIMIT = 30 * 1024 * 1024
"""Bytes in one part of a recording. Cloud Run refuses any request over 32 MiB;
the browser sends 16 MiB."""
MAX_PARTS = 32
"""Cloud Storage joins at most 32 objects in one go: 512 MiB, an hour and a half."""


@router.put("/sessions/{session_id}/recording/parts/{index}", status_code=204)
async def upload_recording_part(
    session_id: str, index: int, request: Request, store: Annotated[Store, Depends(get_store)]
) -> None:
    """One piece of a recording. A ten-minute session is nearly twice what Cloud
    Run accepts in a request, so it arrives in parts, joined when the
    transcript follows. A PUT, so a part that failed can simply be sent again."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")
    if session.ended_at is not None:
        raise HTTPException(status_code=409, detail=f"Session {session_id} is already kept")
    if not 0 <= index < MAX_PARTS:
        raise HTTPException(status_code=422, detail=f"Part {index} is out of range")
    data = await request.body()
    if len(data) > PART_LIMIT:
        raise HTTPException(status_code=413, detail=f"A part may be at most {PART_LIMIT} bytes")
    store.save_audio_part(session_id, index, data)


@router.post("/sessions/{session_id}/recording", status_code=204)
async def upload_recording(
    session_id: str,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
    transcript: Annotated[str, Form()],
    duration_seconds: Annotated[float, Form()],
    input_label: Annotated[str, Form()] = "microphone",
    audio: Annotated[UploadFile | None, File()] = None,
    audio_parts: Annotated[int, Form(ge=0, le=MAX_PARTS)] = 0,
) -> None:
    """The transcript, and either the recording itself or the number of parts
    it was sent in. Parts are joined first: if any is missing nothing is kept
    yet, and the browser, which still holds everything, can send it again."""
    if store.get(session_id) is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")

    try:
        turns = [Turn(**turn) for turn in json.loads(transcript)]
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"Bad transcript: {error}") from error

    if audio is None and audio_parts:
        try:
            store.join_audio_parts(session_id, audio_parts)
        except MissingAudioParts as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    store.finish(
        session_id,
        turns=turns,
        audio=await audio.read() if audio else None,
        duration_seconds=duration_seconds,
        input_label=input_label,
    )
    # Extraction takes seconds and can fail. Neither should cost the upload,
    # which until now held the only copy of the recording.
    store.set_status(session_id, "queued")
    background.add_task(process_session, settings, store, session_id)


@router.post("/sessions/{session_id}/process", status_code=202)
def process_again(
    session_id: str,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> None:
    """Reads a session again whose reading failed, or was lost to a restart."""
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")
    if not can_retry(session, datetime.datetime.now(tz=datetime.UTC)):
        raise HTTPException(
            status_code=409, detail=f"Session {session_id} cannot be read again ({session.status})"
        )
    store.set_status(session_id, "queued")
    background.add_task(process_session, settings, store, session_id)


@router.get("/sessions")
def list_sessions(store: Annotated[Store, Depends(get_store)]) -> list[SessionSummary]:
    now = datetime.datetime.now(tz=datetime.UTC)
    return [
        SessionSummary(
            id=session.id,
            status=session.status,
            started_at=session.started_at,
            duration_seconds=session.duration_seconds,
            voice=session.voice,
            silence_duration_ms=session.silence_duration_ms,
            input_label=session.input_label,
            turns=len(session.turns),
            has_audio=store.has_audio(session.id),
            can_process=can_retry(session, now),
        )
        for session in store.list_sessions()
    ]


@router.get("/sessions/{session_id}")
def read_session(session_id: str, store: Annotated[Store, Depends(get_store)]) -> SessionDetail:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}")
    return SessionDetail(
        id=session.id,
        status=session.status,
        started_at=session.started_at,
        duration_seconds=session.duration_seconds,
        voice=session.voice,
        silence_duration_ms=session.silence_duration_ms,
        input_label=session.input_label,
        turns=len(session.turns),
        has_audio=store.has_audio(session.id),
        can_process=can_retry(session, datetime.datetime.now(tz=datetime.UTC)),
        model=session.model,
        end_of_speech_sensitivity=session.end_of_speech_sensitivity,
        transcript=[TurnView(**turn.__dict__) for turn in session.turns],
        stories=[
            StoryView(
                id=story.id,
                title=story.title,
                summary=story.summary,
                life_stage=story.life_stage,
                approx_period=story.approx_period,
                people=story.people,
                places=story.places,
                quotes=[QuoteView(**q.__dict__) for q in story.quotes],
                visibility=story.visibility,
                consent_quote=story.consent_quote,
            )
            for story in store.stories_for_session(session_id)
        ],
        processing_error=session.processing_error,
        screen_consent=session.screen_consent,
    )


@router.get("/family/{senior_id}")
def read_family_view(
    senior_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> FamilyView:
    """Only what the person agreed to share, grouped into chapters.

    The filtering happens in the query, not in the caller, so there is no way to
    reach this endpoint and accidentally receive a private story.
    """
    senior = store.get_senior(senior_id)
    if senior is None:
        raise HTTPException(status_code=404, detail=f"No senior {senior_id}")

    shared = store.stories_for_senior(senior_id, shared_only=True)
    everything = store.stories_for_senior(senior_id)
    recorded = {s.session_id for s in shared if store.has_audio(s.session_id)}
    transcripts: dict[str, list[Turn]] = {}

    def answer(session_id: str, turn: int) -> str:
        if session_id not in transcripts:
            session = store.get(session_id)
            transcripts[session_id] = session.turns if session else []
        turns = transcripts[session_id]
        if 0 <= turn < len(turns) and turns[turn].speaker == "senior":
            return turns[turn].text
        return ""

    chapters = []
    for stage in LIFE_STAGES:
        in_stage = [s for s in shared if s.life_stage == stage]
        if not in_stage:
            continue
        chapters.append(
            FamilyChapter(
                life_stage=stage,
                stories=[
                    FamilyStoryView(
                        id=story.id,
                        title=story.title,
                        summary=story.summary,
                        life_stage=story.life_stage,
                        approx_period=story.approx_period,
                        people=story.people,
                        places=story.places,
                        quotes=[
                            FamilyQuoteView(
                                text=quote.text,
                                turn=quote.turn,
                                audio=f"/api/family/{senior_id}/stories/{story.id}/quotes/{i}/audio"
                                if story.session_id in recorded
                                else None,
                                said=answer(story.session_id, quote.turn),
                            )
                            for i, quote in enumerate(story.quotes)
                        ],
                    )
                    for story in in_stage
                ],
            )
        )

    shared_ids = {story.id for story in shared}
    questions = [_family_safe(q, shared_ids) for q in store.family_questions(senior_id)]
    now = datetime.datetime.now(tz=datetime.UTC)
    return FamilyView(
        senior=SeniorView(**senior.__dict__),
        chapters=chapters,
        withheld=len(everything) - len(shared),
        questions=questions,
        # A reading that stalled is not on its way, and saying so would leave
        # them waiting for nothing.
        writing=any(
            s.status in ("queued", "processing") and not can_retry(s, now)
            for s in store.sessions_for_senior(senior_id)
        ),
        showcase=senior_id == settings.showcase_senior,
        visitor=senior.visitor,
    )


@router.get("/family/{senior_id}/translations")
def read_family_translations(
    senior_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> dict[str, str]:
    """English for what the family page shows, by the text, when the person
    speaks another language, so that someone without it, such as a judge, can
    follow. Shown under the original, never in its place.

    Read after the page rather than with it, so the page never waits on a
    translation: the first reading of a text takes seconds, and after that it
    is kept. Only what the page shows is translated, never a private story."""
    view = read_family_view(senior_id, settings, store)
    senior = store.get_senior(senior_id)
    assert senior is not None, "checked by read_family_view"
    shown = [view.senior.name, view.senior.birthplace]
    for chapter in view.chapters:
        for told in chapter.stories:
            shown += [told.title, told.summary, told.approx_period, *told.people, *told.places]
            shown += [text for quote in told.quotes for text in (quote.text, quote.said)]
    for question in view.questions:
        shown += [question.asked_by, question.text]
    return _in_english(settings, store, senior, shown)


def _in_english(
    settings: Settings, store: Store, senior: Senior, texts: list[str]
) -> dict[str, str]:
    """Each text translated once, the first time a page shows it, and kept. A
    page that cannot be translated just now is shown without, not at all."""
    if senior.language == "en" or not settings.gemini_api_key:
        return {}
    wanted = list(dict.fromkeys(text for text in texts if text))
    kept = store.translations(senior.id)
    missing = [text for text in wanted if text not in kept]
    if missing:
        try:
            english = brain.translate(settings, missing, get(senior.language), senior)
        except Exception:
            log.exception("could not translate the family page of %s", senior.id)
        else:
            new = dict(zip(missing, english, strict=True))
            store.save_translations(senior.id, new)
            kept |= new
    return {text: kept[text] for text in wanted if text in kept}


def _family_safe(question: FamilyQuestion, shared_ids: set[str]) -> FamilyQuestionView:
    return FamilyQuestionView(
        id=question.id,
        asked_by=question.asked_by,
        text=question.text,
        status="asked" if question.status == "asked" else "waiting",
        answered_in=[sid for sid in question.answer_story_ids if sid in shared_ids],
    )


@router.post("/family/{senior_id}/questions")
def ask_a_question(
    senior_id: str,
    request: FamilyQuestionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[Store, Depends(get_store)],
) -> FamilyQuestionView:
    if store.get_senior(senior_id) is None:
        raise HTTPException(status_code=404, detail=f"No senior {senior_id}")
    if senior_id == settings.showcase_senior:
        raise HTTPException(status_code=403, detail="This page is read-only")

    # Screened before it is stored, so a question never sits waiting unchecked
    # against what she refused. If it cannot be checked, it is not taken.
    status = "pending"
    avoid = store.get_plan(senior_id).avoid_topics
    if avoid:
        draft = FamilyQuestion(
            id="new",
            senior_id=senior_id,
            asked_by=request.asked_by,
            text=request.text,
            status="pending",
            asked_in_session=None,
            answer_story_ids=[],
        )
        try:
            held = brain.screen(settings, [draft], avoid)
        except Exception as error:
            log.exception("could not screen a family question for %s", senior_id)
            raise HTTPException(
                status_code=503, detail="The question could not be sent just now."
            ) from error
        status = "held" if held else "pending"

    question_id = store.add_family_question(
        senior_id, asked_by=request.asked_by, text=request.text, status=status
    )
    stored = next(q for q in store.family_questions(senior_id) if q.id == question_id)
    return _family_safe(stored, set())


@router.get("/family/{senior_id}/stories/{story_id}/quotes/{index}/audio")
def read_quote_audio(
    senior_id: str, story_id: str, index: int, store: Annotated[Store, Depends(get_store)]
) -> Response:
    """Their voice saying one shared quote: the turn it came from, their channel
    only. The story is looked up among the shared ones, so a private story has
    no audio here to find, any more than it has text on the family page."""
    story = next(
        (s for s in store.stories_for_senior(senior_id, shared_only=True) if s.id == story_id),
        None,
    )
    if story is None or not 0 <= index < len(story.quotes):
        raise HTTPException(status_code=404, detail="No such quote")
    session = store.get(story.session_id)
    turn = story.quotes[index].turn
    if session is None or not 0 <= turn < len(session.turns):
        raise HTTPException(status_code=404, detail="No recording of this quote")
    recording = store.open_audio(story.session_id)
    if recording is None:
        raise HTTPException(status_code=404, detail="No recording of this quote")

    try:
        with recording:
            audio = clips.clip(recording, *clips.turn_window(session.turns, turn))
    except (wave.Error, EOFError, ValueError) as error:
        log.exception("could not cut a clip from %s", story.session_id)
        raise HTTPException(status_code=404, detail="No recording of this quote") from error
    return Response(content=audio, media_type="audio/wav")


@router.get("/sessions/{session_id}/audio")
def read_audio(session_id: str, store: Annotated[Store, Depends(get_store)]) -> StreamingResponse:
    """Streamed, not sent whole: a long session is bigger than Cloud Run lets a
    single unstreamed response be."""
    recording = store.open_audio(session_id)
    if recording is None:
        raise HTTPException(status_code=404, detail=f"No recording for {session_id}")

    def chunks() -> Iterator[bytes]:
        with recording:
            while chunk := recording.read(1 << 20):
                yield chunk

    return StreamingResponse(
        chunks(),
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="kataribe-{session_id}.wav"'},
    )

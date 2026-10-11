"""Runs the brain over a finished session.

Kept apart from the API so it can move to its own Cloud Run job later without
anything above it changing.
"""

import datetime
import logging
from dataclasses import replace

from kataribe import brain, clips
from kataribe.brain import Answer
from kataribe.config import Settings
from kataribe.languages import get
from kataribe.store import Plan, Senior, Session, Store, Story

log = logging.getLogger(__name__)

STALLED_AFTER = datetime.timedelta(minutes=5)
"""Reading a session takes seconds. One still queued or processing this long
after it was queued was lost, most likely to a restart: processing runs inside
the server, and a restart drops it without a word."""


def can_retry(session: Session, now: datetime.datetime) -> bool:
    """Whether reading this session may be started again.

    Never while a run may still be going, since two would race to write the same
    stories. Never for one already processed: its stories may be shared and
    asked about by now, and a second reading would replace them. And not for a
    session with nothing said in it, or nobody to attach stories to.

    Stalled sessions are not picked up again on startup. Once deployed there may
    be several servers, and each would claim the same session.
    """
    if not session.turns or not session.senior_id:
        return False
    if session.status in ("queued", "processing"):
        # Timed from the status itself, not from the end of the session: a
        # session from last week queued again a second ago is not stalled.
        # Rows from before the status was timed fall back to the end.
        since = session.status_at or session.ended_at
        return since is not None and now - since > STALLED_AFTER
    return session.status in ("recorded", "failed")


def process_session(settings: Settings, store: Store, session_id: str) -> None:
    session = store.get(session_id)
    if session is None:
        return
    if not session.senior_id:
        store.set_status(session_id, "skipped", "No senior attached to this session")
        return

    senior = store.get_senior(session.senior_id)
    if senior is None:
        store.set_status(session_id, "failed", f"No senior {session.senior_id}")
        return

    store.set_status(session_id, "processing")
    try:
        # Only what this session's interviewer was given. Another question may
        # have arrived since, and "asked" must mean the interviewer asked it.
        carried = [
            q for q in store.family_questions(senior.id) if q.id in session.carried_questions
        ]
        # What today could decide about other conversations' stories: a shared
        # one taken back, or one never asked about agreed to at the close.
        earlier = [
            story
            for story in store.stories_for_senior(senior.id)
            if story.session_id != session_id and (story.shared or not story.asked_to_share)
        ]
        spoken = get(senior.language)
        extraction = brain.extract(
            settings, senior, session.turns, family_questions=carried, earlier=earlier
        )
        stories, dropped = brain.verify(extraction, session.turns, spoken)
        decisions, unproven = brain.verify_earlier(
            extraction.earlier, earlier, session.turns, spoken
        )
        stories, decisions, unheard = _bear_out(
            settings, store, senior, session, stories, decisions
        )
        dropped += unproven + unheard
        if dropped:
            # Loud on purpose: a quote the person never said is the failure this
            # product can least afford, and the guard existing is not the same
            # as the guard never firing.
            log.warning(
                "session %s: held back %d quote(s) the transcript or recording does not"
                " bear out: %s",
                session_id,
                len(dropped),
                dropped,
            )

        stored = [replace(story, senior_id=senior.id, session_id=session_id) for story in stories]
        store.replace_stories(session_id, senior.id, stored)

        for decision in decisions:
            log.info("session %s: story %s %s", session_id, decision.story_id, decision.decision)
            agreed = decision.decision == "agreed"
            store.set_sharing(
                decision.story_id,
                visibility="family" if agreed else "private",
                consent_quote=decision.words if agreed else "",
            )

        # Close the loop on whatever the family asked. The answer is linked, not
        # copied: the family view shows it only if that story was shared.
        # `verify` keeps every story it is given, so extraction's indexes hold.
        for raised in extraction.raised:
            if not 0 <= raised.question < len(carried):
                continue
            answers = [stored[i].id for i in raised.stories if 0 <= i < len(stored)]
            store.mark_question_asked(carried[raised.question].id, session_id, answers)

        previous = store.get_plan(senior.id)
        avoid = sorted(set(previous.avoid_topics) | set(extraction.refused_topics))

        # Something refused today may make a question sent last week unaskable.
        if set(avoid) != set(previous.avoid_topics):
            still_waiting = store.family_questions(senior.id, status="pending")
            for question_id in brain.screen(settings, still_waiting, avoid):
                store.set_question_status(question_id, "held")

        everything = store.stories_for_senior(senior.id)
        planned = brain.plan_next(settings, senior, everything, avoid)

        store.save_plan(
            senior.id,
            Plan(
                story_so_far=planned.story_so_far,
                next_questions=planned.next_questions,
                avoid_topics=avoid,
            ),
        )
        store.set_status(session_id, "processed")
    except Exception as error:  # noqa: BLE001
        log.exception("session %s could not be processed", session_id)
        store.set_status(session_id, "failed", f"{type(error).__name__}: {error}")


def _bear_out(
    settings: Settings,
    store: Store,
    senior: Senior,
    session: Session,
    stories: list[Story],
    answers: list[Answer],
) -> tuple[list[Story], list[Answer], list[str]]:
    """Holds back what the recording does not bear out, after the transcript has.

    Every quote is checked against the clip the family would play for it, and
    every agreement to share against the clip of the turn it was said in. A
    quote that fails is dropped; an agreement that fails leaves the story
    private and still to be asked about. Without a recording there is nothing
    to check against, and nothing for the family to play either.
    """
    if not store.has_audio(session.id):
        log.warning("session %s: no recording, so nothing was checked against one", session.id)
        return stories, answers, []

    claims: list[tuple[str, int]] = []
    for story in stories:
        claims += [(quote.text, quote.turn) for quote in story.quotes]
        if story.shared:
            claims.append(_consent_claim(story, session))
    claims += [(a.words, a.turn) for a in answers if a.decision == "agreed" and a.turn is not None]
    if not claims:
        return stories, answers, []

    verdicts = brain.confirm(
        settings, senior, [(text, _clip(store, session, turn)) for text, turn in claims]
    )
    borne = {claim for claim, (same, _) in zip(claims, verdicts, strict=True) if same}
    unheard = [
        f"(heard 「{heard}」) {text}"
        for (text, _), (same, heard) in zip(claims, verdicts, strict=True)
        if not same
    ]

    checked: list[Story] = []
    for story in stories:
        story = replace(story, quotes=[q for q in story.quotes if (q.text, q.turn) in borne])
        if story.shared and _consent_claim(story, session) not in borne:
            story = replace(story, visibility="private", consent_quote="", asked_to_share=False)
        checked.append(story)
    kept = [a for a in answers if a.decision != "agreed" or (a.words, a.turn) in borne]
    return checked, kept, unheard


def _consent_claim(story: Story, session: Session) -> tuple[str, int]:
    turn = brain.where_said(story.consent_quote, session.turns)
    assert turn is not None, "verify shares a story only with consent it found"
    return story.consent_quote, turn


def _clip(store: Store, session: Session, turn: int) -> bytes:
    recording = store.open_audio(session.id)
    if recording is None:
        raise RuntimeError(f"The recording of {session.id} went missing while it was read")
    with recording:
        return clips.clip(recording, *clips.turn_window(session.turns, turn))

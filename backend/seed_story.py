"""Puts one story into the store, for the browser tests to read back.

The family page's promise is that nothing private reaches it, and that is worth
testing from the page rather than only from the API. Doing so needs a story at a
known visibility, and there is no endpoint that creates one — deliberately. A
write path into the family view is the last thing this product should grow, so
the tests reach the store directly instead, through the same code the
processing pipeline uses.

Given `--question`, the story is also recorded as the answer to a question from
the family, as processing does when the interviewer put one to her.

    uv run python seed_story.py --senior-id abc --visibility family ...
    uv run python seed_story.py ... --asked-by 孫のゆか --question 工場のことを教えて
"""

import argparse
import uuid
from pathlib import Path

from kataribe.store import Quote, Store, Story, Turn


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("var"))
    parser.add_argument("--senior-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--life-stage", default="子供時代")
    parser.add_argument("--quote", required=True)
    parser.add_argument("--visibility", choices=["private", "family"], default="private")
    parser.add_argument("--question", help="a family question this story answers")
    parser.add_argument("--asked-by", default="孫のゆか")
    args = parser.parse_args()

    store = Store(args.data_dir)
    session_id = store.start(
        model="seeded",
        voice="Sulafat",
        silence_duration_ms=5000,
        end_of_speech_sensitivity="LOW",
        senior_id=args.senior_id,
    )
    store.finish(
        session_id,
        turns=[
            Turn(speaker="ai", text="こんにちは。", started_at=2.0),
            Turn(speaker="senior", text=args.quote, started_at=14.0),
        ],
        audio=None,
        duration_seconds=15.0,
        input_label="seeded",
    )
    story_id = uuid.uuid4().hex[:12]
    store.replace_stories(
        session_id,
        args.senior_id,
        [
            Story(
                id=story_id,
                senior_id=args.senior_id,
                session_id=session_id,
                title=args.title,
                summary=args.summary,
                life_stage=args.life_stage,
                approx_period="",
                people=[],
                places=[],
                quotes=[Quote(text=args.quote, turn=1)],
                visibility=args.visibility,
                consent_quote="ええ、かまいませんよ。" if args.visibility == "family" else "",
            )
        ],
    )
    if args.question:
        question_id = store.add_family_question(
            args.senior_id, asked_by=args.asked_by, text=args.question
        )
        store.mark_question_asked(question_id, session_id, [story_id])
    print(session_id)


if __name__ == "__main__":
    main()

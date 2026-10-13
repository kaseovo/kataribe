"""Forgets a person entirely: their sessions and every recording, their stories,
plan and family questions.

It is what the deployed smoke test uses to leave the live data as it found it,
and the answer when a family asks for someone to be removed. It works on
whichever store the settings name, so for the deployed one:

    KATARIBE_STORAGE=cloud KATARIBE_GCP_PROJECT=... KATARIBE_RECORDINGS_BUCKET=... \\
        uv run python forget.py --senior-id abc

`--visitors` forgets every persona a stranger made from the start page, which the
start page promises once judging is over. It never touches the team's people,
the showcase among them: they are not visitors.
"""

import argparse

from kataribe.config import Settings
from kataribe.store import LocalStore, Store


def store_for(settings: Settings) -> Store:
    if settings.storage == "cloud":
        from kataribe.cloud_store import CloudStore

        return CloudStore(
            project=settings.gcp_project,
            database=settings.firestore_database,
            bucket=settings.recordings_bucket,
        )
    return LocalStore(settings.data_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--senior-id")
    who.add_argument("--visitors", action="store_true", help="every visitor persona")
    args = parser.parse_args()

    settings = Settings()
    store = store_for(settings)
    if args.visitors:
        visitors = [senior for senior in store.list_seniors() if senior.visitor]
        for senior in visitors:
            store.forget_senior(senior.id)
        print(f"Forgot {len(visitors)} visitor persona(s) from the {settings.storage} store")
        return

    senior = store.get_senior(args.senior_id)
    if senior is None:
        raise SystemExit(f"No one with id {args.senior_id} in the {settings.storage} store")

    gone = store.forget_senior(args.senior_id)
    print(f"Forgot {senior.name} from the {settings.storage} store: {gone}")


if __name__ == "__main__":
    main()

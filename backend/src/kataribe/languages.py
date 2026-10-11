"""Languages the interviewer can work in.

Japanese is the product. French and English exist so the whole loop can be
exercised without a Japanese speaker in the room — turn-taking, following a
change of subject, backing off, extraction, memory. All of that is the same
behaviour in any language.

What is not the same: honorific register, and the kanji homophones that make a
name come back misspelled. Those have no French or English equivalent, so a
green run in a development language says nothing about them.

Each language keeps its own defaults for exactly that reason. A pause length
that feels right in French must not become the one an elderly Japanese speaker
gets — only the Japanese figure below was measured against Japanese speech.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    locale: str
    label: str
    endonym: str
    prompt_file: str
    voice: str
    silence_duration_ms: int
    measured: bool
    """Whether silence_duration_ms came from a measurement or is a starting guess."""

    opening: str
    """A stage direction sent when the session opens, so the interviewer speaks
    first rather than waiting to be spoken to. Nobody should have to work out
    that they are meant to start."""

    closing: str
    """A stage direction sent once the conversation has run its time, so it ends
    with the close: thanks, the question about sharing, and goodbye. The model
    keeps no clock of its own, and left to judge it closed after two minutes."""

    alphabet: str
    """Every character this language is written in, as the body of a regex class.
    A quote holding anything else is a recognition glitch, such as a Korean
    particle in the middle of Japanese, and is not shown as the person's words."""


LATIN = r"\u0020-\u007e\u00a0-\u017f\u2000-\u206f"
"""ASCII, Latin-1 and Latin Extended-A (é, ç, œ), and typographic punctuation."""

LANGUAGES: dict[str, Language] = {
    "ja": Language(
        code="ja",
        locale="ja-JP",
        label="Japanese",
        endonym="日本語",
        prompt_file="interviewer_ja.md",
        voice="Sulafat",
        # Measured: 3500ms cut into a 2.5s pause for thought, 6000ms sat
        # through 4s. See docs/roadmap.md.
        silence_duration_ms=5000,
        measured=True,
        opening="（その方が席につかれました。こちらから、やさしく声をかけてください。）",
        closing="（そろそろお開きの時間です。今のお話がひと区切りついたら、終わり方のとおりにお開きにしてください。）",
        # Kana, kanji, Japanese and full-width punctuation, and plain ASCII for
        # the odd number or acronym.
        alphabet=(
            r"\u0020-\u007e\u00a0\u2000-\u206f\u3000-\u303f\u3040-\u309f\u30a0-\u30ff"
            r"\u31f0-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef"
        ),
    ),
    "fr": Language(
        code="fr",
        locale="fr-FR",
        label="French",
        endonym="Français",
        prompt_file="interviewer_fr.md",
        voice="Sulafat",
        # A starting point, not a measurement. Nobody has run the pause test
        # against French speech; this was lowered from 2500 because the wait
        # between turns felt dead, and French is only ever used for testing.
        silence_duration_ms=1500,
        measured=False,
        opening="(La personne vient de s'asseoir. Adressez-lui la parole doucement.)",
        closing=(
            "(Il est bientôt l'heure de conclure. Quand son récit arrive à une pause, "
            "concluez comme indiqué.)"
        ),
        alphabet=LATIN,
    ),
    "en": Language(
        code="en",
        locale="en-US",
        label="English",
        endonym="English",
        prompt_file="interviewer_en.md",
        voice="Sulafat",
        silence_duration_ms=2500,
        measured=False,
        opening="(They have just sat down. Speak to them gently, first.)",
        closing="(It is nearly time to close. When their story pauses, close as described.)",
        alphabet=LATIN,
    ),
}

DEFAULT = LANGUAGES["ja"]


def get(code: str | None) -> Language:
    return LANGUAGES.get(code or "", DEFAULT)

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

    visitor_rules: str = ""
    """Added to a visitor's prompt: a stranger trying it for a few minutes, such
    as a judge. They are asked whether to go on rather than closed on, and the
    question about sharing is asked on its own, since a judge lost it in the
    middle of the full close. Empty where visitors are not offered the language;
    they then get the close a senior gets."""

    visitor_check_in: str = ""
    """A visitor's timed stage direction, in place of `closing`: go on, or stop?"""

    visitor_finish: str = ""
    """A visitor's stage direction when they press Finish: they want to stop."""


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
        # Not yet reviewed by a native speaker; see docs/demo/japanese-review.md.
        visitor_rules="""## 短いお試し

この方は、ご自分の人生を題材に、数分だけお試しで話していらっしゃいます。
前回までのお話がここに書かれていなければ、今日が初めてです。「また」とは言わないでください。

「終わり方」の代わりに、次のとおりにしてください。

- そろそろ時間だというメモが届いたら、お話がひと区切りついたところで、
  このまま続けるか、今日はここまでにするかだけをお尋ねください。そのときは、ほかのことは言わないでください。
  続けるとおっしゃったら、そのまま続けて、もう一度は聞かないでください。
- 終わりにしたいときは、ひとつだけお尋ねください。
  ご本人がそうおっしゃったときも、「おわる」が押されたというメモが届いたときも同じです。
  今日のお話をひとことで挙げて、ご家族に読んでもらってよいか、
  それともご自分だけのものにしておきたいか。
  「終わる前にひとつだけ。ご実家のお話、ご家族に読んでいただいてもよろしいですか。それとも、ご自分だけのものにしておきましょうか」
  そのときは、お礼も次回のお話も、まだ言わないでください。
- お答えをいただいたら、ひとことお礼を言って、お別れのあいさつをしてください。
  はっきりしないお答えでも、もう一度は聞かずに、あいさつだけにしてください。""",
        visitor_check_in="（そろそろ時間です。お話がひと区切りついたら、続けるか、ここまでにするかだけをお尋ねください。）",
        visitor_finish="（「おわる」が押されました。ここまでにしたいとのことです。ご家族に読んでもらってよいかだけをお尋ねください。）",
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
        visitor_rules="""## A short trial

This person is trying you for a few minutes, on their own life.
Unless this prompt tells you about earlier conversations, this is the first: do not say "again".

In place of "How to close":

- When a note says time is nearly up, wait for a pause in their story, then ask only whether
  they would like to keep going or stop here for today. Nothing else in that turn.
  If they keep going, carry on, and do not ask again.
- When they want to stop, because they say so or a note says they pressed Finish, ask one thing
  only: whether their family may read today's story, named in a few words, or whether they would
  rather keep it private. "Before we stop: may your family read what you told me about your
  childhood house, or would you rather keep it private?" Nothing else in that turn: no thanks
  yet, no topic for next time.
- Once they have answered, thank them in a sentence and say goodbye. If the answer was not
  clear, do not ask again; just say goodbye.""",
        visitor_check_in=(
            "(Time is nearly up. When their story pauses, ask only whether they would like to "
            "keep going or stop here.)"
        ),
        visitor_finish=(
            "(They pressed Finish: they want to stop. Ask only whether their family may read "
            "today's story, or they would rather keep it private.)"
        ),
        alphabet=LATIN,
    ),
}

DEFAULT = LANGUAGES["ja"]


def get(code: str | None) -> Language:
    return LANGUAGES.get(code or "", DEFAULT)

"""Turns a finished conversation into stories, and plans the next one.

Every quote an extraction produces is checked against the transcript before it
is stored. The model is asked for the person's own words, and a quote that is
not found verbatim is dropped rather than kept — a memoir is the one place a
plausible-sounding paraphrase must not end up.
"""

import re
import uuid
from dataclasses import dataclass
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from kataribe.config import Settings
from kataribe.languages import DEFAULT, Language, get
from kataribe.store import LIFE_STAGES, FamilyQuestion, Plan, Quote, Senior, Story, Turn

NOISE = re.compile(r"[\s、。「」『』・,.!?！？…ー]")


class ExtractedQuote(BaseModel):
    text: str = Field(description="話し手が言ったとおりの言葉。一字も変えないこと。")
    turn: int = Field(description="その言葉があった発言の番号")


class ExtractedStory(BaseModel):
    title: str
    summary: str
    life_stage: str
    approx_period: str
    people: list[str]
    places: list[str]
    quotes: list[ExtractedQuote]
    consent_quote: str = Field(
        default="",
        description=(
            "The speaker's own words agreeing their family may read this story, "
            "exactly as said. Empty unless they clearly agreed."
        ),
    )
    asked_to_share: bool = Field(
        default=False,
        description=(
            "Whether the interviewer asked if their family may read this story, on its "
            "own or in a list, and they answered, whatever the answer. False if they "
            "gave no reply at all"
        ),
    )


class RaisedQuestion(BaseModel):
    question: int = Field(description="The number of the family question, as listed")
    stories: list[int] = Field(
        default_factory=list,
        description="Indexes into `stories` of whatever the speaker said in answer",
    )


class EarlierAnswer(BaseModel):
    story: int = Field(description="The number of the earlier story, as listed")
    decision: Literal["agreed", "declined", "withdrawn"]
    words: str = Field(default="", description="The speaker's own words, exactly as said")


class Extraction(BaseModel):
    stories: list[ExtractedStory]
    refused_topics: list[str]
    raised: list[RaisedQuestion] = Field(
        default_factory=list,
        description="Family questions the interviewer actually put to the speaker",
    )
    earlier: list[EarlierAnswer] = Field(
        default_factory=list,
        description="What the speaker decided today about stories from earlier conversations",
    )


class Heard(BaseModel):
    clip: int = Field(description="The number of the clip")
    heard: str = Field(description="What the speaker says in the clip, written down as heard")
    same: bool = Field(description="Whether they say the given words somewhere in the clip")


class Hearing(BaseModel):
    clips: list[Heard]


class Screening(BaseModel):
    hold: list[int] = Field(
        default_factory=list,
        description="Numbers of the questions that touch a topic never to raise",
    )


class NextPlan(BaseModel):
    story_so_far: str
    next_questions: list[str]


def _numbered(turns: list[Turn]) -> str:
    return "\n".join(
        f"[{i}] {'話し手' if t.speaker == 'senior' else '聞き手'}: {t.text}"
        for i, t in enumerate(turns)
    )


def _who(senior: Senior) -> str:
    facts = [f"お名前: {senior.name}"]
    if senior.name_reading:
        facts.append(f"読み: {senior.name_reading}")
    if senior.birth_year:
        facts.append(f"生まれ年: {senior.birth_year}年")
    if senior.birthplace:
        facts.append(f"出身: {senior.birthplace}")
    if senior.family:
        facts.append(f"ご家族: {'、'.join(senior.family)}")
    return "\n".join(facts)


def _earlier(stories: list[Story] | None) -> str:
    return "\n".join(
        f"[{i}] ({'shared with their family' if s.shared else 'not yet asked'}) "
        f"{s.title}: {s.summary}"
        for i, s in enumerate(stories or [])
    )


def _listed(questions: list[FamilyQuestion]) -> str:
    return "\n".join(f"[{i}] {q.asked_by}: {q.text}" for i, q in enumerate(questions))


def extract(
    settings: Settings,
    senior: Senior,
    turns: list[Turn],
    language: Language | None = None,
    family_questions: list[FamilyQuestion] | None = None,
    earlier: list[Story] | None = None,
) -> Extraction:
    """Instructions are in English; what it writes is in the language spoken.

    `earlier` lists stories from other conversations that today's could decide
    about: shared ones they might take back, and ones never asked about that the
    interviewer may have asked about at the close.

    One set of instructions rather than one per language: the rules here are
    about not inventing things, which is the same rule everywhere, and three
    copies would drift apart.
    """
    spoken = language or get(senior.language)
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            "Below is a recorded conversation in which an elderly person was "
            "asked about their life. Pull out the events of their life from it.\n\n"
            f"=== About this person (established facts) ===\n{_who(senior)}\n\n"
            f"=== The conversation ===\n{_numbered(turns)}\n\n"
            + (
                f"=== Questions their family sent in ===\n{_listed(family_questions)}\n\n"
                if family_questions
                else ""
            )
            + (
                f"=== Stories from earlier conversations ===\n{_earlier(earlier)}\n\n"
                if earlier
                else ""
            )
            + "=== How to do it ===\n"
            f"- Write everything in {spoken.label}, the language they spoke.\n"
            "- Only what the speaker actually said. Never the interviewer's words.\n"
            "- Do not fill in anything the conversation does not contain.\n"
            "- summary: the story in a few plain, natural sentences, as their\n"
            "  family will read it. About them, in the third person, by name:\n"
            "  never 'I', since these are not their words, and never 'he' or\n"
            "  'she'. Every fact must be one they said. Add no detail, feeling\n"
            "  or judgement ('wonderful', 'cherished'), and do not assert a\n"
            "  relationship they did not state: if they said 'my father's\n"
            "  factory' it is their father's factory, not 'the family\n"
            "  factory'. Keep their word for each thing rather than swapping in\n"
            "  another. What you may add is only what turns their words into\n"
            "  sentences: who did it, linking words, tense and order. Do not\n"
            "  string their phrases together as they came, and do not keep their\n"
            "  grammar where it faltered: a halting phrase becomes a correct\n"
            "  sentence that means the same.\n"
            "- title: a few words naming the story, as a chapter heading would,\n"
            "  with their words for the things in it.\n"
            "- quotes must be the speaker's words exactly, not one character\n"
            "  changed. Never summarise or paraphrase inside a quote.\n"
            f"- life_stage must be one of: {', '.join(LIFE_STAGES)}\n"
            "- approx_period as far as the conversation shows it, and empty if\n"
            "  it does not.\n"
            "- If nothing has been told yet, leave stories empty.\n"
            "- consent_quote: if they were asked whether their family may read\n"
            "  this and clearly agreed, put their own words here, exactly as\n"
            "  said. One answer can cover several stories: if they were asked\n"
            "  about several at once and agreed, give each story they agreed to\n"
            "  the same words. A story they kept out ('but not the one about...')\n"
            "  gets none. Leave it empty if they were not asked, if they declined,\n"
            "  if they hesitated, if they agreed and then took it back, or if the\n"
            "  answer is at all unclear. A polite noise that is not an answer is\n"
            "  not agreement.\n"
            "- asked_to_share: true if the interviewer asked whether their family\n"
            "  may read this story, on its own or in a list, and they answered:\n"
            "  yes, no, and an unsure or hesitant reply all count as an answer.\n"
            "  False if they were not asked, or were asked and gave no reply at\n"
            "  all, because the conversation ended there or they went on to\n"
            "  something else without answering.\n"
            "- refused_topics: anything they said they did not want to discuss.\n"
            "- raised: for each family question listed above that the interviewer\n"
            "  actually put to them in this conversation, its number, and the\n"
            "  indexes of the stories that hold their answer. Leave a question out\n"
            "  if it was not asked. If it was asked but they did not answer, list\n"
            "  it with no stories.\n"
            "- earlier: for the stories from earlier conversations listed above.\n"
            "  One marked shared that they asked to take back, or not to show their\n"
            "  family: decision 'withdrawn', with their words. One marked not yet\n"
            "  asked that the interviewer asked about today: 'agreed', with their\n"
            "  words exactly as said, only if they clearly agreed; 'declined' if\n"
            "  they answered any other way. Leave out a story they were asked about\n"
            "  but gave no reply to, and every story nothing was said about."
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Extraction,
            temperature=0.0,
        ),
    )
    result = response.parsed
    if not isinstance(result, Extraction):
        raise RuntimeError(f"Extraction returned nothing usable: {response.text!r}")
    return result


def where_said(text: str, turns: list[Turn]) -> int | None:
    """The turn in which the person said `text`, ignoring punctuation and spacing."""
    needle = NOISE.sub("", text)
    if not needle:
        return None
    return next(
        (
            i
            for i, turn in enumerate(turns)
            if turn.speaker == "senior" and needle in NOISE.sub("", turn.text)
        ),
        None,
    )


def foreign(text: str, language: Language) -> str:
    """Characters in `text` that its language is never written in, if any."""
    return "".join(sorted(set(re.sub(f"[{language.alphabet}\\s]", "", text))))


def verify(
    extraction: Extraction, turns: list[Turn], language: Language = DEFAULT
) -> tuple[list[Story], list[str]]:
    """Keep only quotes that the person actually said. Returns stories and what was dropped.

    Said means found in their own turns of the transcript, and written only in
    their language: a transcript can glitch, and a quote copied from the glitch
    would be found in it all the same."""
    stories: list[Story] = []
    dropped: list[str] = []

    for extracted in extraction.stories:
        kept: list[Quote] = []
        for quote in extracted.quotes:
            if not NOISE.sub("", quote.text):
                continue
            where = where_said(quote.text, turns)
            odd = foreign(quote.text, language)
            if where is None:
                dropped.append(quote.text)
            elif odd:
                dropped.append(f"(not {language.label}: {odd}) {quote.text}")
            else:
                kept.append(Quote(text=quote.text, turn=where))

        stage = extracted.life_stage if extracted.life_stage in LIFE_STAGES else LIFE_STAGES[0]

        # Sharing a life story with a family is not something to infer. It
        # counts only when the person said so and we still have the words: an
        # agreement the model reports but cannot evidence is no agreement.
        consent = extracted.consent_quote
        agreed = (
            bool(NOISE.sub("", consent))
            and where_said(consent, turns) is not None
            and not foreign(consent, language)
        )
        if consent and not agreed:
            dropped.append(f"(consent) {consent}")

        stories.append(
            Story(
                id=uuid.uuid4().hex[:12],
                senior_id="",
                session_id="",
                title=extracted.title,
                summary=extracted.summary,
                life_stage=stage,
                approx_period=extracted.approx_period,
                people=extracted.people,
                places=extracted.places,
                quotes=kept,
                visibility="family" if agreed else "private",
                consent_quote=consent if agreed else "",
                # Words of agreement that cannot be evidenced may be a misheard
                # yes, or one that never happened: either way, ask again.
                asked_to_share=agreed or (extracted.asked_to_share and not consent),
            )
        )
    return stories, dropped


@dataclass(frozen=True)
class Answer:
    """What today's conversation decided about one earlier story."""

    story_id: str
    decision: str
    """agreed, declined or withdrawn"""
    words: str
    turn: int | None


def verify_earlier(
    answers: list[EarlierAnswer],
    earlier: list[Story],
    turns: list[Turn],
    language: Language = DEFAULT,
) -> tuple[list[Answer], list[str]]:
    """Today's decisions about earlier stories, held to the same terms as today's.

    Taking a story back needs no evidence: when in doubt, it stays private.
    Sharing one needs their words, found in the transcript like any consent, and
    an agreement that cannot be evidenced changes nothing, so the story is asked
    about again. Only a shared story can be taken back, and only one never asked
    about can be agreed to."""
    decided: list[Answer] = []
    dropped: list[str] = []
    for answer in answers:
        if not 0 <= answer.story < len(earlier):
            continue
        story = earlier[answer.story]
        turn = where_said(answer.words, turns)
        if answer.decision == "withdrawn":
            if story.shared:
                decided.append(Answer(story.id, "withdrawn", answer.words, turn))
        elif story.shared or story.asked_to_share:
            continue
        elif answer.decision == "agreed":
            if turn is None or foreign(answer.words, language):
                dropped.append(f"(consent) {answer.words}")
            else:
                decided.append(Answer(story.id, "agreed", answer.words, turn))
        else:
            decided.append(Answer(story.id, "declined", "", None))
    return decided, dropped


CONFIRM_BATCH_BYTES = 12_000_000
"""Audio sent in one request. The API takes 20 MB, and base64 adds a third."""


def confirm(
    settings: Settings,
    senior: Senior,
    claims: list[tuple[str, bytes]],
    language: Language | None = None,
) -> list[tuple[bool, str]]:
    """Whether each clip says the words a quote claims, and what was heard in it.

    A second opinion from the recording itself, after the transcript has had its
    say. The clip is the one the family would play, so a quote that passes reads
    the way it sounds. Spelling is not judged, since kana and kanji, or 十八 and
    18, are the same words; a different name, place or number is not. A clip too
    long to send is not confirmed: it is held back rather than waved through."""
    spoken = language or get(senior.language)
    verdicts: list[tuple[bool, str]] = [(False, "")] * len(claims)
    batch: list[int] = []
    size = 0
    for index, (_, audio) in enumerate(claims):
        if len(audio) > CONFIRM_BATCH_BYTES:
            verdicts[index] = (False, "(clip too long to check)")
            continue
        if batch and size + len(audio) > CONFIRM_BATCH_BYTES:
            _hear(settings, senior, spoken, claims, batch, verdicts)
            batch, size = [], 0
        batch.append(index)
        size += len(audio)
    if batch:
        _hear(settings, senior, spoken, claims, batch, verdicts)
    return verdicts


def _hear(
    settings: Settings,
    senior: Senior,
    spoken: Language,
    claims: list[tuple[str, bytes]],
    batch: list[int],
    verdicts: list[tuple[bool, str]],
) -> None:
    parts: list[types.Part] = []
    for number, index in enumerate(batch):
        text, audio = claims[index]
        parts.append(types.Part.from_text(text=f"[{number}] Words to check: 「{text}」"))
        parts.append(types.Part.from_bytes(data=audio, mime_type="audio/wav"))

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=[
            types.Part.from_text(
                text=(
                    f"Each numbered clip below is an elderly person speaking {spoken.label}. "
                    "Before each clip are the words a live transcript says they spoke in "
                    "it. For each clip, write down what they say (heard), then decide "
                    "whether they say the given words somewhere in it (same).\n"
                    "- The clip may hold more than the given words. That is fine.\n"
                    "- The same spoken words written differently are the same: kana or\n"
                    "  kanji, figures or written numbers, punctuation, spacing.\n"
                    "- Different words are not the same: another name, place, number or\n"
                    "  date, a word added or left out, a character from another language.\n"
                    "- If you cannot make the words out, they are not the same.\n\n"
                    f"Known facts about the speaker, for names and places:\n{_who(senior)}"
                )
            ),
            *parts,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Hearing,
            temperature=0.0,
        ),
    )
    result = response.parsed
    if not isinstance(result, Hearing):
        raise RuntimeError(f"Hearing returned nothing usable: {response.text!r}")
    for heard in result.clips:
        if 0 <= heard.clip < len(batch):
            verdicts[batch[heard.clip]] = (heard.same, heard.heard)


def screen(settings: Settings, questions: list[FamilyQuestion], avoid: list[str]) -> set[str]:
    """Ids of family questions that must never be put to the senior.

    Relatives do not know what the senior has refused to talk about, and should
    not find out from this. A question about the war, sent by a grandchild after
    the war was declined, is simply not asked — and to the family it looks no
    different from a question still waiting its turn.
    """
    if not questions or not avoid:
        return set()

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            "An elderly person has asked never to be asked about some topics. Their "
            "family, who do not know this, have sent questions. Decide which "
            "questions would lead into a topic they asked never to raise — directly, "
            "or by the obvious route there.\n\n"
            f"=== Topics never to raise ===\n{', '.join(avoid)}\n\n"
            f"=== Questions from the family ===\n{_listed(questions)}\n\n"
            "Return the numbers of the questions to hold back. When in doubt, hold "
            "it back: an unasked question costs a little, and a question about "
            "something they refused costs their trust."
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Screening,
            temperature=0.0,
        ),
    )
    result = response.parsed
    if not isinstance(result, Screening):
        raise RuntimeError(f"Screening returned nothing usable: {response.text!r}")
    return {questions[i].id for i in result.hold if 0 <= i < len(questions)}


class Translated(BaseModel):
    english: list[str] = Field(description="One translation per passage, in order")


def translate(settings: Settings, texts: list[str], language: Language) -> list[str]:
    """English for what a family page shows in another language, one for each
    text and in its order: names, titles, summaries, the person's own words, and
    the family's questions.

    Shown under the original, never in its place. The quote stays the person's
    own words, with their voice behind it; the translation is there so that
    someone without the language can follow, and says that it is one.
    """
    if not texts:
        return []

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            f"Translate each numbered passage below from {language.label} into plain, "
            "natural English. They come from the page where a family reads an elderly "
            "person's life story: names, story titles, short summaries, the person's own "
            "spoken words, and questions their family sent.\n\n"
            "- Translate faithfully. Add nothing and explain nothing. Spoken words stay "
            "spoken: keep their tone, and do not tidy them into something they did not "
            "say.\n"
            "- Write names of people and places as they sound, in the Latin alphabet, "
            "family name first as in the original: 田中ハル is Tanaka Haru, 長野 is Nagano. "
            "A relation stays a relation, no more precise than it was said: 孫のゆか "
            "is grandchild Yuka.\n"
            "- Where the original leaves out who, as Japanese does, say it with their "
            "name, or 'they', never 'he' or 'she': nothing here says which they are.\n"
            "- One translation per passage, in the same order, without the numbers.\n\n"
            + "\n".join(f"[{i}] {text}" for i, text in enumerate(texts))
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Translated,
            temperature=0.0,
        ),
    )
    result = response.parsed
    if not isinstance(result, Translated) or len(result.english) != len(texts):
        raise RuntimeError(f"Translation returned nothing usable: {response.text!r}")
    return result.english


def plan_next(
    settings: Settings,
    senior: Senior,
    stories: list[Story],
    avoid: list[str],
    language: Language | None = None,
) -> NextPlan:
    spoken = language or get(senior.language)
    told = (
        "\n".join(f"- [{s.life_stage}] {s.title}: {s.summary}" for s in stories)
        or "(nothing has been told yet)"
    )
    thin = [stage for stage in LIFE_STAGES if not any(s.life_stage == stage for s in stories)]

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.text_model,
        contents=(
            "An elderly person's life story is being collected a little at a "
            "time. Decide what to ask about when you next sit with them.\n\n"
            f"=== About this person ===\n{_who(senior)}\n\n"
            f"=== What they have told us so far ===\n{told}\n\n"
            f"=== Periods not yet covered ===\n{', '.join(thin) or 'none'}\n\n"
            f"=== Topics never to raise ===\n{', '.join(avoid) or 'none'}\n\n"
            "=== What to write ===\n"
            f"- Write everything in {spoken.label}, the language they speak.\n"
            "- story_so_far: two or three sentences covering what they have told\n"
            "  us, used to open the next session with 'last time you told me\n"
            "  about...'. Use only what is written above. Do not imagine a scene,\n"
            "  and do not add an impression or an evaluation. Words like 'it was\n"
            "  very moving' or 'surrounded by rich nature' must never appear\n"
            "  unless they said them.\n"
            "- next_questions: three short questions. Prefer the periods not yet\n"
            "  covered, and people who have been named but not yet described.\n"
            "  Never touch a topic listed above as never to raise.\n"
            "  One question asks one thing."
        ),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=NextPlan,
            temperature=0.3,
        ),
    )
    result = response.parsed
    if not isinstance(result, NextPlan):
        raise RuntimeError(f"Planning returned nothing usable: {response.text!r}")
    return result


def context_for(
    senior: Senior,
    plan: Plan,
    family_questions: list[FamilyQuestion] | None = None,
    unasked: list[Story] | None = None,
) -> str:
    """The part of the interviewer's prompt that changes between sessions.

    `family_questions` must already be screened: anything here may be asked.
    `unasked` are earlier stories with no answer yet about whether the family
    may read them, most often because the last conversation ended before its
    close, or before they replied.
    """
    lines = [
        "## お相手について",
        "",
        "次のことは、すでに分かっています。お尋ねする必要はありません。",
        "お名前は、この表記のとおりにお呼びしてください。",
        "",
        _who(senior),
    ]
    if plan.story_so_far:
        lines += ["", "## 前回までに伺ったお話", "", plan.story_so_far]
    if plan.next_questions:
        lines += [
            "",
            "## 今日、伺えるとよいこと",
            "",
            "順番に聞く必要はありません。相手のお話にあわせて、自然に。",
            "",
            *(f"- {q}" for q in plan.next_questions),
        ]
    if family_questions:
        # Asked in the opening line, where it interrupts nothing she is telling —
        # but after the recall of last time, which it must not push out.
        when = (
            "はじめの一言で、前回のお話にひとことふれてから、ひとつめをおたずねください。"
            if plan.story_so_far
            else "はじめの一言で、ひとつめをおたずねください。"
        )
        lines += [
            "",
            "## ご家族から届いたご質問",
            "",
            f"ご家族が知りたがっていらっしゃることです。{when}",
            "どなたからのご質問かを、かならず添えて。答えたくなさそうなら、すぐに引いてください。",
            "",
            *(f"- {q.asked_by}より: {q.text}" for q in family_questions),
        ]
    if unasked:
        lines += [
            "",
            "## ご家族にお伝えしてよいか、まだ伺っていないお話",
            "",
            "前回までに伺ったお話のうち、まだお尋ねしていないものです。",
            "今日のおしまいに、今日のお話とあわせてお尋ねください。",
            "",
            *(f"- {s.title}" for s in unasked),
        ]
    if plan.avoid_topics:
        lines += [
            "",
            "## 触れてはいけない話題",
            "",
            "以前、話したくないとおっしゃった話題です。こちらから持ち出さないでください。",
            "",
            *(f"- {t}" for t in plan.avoid_topics),
        ]
    return "\n".join(lines)

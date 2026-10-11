from kataribe.brain import (
    EarlierAnswer,
    ExtractedQuote,
    ExtractedStory,
    Extraction,
    context_for,
    verify,
    verify_earlier,
)
from kataribe.languages import get
from kataribe.store import Plan, Quote, Senior, Story, Turn

HARU = Senior(
    id="s1",
    name="佐藤茂",
    name_reading="さとうしげる",
    birth_year=1938,
    birthplace="鹿児島",
    family=["妻 ハル"],
)

TURNS = [
    Turn(speaker="ai", text="こんにちは。", started_at=0.0),
    Turn(
        speaker="senior",
        text="昭和十三年に、鹿児島の漁師町で生まれました。父は漁師でした。",
        started_at=3.0,
    ),
]


def story_with(*quotes: str) -> Extraction:
    return Extraction(
        stories=[
            ExtractedStory(
                title="生まれた町",
                summary="鹿児島の漁師町で生まれた。",
                life_stage="子供時代",
                approx_period="昭和十三年",
                people=["父"],
                places=["鹿児島"],
                quotes=[ExtractedQuote(text=q, turn=1) for q in quotes],
            )
        ],
        refused_topics=[],
    )


def test_a_quote_the_person_actually_said_is_kept() -> None:
    stories, dropped = verify(story_with("鹿児島の漁師町で生まれました"), TURNS)

    assert dropped == []
    assert [q.text for q in stories[0].quotes] == ["鹿児島の漁師町で生まれました"]
    assert stories[0].quotes[0].turn == 1


def test_a_quote_they_never_said_is_dropped() -> None:
    # Plausible, fits the story, and never spoken. This is the failure the whole
    # product turns on, so it is dropped rather than stored.
    stories, dropped = verify(story_with("串木野市で生まれました"), TURNS)

    assert dropped == ["串木野市で生まれました"]
    assert stories[0].quotes == []


def test_a_paraphrase_is_dropped_even_though_it_means_the_same() -> None:
    stories, dropped = verify(story_with("漁師町の生まれです"), TURNS)

    assert dropped == ["漁師町の生まれです"]
    assert stories[0].quotes == []


def test_punctuation_differences_do_not_drop_a_real_quote() -> None:
    stories, dropped = verify(story_with("鹿児島の、漁師町で生まれました。"), TURNS)

    assert dropped == []
    assert len(stories[0].quotes) == 1


def test_words_the_interviewer_said_are_not_treated_as_the_persons_own() -> None:
    stories, dropped = verify(story_with("こんにちは"), TURNS)

    assert dropped == ["こんにちは"]


def test_an_unknown_life_stage_falls_back_rather_than_failing() -> None:
    extraction = story_with("父は漁師でした")
    extraction.stories[0].life_stage = "青春時代"

    stories, _ = verify(extraction, TURNS)

    assert stories[0].life_stage == "子供時代"


def test_context_gives_the_name_so_it_is_not_transcribed() -> None:
    # The interviewer heard 佐藤茂 and wrote 佐藤繁. Supplying the name stops it
    # being guessed from audio.
    context = context_for(HARU, Plan(story_so_far="", next_questions=[], avoid_topics=[]))

    assert "佐藤茂" in context
    assert "さとうしげる" in context
    assert "鹿児島" in context


def test_context_carries_last_time_and_what_to_avoid() -> None:
    plan = Plan(
        story_so_far="前回は、織物工場のお話を伺いました。",
        next_questions=["お父様はどんな方でしたか?"],
        avoid_topics=["戦争"],
    )

    context = context_for(HARU, plan)

    assert "織物工場" in context
    assert "お父様はどんな方でしたか?" in context
    assert "戦争" in context


def test_context_stays_quiet_when_there_is_nothing_to_recall() -> None:
    context = context_for(HARU, Plan(story_so_far="", next_questions=[], avoid_topics=[]))

    assert "前回" not in context
    assert "触れてはいけない" not in context


CONSENT_TURNS = [
    Turn(speaker="senior", text="鹿児島の漁師町で生まれました。", started_at=1.0),
    Turn(speaker="ai", text="ご家族にお伝えしてもよろしいですか。", started_at=9.0),
    Turn(speaker="senior", text="ええ、かまいませんよ。", started_at=14.0),
]


def consented(quote: str) -> Extraction:
    return Extraction(
        stories=[
            ExtractedStory(
                title="生まれた町",
                summary="鹿児島の漁師町で生まれた。",
                life_stage="子供時代",
                approx_period="",
                people=[],
                places=["鹿児島"],
                quotes=[],
                consent_quote=quote,
            )
        ],
        refused_topics=[],
    )


def test_a_story_is_private_until_they_say_otherwise() -> None:
    stories, _ = verify(consented(""), CONSENT_TURNS)

    assert stories[0].visibility == "private"
    assert not stories[0].shared


def test_their_own_words_agreeing_make_it_shareable() -> None:
    stories, dropped = verify(consented("ええ、かまいませんよ。"), CONSENT_TURNS)

    assert stories[0].visibility == "family"
    assert stories[0].consent_quote == "ええ、かまいませんよ。"
    assert dropped == []


def test_consent_the_model_reports_but_cannot_evidence_is_refused() -> None:
    # The most dangerous failure here: a summary of agreement rather than the
    # agreement itself. Sharing a life story is not something to infer.
    stories, dropped = verify(consented("はい、どうぞお使いください。"), CONSENT_TURNS)

    assert stories[0].visibility == "private"
    assert stories[0].consent_quote == ""
    assert dropped == ["(consent) はい、どうぞお使いください。"]


def test_words_the_interviewer_said_cannot_grant_consent() -> None:
    stories, _ = verify(consented("ご家族にお伝えしてもよろしいですか。"), CONSENT_TURNS)

    assert stories[0].visibility == "private"


def test_a_quote_carrying_a_character_from_another_language_is_held_back() -> None:
    # Seen in a real run: a Korean particle in the middle of Japanese. The quote
    # is in the transcript, since the transcript is where the glitch came from.
    turns = [Turn(speaker="senior", text="みんなで食卓를囲んでいるときが一番です。", started_at=3)]

    stories, dropped = verify(story_with("みんなで食卓를囲んでいるときが一番です"), turns)

    assert stories[0].quotes == []
    assert dropped == ["(not Japanese: 를) みんなで食卓를囲んでいるときが一番です"]


def test_everyday_japanese_writing_passes_the_script_check() -> None:
    said = "ええと、昭和３０年頃〜18の時、ツヨシ々とNHKを聞いておりました…"
    turns = [Turn(speaker="senior", text=said, started_at=3)]

    stories, dropped = verify(story_with(said), turns)

    assert dropped == []
    assert [q.text for q in stories[0].quotes] == [said]


def test_french_is_checked_against_its_own_alphabet() -> None:
    said = "Je suis né à Quimper, près de l’océan, en 1947 — « là-bas »."
    turns = [Turn(speaker="senior", text=said, started_at=3)]

    stories, dropped = verify(story_with(said), turns, get("fr"))

    assert dropped == []
    assert stories[0].quotes[0].text == said


ASKED_AT_THE_CLOSE = [
    Turn(speaker="senior", text="昭和十三年に、鹿児島の漁師町で生まれました。", started_at=3.0),
    Turn(speaker="senior", text="十八で大阪に出て、工場で働きました。", started_at=9.0),
    Turn(
        speaker="ai",
        text="今日は、生まれた町のお話と、大阪のお話を伺いました。ご家族にお伝えしてよろしいですか。",
        started_at=12.0,
    ),
    Turn(speaker="senior", text="ええ、どちらも見せてやってください。", started_at=16.0),
]


def story_titled(title: str, consent: str, *, asked: bool = True) -> ExtractedStory:
    return ExtractedStory(
        title=title,
        summary=f"{title}のこと。",
        life_stage="子供時代",
        approx_period="",
        people=[],
        places=[],
        quotes=[],
        consent_quote=consent,
        asked_to_share=asked,
    )


def test_one_yes_at_the_close_can_share_several_stories() -> None:
    yes = "ええ、どちらも見せてやってください。"
    extraction = Extraction(
        stories=[story_titled("生まれた町", yes), story_titled("大阪の工場", yes)],
        refused_topics=[],
    )

    stories, dropped = verify(extraction, ASKED_AT_THE_CLOSE)

    assert [s.visibility for s in stories] == ["family", "family"]
    assert dropped == []


def test_a_story_asked_about_and_kept_private_is_not_asked_again() -> None:
    extraction = Extraction(stories=[story_titled("大阪の工場", "")], refused_topics=[])

    [story], _ = verify(extraction, ASKED_AT_THE_CLOSE)

    assert not story.shared
    assert story.asked_to_share


def test_a_story_never_asked_about_waits_for_the_next_close() -> None:
    extraction = Extraction(
        stories=[story_titled("大阪の工場", "", asked=False)], refused_topics=[]
    )

    [story], _ = verify(extraction, ASKED_AT_THE_CLOSE)

    assert not story.shared
    assert not story.asked_to_share


def test_a_yes_that_cannot_be_evidenced_is_asked_about_again() -> None:
    # Misheard, or never said: either way the answer is not known.
    extraction = Extraction(
        stories=[story_titled("大阪の工場", "はい、全部どうぞ。")], refused_topics=[]
    )

    [story], _ = verify(extraction, ASKED_AT_THE_CLOSE)

    assert not story.shared
    assert not story.asked_to_share


def earlier(title: str, *, shared: bool, asked: bool) -> Story:
    return Story(
        id=title,
        senior_id="s1",
        session_id="before",
        title=title,
        summary="",
        life_stage="子供時代",
        approx_period="",
        people=[],
        places=[],
        quotes=[Quote(text="", turn=0)],
        visibility="family" if shared else "private",
        consent_quote="はい。" if shared else "",
        asked_to_share=asked,
    )


TAKE_BACK = [Turn(speaker="senior", text="あの川の話は、家族には見せないでね。", started_at=3.0)]


def test_a_shared_story_can_be_taken_back_without_further_proof() -> None:
    # Words or not, the safe direction is private.
    stories = [earlier("川", shared=True, asked=True)]

    decided, dropped = verify_earlier(
        [EarlierAnswer(story=0, decision="withdrawn", words="そういうことにして")],
        stories,
        TAKE_BACK,
    )

    assert [(d.story_id, d.decision) for d in decided] == [("川", "withdrawn")]
    assert dropped == []


def test_an_earlier_story_is_shared_only_on_her_own_words() -> None:
    stories = [earlier("川", shared=False, asked=False), earlier("工場", shared=False, asked=False)]
    said = [Turn(speaker="senior", text="川のお話なら、どうぞ。", started_at=3.0)]

    decided, dropped = verify_earlier(
        [
            EarlierAnswer(story=0, decision="agreed", words="川のお話なら、どうぞ。"),
            EarlierAnswer(story=1, decision="agreed", words="工場の話もいいですよ"),
        ],
        stories,
        said,
    )

    assert [(d.story_id, d.decision) for d in decided] == [("川", "agreed")]
    assert dropped == ["(consent) 工場の話もいいですよ"]


def test_a_decision_already_made_is_not_reopened_by_extraction() -> None:
    # She kept it private when asked. A later "agreed" the model reports for it
    # was not an answer to anything asked, and is ignored.
    stories = [earlier("川", shared=False, asked=True)]
    said = [Turn(speaker="senior", text="どうぞ。", started_at=3.0)]

    decided, _ = verify_earlier(
        [EarlierAnswer(story=0, decision="agreed", words="どうぞ。")], stories, said
    )

    assert decided == []


def test_context_lists_the_stories_still_to_be_asked_about() -> None:
    context = context_for(
        HARU,
        Plan(story_so_far="", next_questions=[], avoid_topics=[]),
        unasked=[earlier("千曲川で泳いだ夏", shared=False, asked=False)],
    )

    assert "まだ伺っていないお話" in context
    assert "- 千曲川で泳いだ夏" in context

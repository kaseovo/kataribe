import { useEffect, useRef, useState, type FormEvent } from 'react';

import './App.css';
import './Landing.css';
import { lifeStage } from './lifeStages';

/** The start page, for strangers on the public URL: judges, mostly.
 *
 *  It goes in the order a judge needs: what it is, how it works, a real story
 *  from the demo's family page, and then their own turn. Chosen on 2026-10-14
 *  from three prototypes, over two side-by-side doors and a guided tour.
 *
 *  Each visitor gets a persona of their own and talks as themselves. Memory is
 *  per person, so a shared persona would greet the second visitor with the
 *  first one's childhood. Theirs is remembered in this browser, so coming back
 *  continues it, and a second conversation recalls the first. */

interface Start {
  languages: { code: string; endonym: string }[];
  showcase: string | null;
  video: string;
  repo: string;
  open: boolean;
}

/** The demo's family page, as much of it as the start page shows. */
interface Told {
  name: string;
  story: {
    title: string;
    summary: string;
    life_stage: string;
    /** In their words, with the English once it is made, and their voice
     *  where recorded. */
    quotes: { text: string; english?: string; audio: string | null }[];
  };
  question: { asked_by: string; text: string } | null;
}

interface Remembered {
  id: string;
  name: string;
}

/** Filled in already, so a visitor can press Start without thinking and still
 *  hear the family loop: the first conversation opens with it. A childhood
 *  place suits anyone at any age, rarely touches anything painful, and gets a
 *  story going in one turn. */
const QUESTIONS: Record<string, { asked_by: string; question: string }> = {
  en: {
    asked_by: 'Your family',
    question: 'Which place from your childhood do you still think about?',
  },
  ja: {
    asked_by: 'ご家族',
    question: '子どもの頃の場所で、今も思い出すところはどこですか？',
  },
};

const KEY = 'kataribe.visitor';

function remembered(): Remembered | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Remembered) : null;
  } catch {
    return null;
  }
}

function remember(visitor: Remembered | null) {
  try {
    if (visitor) localStorage.setItem(KEY, JSON.stringify(visitor));
    else localStorage.removeItem(KEY);
  } catch {
    // A private window: they start afresh next time, which is all it costs.
  }
}

/** What a conversation needs from the browser, checked before anyone presses
 *  Start, so an unsupported browser is told so up front rather than failing
 *  once the microphone should have opened. */
function canConverse(): boolean {
  return (
    typeof AudioWorkletNode !== 'undefined' &&
    typeof WebSocket !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia
  );
}

/** One story from the demo's family page, in English, for a judge: the one a
 *  family question was answered in, since it shows the loop, or else the first.
 *  Null until it has loaded, or when no showcase is set. */
function useTold(showcase: string | null): Told | null {
  const [told, setTold] = useState<Told | null>(null);
  useEffect(() => {
    if (!showcase) return;
    const page = fetch(`/api/family/${showcase}`).then((r) => r.json());
    const english = fetch(`/api/family/${showcase}/translations`)
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({}));
    Promise.all([page, english])
      .then(([view, en]: [FamilyPage, Record<string, string>]) => {
        const say = (text: string) => en[text] ?? text;
        const stories = view.chapters.flatMap((chapter) => chapter.stories);
        const question = view.questions.find((q) => q.answered_in.length > 0);
        const story = stories.find((s) => question?.answered_in.includes(s.id)) ?? stories[0];
        if (!story) return;
        setTold({
          name: say(view.senior.name),
          story: {
            title: say(story.title),
            summary: say(story.summary),
            life_stage: story.life_stage,
            // No fallback here: a quote with no English yet shows its words
            // once, rather than again in English quotation marks.
            quotes: story.quotes.map((q) => ({ ...q, english: en[q.text] })),
          },
          question: question ? { asked_by: say(question.asked_by), text: say(question.text) } : null,
        });
      })
      .catch(() => undefined);
  }, [showcase]);
  return told;
}

interface FamilyPage {
  senior: { name: string };
  chapters: {
    stories: {
      id: string;
      title: string;
      summary: string;
      life_stage: string;
      quotes: { text: string; audio: string | null }[];
    }[];
  }[];
  questions: { asked_by: string; text: string; answered_in: string[] }[];
}

/** The story, with its first quote, and every other one a press away: the
 *  summary is a retelling, so a judge can check each thing in it against what
 *  was actually said, and hear it where there is a recording. */
function Story({ told }: { told: Told }) {
  const [all, setAll] = useState(false);
  const player = useRef<HTMLAudioElement | null>(null);
  const { story, question } = told;
  const quotes = all ? story.quotes : story.quotes.slice(0, 1);
  const play = (audio: string) => {
    const element = player.current;
    if (!element) return;
    if (!element.src.endsWith(audio)) element.src = audio;
    element.currentTime = 0;
    void element.play();
  };
  return (
    <article className="story">
      <audio ref={player} preload="none" />
      {question && (
        <p className="asked">
          {question.asked_by} asked: {question.text}
        </p>
      )}
      <p className="stage">{lifeStage(story.life_stage)}</p>
      <h3>{story.title}</h3>
      <p>{story.summary}</p>
      {quotes.map((quote) => (
        <blockquote key={quote.text}>
          {quote.audio && (
            <button className="listen" onClick={() => play(quote.audio!)} aria-label="Listen">
              ▶
            </button>
          )}
          <span>
            <span lang="ja">「{quote.text}」</span>
            {quote.english && <span className="english">“{quote.english}”</span>}
          </span>
        </blockquote>
      ))}
      {story.quotes.length > 1 && (
        <button type="button" className="quiet more" onClick={() => setAll(!all)}>
          {all
            ? 'Show only the first quote'
            : `Show all ${story.quotes.length} quotes, in their own words`}
        </button>
      )}
    </article>
  );
}

export default function Landing() {
  const [start, setStart] = useState<Start | null>(null);
  const [visitor, setVisitor] = useState<Remembered | null>(remembered);
  const [draft, setDraft] = useState({ name: '', language: 'en', ...QUESTIONS.en });
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const supported = canConverse();
  const told = useTold(start?.showcase ?? null);

  useEffect(() => {
    fetch('/api/try')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setStart)
      .catch(() => setProblem('The page could not load just now. Please reload it in a moment.'));
  }, []);

  /** The question follows the language, unless they have written their own. */
  const pickLanguage = (language: string) => {
    const before = QUESTIONS[draft.language];
    const after = QUESTIONS[language] ?? QUESTIONS.en;
    setDraft({
      ...draft,
      language,
      asked_by: draft.asked_by === before?.asked_by ? after.asked_by : draft.asked_by,
      question: draft.question === before?.question ? after.question : draft.question,
    });
  };

  const begin = async (event: FormEvent) => {
    event.preventDefault();
    setSending(true);
    setProblem(null);
    try {
      const response = await fetch('/api/try', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      });
      if (response.status === 429) {
        setStart((s) => s && { ...s, open: false });
        return;
      }
      if (!response.ok) throw new Error(String(response.status));
      const { id } = (await response.json()) as { id: string };
      remember({ id, name: draft.name.trim() });
      window.location.assign(`/talk/${id}`);
    } catch {
      setProblem('It could not start just now. Please try again in a moment.');
    } finally {
      setSending(false);
    }
  };

  const forget = () => {
    remember(null);
    setVisitor(null);
  };

  const open = start?.open ?? true;
  const languages = start?.languages ?? [{ code: 'en', endonym: 'English' }];
  const ready = !!start && open && supported;

  return (
    <div className="landing">
      <header className="hero">
        <p className="brand">
          Kataribe <span lang="ja">語り部</span>
        </p>
        <h1>Every grandparent has stories nobody has asked about yet.</h1>
        <p className="lede">
          Kataribe talks with an elderly person for a few minutes a day, in Japanese, and turns
          what they remember into a life story their family can read, and hear in their own voice.
          A <em>kataribe</em> is a traditional keeper of oral history: the one who remembers the
          stories and passes them on.
        </p>
        <p className="actions">
          {told && (
            <a className="start" href="#example">
              See a life story
            </a>
          )}
          <a className={told ? 'secondary' : 'start'} href="#try">
            Try it on your own life
          </a>
        </p>
      </header>

      <section className="loop" aria-label="How it works">
        <ol>
          <li>
            <strong>They talk</strong>
            The interviewer speaks first, asks one thing at a time, and waits through a pause.
          </li>
          <li>
            <strong>It writes their story</strong>
            Every quote word for word, with their voice behind it.
          </li>
          <li>
            <strong>The family reads</strong>
            Only what they agreed, aloud, to share.
          </li>
          <li>
            <strong>The family asks back</strong>
            A relative’s question opens the next conversation.
          </li>
        </ol>
      </section>

      {/* Before the form, so a judge sees what it makes before talking to it. */}
      {told && start?.showcase && (
        <section id="example" className="example">
          <h2>From {told.name}’s family page</h2>
          <p className="note">A life story from our demo, told in Japanese, shown in English.</p>
          <Story told={told} />
          <p className="actions">
            <a className="secondary" href={`/family/${start.showcase}`}>
              Read the whole family page
            </a>
            {start.video && (
              <a className="secondary" href={start.video}>
                Watch the demo video
              </a>
            )}
          </p>
        </section>
      )}
      {!told && start?.video && (
        <p className="actions">
          <a className="secondary" href={start.video}>
            Watch the demo video
          </a>
        </p>
      )}

      <section id="try" className="try">
        <h2>Your turn</h2>
        <p>
          Talk about your own life for two minutes or so. At two minutes it asks whether you want
          to go on. When you are done, it asks whether your family may read today’s story: answer
          aloud, or press <strong>Share with my family</strong> or <strong>Keep it private</strong>.
          Your story then appears on a family page of your own.
        </p>

        {!supported && (
          <p className="notice" role="alert">
            This browser cannot hold a conversation here. Please open this page in Chrome or Edge on
            a computer.
          </p>
        )}
        {start && !open && (
          <p className="notice" role="status">
            Today’s conversations are used up. They start again at midnight, Japan time. Meanwhile,
            the life story above shows it at work.
          </p>
        )}

        {visitor ? (
          <div className="returning">
            <p>Welcome back, {visitor.name}. Your conversations continue where you left off.</p>
            <div className="actions">
              {ready && (
                <a className="start" href={`/talk/${visitor.id}`}>
                  Talk again
                </a>
              )}
              <a className="secondary" href={`/family/${visitor.id}`}>
                Your family page
              </a>
              <button type="button" className="quiet" onClick={forget}>
                Start afresh as someone else
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={begin}>
            <label>
              Your name
              <input
                required
                maxLength={40}
                autoComplete="given-name"
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </label>

            {languages.length > 1 && (
              <fieldset className="languages">
                <legend>Language</legend>
                {languages.map((language) => (
                  <label key={language.code}>
                    <input
                      type="radio"
                      name="language"
                      value={language.code}
                      checked={draft.language === language.code}
                      onChange={() => pickLanguage(language.code)}
                    />
                    {language.endonym}
                  </label>
                ))}
              </fieldset>
            )}

            {/* Filled in already, so it is there without being one more thing
                to read before pressing Start. */}
            <details className="family-question">
              <summary>A question to open with, from someone who would love to hear your stories</summary>
              <label>
                Who is asking
                <input
                  maxLength={40}
                  value={draft.asked_by}
                  onChange={(e) => setDraft({ ...draft, asked_by: e.target.value })}
                />
              </label>
              <label>
                Their question
                <textarea
                  maxLength={300}
                  rows={2}
                  value={draft.question}
                  onChange={(e) => setDraft({ ...draft, question: e.target.value })}
                />
              </label>
            </details>

            <button
              type="submit"
              className="start"
              disabled={!ready || sending || !draft.name.trim()}
            >
              {sending ? 'Starting…' : 'Start talking'}
            </button>
          </form>
        )}

        {problem && (
          <p className="notice" role="alert">
            {problem}
          </p>
        )}
      </section>

      <p className="privacy">
        Your conversation is recorded and processed by Google’s Gemini. Your family page is
        reachable only by its link, kept in this browser, and shows only what you agree to share,
        though the Kataribe team can see full conversations to fix problems. Everything recorded
        from this page is deleted once judging ends.
      </p>

      <footer>{start?.repo && <a href={start.repo}>Source code</a>}</footer>
    </div>
  );
}

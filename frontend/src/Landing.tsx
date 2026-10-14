import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { createPortal } from 'react-dom';

import './App.css';
import Family from './Family';
import './Landing.css';
import { lifeStage } from './lifeStages';

/** The start page, for strangers on the public URL: judges, mostly.
 *
 *  It goes in the order a judge needs: what it is, the video, how it works,
 *  the demo's family page, and then their own turn. Chosen on 2026-10-14 from
 *  three prototypes, over two side-by-side doors and a guided tour. The family
 *  page opens whole over the start page, from its cover: chosen the same day
 *  over one story to browse, one question to follow step by step, the page in
 *  a phone or a browser window, and the page laid out within the start page.
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

/** The cover of the demo's family page, in English: its name, its chapters,
 *  and how many questions the family has sent. */
interface Cover {
  name: string;
  original: string;
  born: string;
  pronouns: string;
  chapters: { stage: string; titles: string[] }[];
  questions: number;
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

/** The demo's family page, as much of it as its cover shows. Null until it has
 *  loaded, or when no showcase is set. */
function useCover(showcase: string | null): Cover | null {
  const [cover, setCover] = useState<Cover | null>(null);
  useEffect(() => {
    if (!showcase) return;
    const page = fetch(`/api/family/${showcase}`).then((r) => r.json());
    const english = fetch(`/api/family/${showcase}/translations`)
      .then((r) => (r.ok ? r.json() : {}))
      .catch(() => ({}));
    Promise.all([page, english])
      .then(([view, en]: [FamilyPage, Record<string, string>]) => {
        if (view.chapters.length === 0) return;
        const say = (text: string) => en[text] ?? text;
        const { birth_year, birthplace } = view.senior;
        setCover({
          name: say(view.senior.name),
          original: view.senior.name,
          born: [birth_year && `Born in ${birth_year}`, birthplace && say(birthplace)]
            .filter(Boolean)
            .join(', '),
          pronouns: view.senior.pronouns ?? '',
          chapters: view.chapters.map((chapter) => ({
            stage: lifeStage(chapter.life_stage),
            titles: chapter.stories.map((story) => say(story.title)),
          })),
          questions: view.questions.length,
        });
      })
      .catch(() => undefined);
  }, [showcase]);
  return cover;
}

interface FamilyPage {
  senior: { name: string; birth_year: number | null; birthplace: string; pronouns?: string };
  chapters: { life_stage: string; stories: { title: string }[] }[];
  questions: unknown[];
}

/** The demo's family page: its cover here, and the whole page a press away,
 *  over the start page, as a relative sees it. Closing it, or the browser's
 *  Back, returns to the same place, and Try it lands on Your turn. */
function Example({ cover, showcase }: { cover: Cover; showcase: string }) {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement | null>(null);
  const sheet = useRef<HTMLDivElement | null>(null);
  /** Where to go once it has closed, when not back to its cover. */
  const then = useRef<(() => void) | null>(null);
  const their = { she: 'her', he: 'his', they: 'their' }[cover.pronouns] ?? `${cover.name}’s`;

  // An entry of its own in the history, so that Back closes it rather than
  // leaving the start page.
  useEffect(() => {
    const onPop = () => {
      const shown = window.history.state?.family === true;
      setOpen(shown);
      if (shown) return;
      const after = then.current;
      then.current = null;
      requestAnimationFrame(() => (after ? after() : opener.current?.focus()));
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const show = () => {
    window.history.pushState({ family: true }, '');
    setOpen(true);
  };
  const hide = (after?: () => void) => {
    then.current = after ?? null;
    window.history.back();
  };
  const toTry = () => document.getElementById('try')?.scrollIntoView();

  useEffect(() => {
    if (!open) return;
    const before = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    // On the page itself, which arrives a moment later: its way back is then
    // the first thing Tab reaches.
    sheet.current?.focus();
    // Escape closes the page, unless it is closing the page's own panel.
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !document.querySelector('.drawer')) hide();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = before;
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  /** The page's own ways back close it, rather than loading the start page
   *  again: back to where the reader was, or on to Your turn. A link within the
   *  page moves within it, without a history entry that Back would have to
   *  undo before closing it. Caught on the way down, since the page's
   *  questions panel keeps its clicks to itself. */
  const follow = (event: MouseEvent) => {
    const href = (event.target as HTMLElement).closest('a')?.getAttribute('href');
    if (href === '/') {
      event.preventDefault();
      hide();
    } else if (href === '/#try') {
      event.preventDefault();
      hide(toTry);
    } else if (href?.startsWith('#')) {
      event.preventDefault();
      document.getElementById(href.slice(1))?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section id="example" className="example">
      <div className="example-text">
        <h2>See a life story</h2>
        <p className="note">
          From our demo, the page {their} family reads. Told in Japanese, shown in English.
        </p>
        <ul className="look">
          <li>
            Each story retold from what was said, every quote a press away, in Japanese with the
            English beneath
          </li>
          <li>The questions the family sent, and the story each one led to</li>
          <li>The whole page in Japanese, as {their} family reads it</li>
        </ul>
      </div>
      <button ref={opener} className="cover-card" onClick={show} aria-haspopup="dialog">
        <span className="kicker">A life story</span>
        <span className="title">{cover.name}</span>
        {cover.original !== cover.name && (
          <span className="original" lang="ja">
            {cover.original}
          </span>
        )}
        {cover.born && <span className="born">{cover.born}</span>}
        <span className="toc">
          {cover.chapters.map((chapter, i) => (
            <span key={chapter.stage} className="toc-row">
              <span className="toc-stage">
                {i + 1} · {chapter.stage}
              </span>
              <span className="toc-titles">
                {chapter.titles.map((title) => (
                  <span key={title}>{title}</span>
                ))}
              </span>
            </span>
          ))}
        </span>
        {cover.questions > 0 && (
          <span className="toc-questions">
            {cover.questions} question{cover.questions === 1 ? '' : 's'} from the family
          </span>
        )}
        <span className="open">Open the family page</span>
      </button>

      {open &&
        createPortal(
          <div
            ref={sheet}
            className="sheet"
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label={`${cover.name}’s family page`}
            onClickCapture={follow}
          >
            <Family seniorId={showcase} />
          </div>,
          document.body,
        )}
    </section>
  );
}

/** The demo video, on the page itself: YouTube or Vimeo embedded with their
 *  captions, a video file in the browser's own player, anything else as a
 *  link. Until there is one, development shows where it will go. */
function Video({ url }: { url: string }) {
  const youtube = url.match(
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([\w-]{11})/,
  );
  const vimeo = url.match(/vimeo\.com\/(?:video\/)?(\d+)/);
  if (youtube) {
    return (
      <iframe
        className="video"
        src={`https://www.youtube-nocookie.com/embed/${youtube[1]}?cc_load_policy=1`}
        title="Kataribe, the demo video"
        allow="fullscreen; picture-in-picture"
        allowFullScreen
      />
    );
  }
  if (vimeo) {
    return (
      <iframe
        className="video"
        src={`https://player.vimeo.com/video/${vimeo[1]}`}
        title="Kataribe, the demo video"
        allow="fullscreen; picture-in-picture"
        allowFullScreen
      />
    );
  }
  if (/\.(mp4|webm|mov)(\?|$)/i.test(url)) {
    return <video className="video" src={url} controls preload="metadata" />;
  }
  if (url) {
    return (
      <a className="video placeholder" href={url}>
        <span aria-hidden>▶</span>
        Watch the demo video
      </a>
    );
  }
  return (
    <div className="video placeholder">
      <span aria-hidden>▶</span>
      The demo video plays here once it is recorded.
    </div>
  );
}

export default function Landing() {
  const [start, setStart] = useState<Start | null>(null);
  const [visitor, setVisitor] = useState<Remembered | null>(remembered);
  const [draft, setDraft] = useState({
    name: '',
    language: 'en',
    ...QUESTIONS.en,
  });
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const supported = canConverse();
  const cover = useCover(start?.showcase ?? null);
  /** How many stories a returning visitor has on their family page. */
  const [shared, setShared] = useState<number | null>(null);
  useEffect(() => {
    if (!visitor) return;
    fetch(`/api/family/${visitor.id}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((page: { chapters: { stories: unknown[] }[] } | null) => {
        if (page) setShared(page.chapters.reduce((n, c) => n + c.stories.length, 0));
      })
      .catch(() => undefined);
  }, [visitor]);

  useEffect(() => {
    fetch('/api/try')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setStart)
      .catch(() => setProblem('The page could not load just now. Please reload it in a moment.'));
  }, []);

  // Arriving at #try from the example family page: the sections above it
  // appear as they load, so go there again each time they do.
  useEffect(() => {
    if (start && window.location.hash) {
      document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
    }
  }, [start, cover]);

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
  const watchable = !!start?.video || import.meta.env.DEV;

  return (
    <div className="landing">
      <header className="hero">
        <div className="hero-text">
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
            {watchable && (
              <a className="start" href="#watch">
                Watch it
              </a>
            )}
            {cover && (
              <a className={watchable ? 'secondary' : 'start'} href="#example">
                See a life story
              </a>
            )}
            <a className={watchable || cover ? 'secondary' : 'start'} href="#try">
              Try it on your own life
            </a>
          </p>
        </div>

        {/* The quickest way in: a whole conversation, then what it became. */}
        {watchable && (
          <figure id="watch" className="watch">
            <Video url={start?.video ?? ''} />
            <figcaption>
              A real conversation in Japanese, with English subtitles: the interviewer, the story it
              became, and the page the family reads.
            </figcaption>
          </figure>
        )}
      </header>

      <section className="loop" aria-label="How it works">
        <h2>How it works</h2>
        <ol>
          <li>
            <strong>They talk</strong>
            In Japanese, a few minutes a day. The interviewer speaks first, asks one thing at a
            time, and waits through a pause for thought.
          </li>
          <li>
            <strong>It writes their story</strong>A retelling to read, and every quote word for
            word, checked against the transcript and the recording, with their voice behind it.
          </li>
          <li>
            <strong>The family reads</strong>
            Only what they agreed to share, in their own words. A private story is not even counted.
          </li>
          <li>
            <strong>The family asks back</strong>A relative’s question opens the next conversation,
            saying who asked. The answer appears under it.
          </li>
        </ol>
      </section>

      {/* Before the form, so a judge sees what it makes before talking to it. */}
      {cover && start?.showcase && <Example cover={cover} showcase={start.showcase} />}

      <section id="try" className="try">
        <div className="try-text">
          <h2>Your turn</h2>
          <p>
            Talk about your own life for two minutes or so. At two minutes it asks whether you want
            to go on. When you are done, it asks whether your family may read today’s story: answer
            aloud, or press <strong>Share with my family</strong> or{' '}
            <strong>Keep it private</strong>. Your story then appears on a family page of your own.
          </p>
          <p className="note">
            You try it as the elder would, about your own life, in English. The product itself is
            Japanese, for seniors at home, with nothing to install or learn.
          </p>
        </div>

        <div className="try-form">
          {!supported && (
            <p className="notice" role="alert">
              This browser cannot hold a conversation here. Please open this page in Chrome or Edge
              on a computer.
            </p>
          )}
          {start && !open && (
            <p className="notice" role="status">
              Today’s conversations are used up. They start again at midnight, Japan time.
              Meanwhile, the life story above shows it at work.
            </p>
          )}

          {visitor ? (
            <div className="returning">
              <div className="who">
                <span className="initial" aria-hidden>
                  {visitor.name.trim().charAt(0).toUpperCase()}
                </span>
                <div>
                  <p className="kicker">Welcome back</p>
                  <p className="name">{visitor.name}</p>
                </div>
              </div>
              <p className="where">
                Your conversations continue where you left off: it remembers what you told it.{' '}
                {shared === null
                  ? ''
                  : shared === 0
                    ? 'Nothing is on your family page yet.'
                    : shared === 1
                      ? 'One story is on your family page.'
                      : `${shared} stories are on your family page.`}
              </p>
              <div className="returning-actions">
                {ready && (
                  <a className="start" href={`/talk/${visitor.id}`}>
                    Talk again
                  </a>
                )}
                <a className="secondary" href={`/family/${visitor.id}`}>
                  Your family page <span aria-hidden>→</span>
                </a>
              </div>
              <p className="someone-else">
                Not {visitor.name}?{' '}
                <button type="button" onClick={forget}>
                  Start afresh as someone else
                </button>
              </p>
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
                <summary>
                  A question to open with, from someone who would love to hear your stories
                </summary>
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
        </div>
      </section>

      {/* For a technical judge: the path from a voice to a family page, and
          what does each step. */}
      <section className="hood">
        <h2>Under the hood</h2>
        <p className="note">From a voice to a family page, in five steps.</p>
        <ol>
          <li>
            <strong>Talk</strong>
            <span>
              The browser speaks with Gemini Live directly, on a short-lived token. Its pause is set
              for someone searching their memory: five seconds in Japanese.
            </span>
          </li>
          <li>
            <strong>Write</strong>
            <span>
              Once it ends, the transcript becomes stories: a retelling, the time of life it belongs
              to, and the quotes it rests on.
            </span>
          </li>
          <li>
            <strong>Check</strong>
            <span>
              Every quote must be found word for word in the transcript, then heard in its clip of
              the recording. One that fails either is dropped. Agreement to share is checked the
              same way.
            </span>
          </li>
          <li>
            <strong>Share</strong>
            <span>
              Only what was agreed reaches the family page, in Japanese or in English, each quote
              with its own clip. Nothing else of the recording is ever linked.
            </span>
          </li>
          <li>
            <strong>Plan</strong>
            <span>
              It finds the times of life not yet told and plans the next questions, alongside the
              family's own, and never raises what was refused.
            </span>
          </li>
        </ol>
        {start?.repo && (
          <p className="stack">
            <a href={start.repo}>
              Read the code <span aria-hidden>→</span>
            </a>
          </p>
        )}
      </section>

      <footer className="privacy">
        <p>
          Your conversation is recorded and processed by Google’s Gemini. Your family page is
          reachable only by its link, kept in this browser, and shows only what you agree to share,
          though the Kataribe team can see full conversations to fix problems. Everything recorded
          from this page is deleted once judging ends.
        </p>
      </footer>
    </div>
  );
}

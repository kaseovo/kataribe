import { useEffect, useRef, useState, type FormEvent } from 'react';

import './App.css';
import './Family.css';
import { lifeStage } from './lifeStages';

interface Quote {
  text: string;
  turn: number;
  /** Their voice saying this, cut from the session on the server. The page
   *  never learns where the whole recording is: it also holds whatever they
   *  chose not to share. Null when the session was not recorded. */
  audio: string | null;
  /** All they said in the answer it comes from: what the clip plays. */
  said: string;
}

/** Their whole answer, with the words quoted from it marked. */
function Answer({ said, quoted }: { said: string; quoted: string }) {
  const at = said.indexOf(quoted);
  if (at < 0) return <>{said}</>;
  return (
    <>
      {said.slice(0, at)}
      <mark>{quoted}</mark>
      {said.slice(at + quoted.length)}
    </>
  );
}

interface Story {
  id: string;
  title: string;
  summary: string;
  life_stage: string;
  approx_period: string;
  people: string[];
  places: string[];
  quotes: Quote[];
}

interface Chapter {
  life_stage: string;
  stories: Story[];
}

/** Held questions — ones that touch something she refused — arrive here as
 *  `waiting`. Telling the family otherwise would tell them what she refused. */
interface Question {
  id: string;
  asked_by: string;
  text: string;
  status: 'waiting' | 'asked';
  answered_in: string[];
}

interface View {
  senior: {
    name: string;
    birth_year: number | null;
    birthplace: string;
    language: string;
    family: string[];
  };
  chapters: Chapter[];
  questions: Question[];
  /** A conversation is still being written up, so more may be on its way. */
  writing: boolean;
  /** The page the start page shows every visitor: read-only. */
  showcase: boolean;
  /** A visitor's own persona, made from the start page. */
  visitor: boolean;
}

const SPOKEN: Record<string, string> = { ja: 'Japanese', fr: 'French' };
const ENDONYM: Record<string, string> = { ja: '日本語', fr: 'Français' };

/** How often the page looks again while a conversation is being written up. */
const REFRESH_MS = 4000;

/** What the family sees. Only stories the person agreed to share reach this
 *  page, and the filtering happens in the query rather than here — there is no
 *  path through which a private story arrives and is merely not rendered. */
const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;

/** Their voice saying it: the clip of the answer the quote comes from. Where
 *  there is no recording, as on a page made up for a demo, it is shown greyed,
 *  so the place the voice belongs is still there. */
function Player({ audio }: { audio: string | null }) {
  const sound = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [done, setDone] = useState(0);
  const [length, setLength] = useState<number | null>(null);
  if (!audio) {
    return (
      <div className="player none">
        <button className="listen" disabled aria-label="No recording">
          ▶
        </button>
        <span className="bar" />
        <span className="time">No recording</span>
      </div>
    );
  }
  const toggle = () => {
    const clip = sound.current;
    if (!clip) return;
    if (clip.paused) void clip.play();
    else clip.pause();
  };
  return (
    <div className="player">
      <audio
        ref={sound}
        src={audio}
        preload="none"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setDone(0)}
        onLoadedMetadata={(e) => setLength(e.currentTarget.duration)}
        onTimeUpdate={(e) => {
          const clip = e.currentTarget;
          if (clip.duration) setDone(clip.currentTime / clip.duration);
        }}
      />
      <button className="listen" onClick={toggle} aria-label={playing ? 'Pause' : 'Listen'}>
        {playing ? '❚❚' : '▶'}
      </button>
      <span className="bar">
        <span style={{ width: `${done * 100}%` }} />
      </span>
      <span className="time">{length ? clock(length) : ''}</span>
    </div>
  );
}

/** The story is read as text. Its quotes, the words it was retold from, with
 *  their voice, are one press away, for whoever wants to check it against what
 *  was said or hear them say it. */
function Quotes({
  story,
  name,
  language,
  english,
}: {
  story: Story;
  name: string;
  language: string;
  english: (text: string) => string | undefined;
}) {
  const [open, setOpen] = useState(false);
  const count = story.quotes.length;
  if (count === 0) return null;
  return (
    <div className="quotes">
      <button className="toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open
          ? 'Hide the quotes'
          : `${count === 1 ? 'The quote' : `All ${count} quotes`} in ${name}’s own words, with their voice`}
      </button>
      {open &&
        story.quotes.map((quote, i) => (
          <blockquote key={i}>
            <span lang={language}>「{quote.text}」</span>
            {english(quote.text) && <span className="translation">“{english(quote.text)}”</span>}
            <Player audio={quote.audio} />
            {quote.said && quote.said !== quote.text && (
              <details className="said">
                <summary>All they said</summary>
                <span lang={language}>
                  <Answer said={quote.said} quoted={quote.text} />
                </span>
                {english(quote.said) && <span className="translation">{english(quote.said)}</span>}
              </details>
            )}
          </blockquote>
        ))}
    </div>
  );
}

/** Relations by group, so finding yours is two presses among few, and Other
 *  for whatever is not here. The interviewer says it aloud: "Your
 *  daughter-in-law Aiko would love to know…". */
const RELATIONS: Record<string, string[]> = {
  Grandchildren: ['granddaughter', 'grandson', 'great-granddaughter', 'great-grandson'],
  Children: ['daughter', 'son'],
  Partner: ['wife', 'husband', 'partner'],
  'Brothers & sisters': ['sister', 'brother'],
  'In-laws': ['daughter-in-law', 'son-in-law', 'sister-in-law', 'brother-in-law'],
  'Wider family': ['niece', 'nephew', 'cousin'],
  'Friends & others': ['friend', 'neighbour', 'carer', 'former colleague'],
};

/** Who is asking, as the interviewer will say it: a relation, then a name. */
function Who({ name, onChange }: { name: string; onChange: (askedBy: string) => void }) {
  const [group, setGroup] = useState<string | null>(null);
  const [relation, setRelation] = useState('');
  const [other, setOther] = useState(false);
  const [person, setPerson] = useState('');
  const update = (r: string, n: string) => {
    setRelation(r);
    setPerson(n);
    onChange([r.trim(), n.trim()].filter(Boolean).join(' '));
  };
  return (
    <>
      <div className="relations" role="group" aria-label={`Who you are to ${name}`}>
        {Object.keys(RELATIONS).map((g) => (
          <button
            key={g}
            type="button"
            aria-pressed={group === g}
            onClick={() => {
              setGroup(g);
              setOther(false);
              update('', person);
            }}
          >
            {g}
          </button>
        ))}
      </div>
      {group && (
        <div className="relations sub" role="group" aria-label={group}>
          {RELATIONS[group].map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={!other && relation === r}
              onClick={() => {
                setOther(false);
                update(r, person);
              }}
            >
              {r}
            </button>
          ))}
          <button
            type="button"
            aria-pressed={other}
            onClick={() => {
              setOther(true);
              update('', person);
            }}
          >
            Other…
          </button>
        </div>
      )}
      {other && (
        <input
          aria-label="Your relation"
          placeholder="e.g. goddaughter"
          maxLength={30}
          value={relation}
          onChange={(e) => update(e.target.value, person)}
        />
      )}
      {group && (
        <input
          aria-label="Your name"
          placeholder="Your first name"
          maxLength={25}
          value={person}
          onChange={(e) => update(relation, e.target.value)}
        />
      )}
    </>
  );
}

export default function Family({ seniorId }: { seniorId: string }) {
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({ asked_by: '', text: '' });
  const [sending, setSending] = useState(false);
  const [unsent, setUnsent] = useState<string | null>(null);
  /** English for the page's text, by the text, when they speak another
   *  language. Shown under the original, never in its place. */
  const [translations, setTranslations] = useState<Record<string, string>>({});
  /** The reader's own choice of language, once they have made one. */
  const [picked, setReading] = useState<'en' | 'original' | null>(null);

  useEffect(() => {
    fetch(`/api/family/${seniorId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setView)
      .catch(() => setError('We could not find that story.'));
  }, [seniorId]);

  // Until the writing-up is done, so a story arrives without anyone reloading.
  const writing = view?.writing ?? false;
  useEffect(() => {
    if (!writing) return;
    const timer = setInterval(() => {
      fetch(`/api/family/${seniorId}`)
        .then((r) => (r.ok ? (r.json() as Promise<View>) : null))
        .then((seen) => seen && setView(seen))
        .catch(() => undefined);
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [writing, seniorId]);

  // Read after the page, so it never waits on a translation: the first time a
  // text is shown takes seconds, after that it is kept. Again whenever a story
  // or a question arrives.
  const foreign = Boolean(view && view.senior.language !== 'en');
  const shownKey = view
    ? `${view.chapters.flatMap((c) => c.stories.map((s) => s.id)).join()}|${view.questions.length}`
    : '';
  useEffect(() => {
    if (!foreign) return;
    fetch(`/api/family/${seniorId}/translations`)
      .then((r) => (r.ok ? (r.json() as Promise<Record<string, string>>) : null))
      .then((english) => english && setTranslations(english))
      .catch(() => undefined);
  }, [foreign, shownKey, seniorId]);

  const ask = async (event: FormEvent) => {
    event.preventDefault();
    setSending(true);
    setUnsent(null);
    try {
      const response = await fetch(`/api/family/${seniorId}/questions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      });
      if (!response.ok) throw new Error(String(response.status));
      const question: Question = await response.json();
      setView((v) => v && { ...v, questions: [...v.questions, question] });
      // Whoever is asking is likely to ask again, so their name stays.
      setDraft({ ...draft, text: '' });
    } catch {
      setUnsent('Your question could not be sent just now. Please try again in a moment.');
    } finally {
      setSending(false);
    }
  };

  if (error) return <p className="empty">{error}</p>;
  if (!view) return null;

  const told = view.chapters.reduce((n, c) => n + c.stories.length, 0);
  const titles = new Map(view.chapters.flatMap((c) => c.stories.map((s) => [s.id, s.title])));
  const askedFor = (storyId: string) =>
    view.questions.filter((q) => q.answered_in.includes(storyId));
  const english = (text: string) => (text ? translations[text] : undefined);
  const translated = Object.keys(translations).length > 0;
  // Until they pick: English, unless their browser is in the language the story
  // was told in. A judge reads English, a Japanese family the words as said.
  const reading =
    picked ?? (navigator.language.toLowerCase().startsWith(view.senior.language) ? 'original' : 'en');
  // One language at a time, except in a quote: the English where there is one,
  // or the original. A quote keeps the original, which is what their voice says.
  const inEnglish = translated && reading === 'en';
  const shown = (text: string) => (inEnglish && english(text)) || text;

  const name = shown(view.senior.name);

  return (
    <div className="family book">
      {translated && (
        <div className="reading" role="group" aria-label="Language">
          <button aria-pressed={reading === 'en'} onClick={() => setReading('en')}>
            English
          </button>
          <button
            lang={view.senior.language}
            aria-pressed={reading === 'original'}
            onClick={() => setReading('original')}
          >
            {ENDONYM[view.senior.language] ?? view.senior.language}
          </button>
        </div>
      )}

      <header className="cover">
        <p className="kicker">A life story</p>
        <h1>{name}</h1>
        {inEnglish && english(view.senior.name) && (
          <p className="original" lang={view.senior.language}>
            {view.senior.name}
          </p>
        )}
        <p className="life">
          {view.senior.birth_year && `Born in ${view.senior.birth_year}`}
          {view.senior.birthplace && `, ${shown(view.senior.birthplace)}`}
        </p>
        {inEnglish && (
          <p className="translated-note">
            Told in {SPOKEN[view.senior.language] ?? 'their own language'}, and translated into
            English by AI so that you can follow. The quotes are {name}’s own words.
          </p>
        )}
        {view.visitor && (
          <p className="yours">
            Your own page, reachable only by its link. <a href={`/talk/${seniorId}`}>Talk again</a>{' '}
            · <a href="/">Start page</a>
          </p>
        )}
      </header>

      {view.writing && (
        <p className="writing" role="status">
          A conversation is still being written up. Its stories will appear here shortly.
        </p>
      )}

      {told === 0 && !view.writing && (
        <p className="empty">
          There is nothing here yet. Stories appear once they have been told, and only once they
          have been agreed to be shared.
        </p>
      )}

      {told > 0 && (
        <nav className="contents" aria-label="Contents">
          <p className="kicker">Contents</p>
          <ol>
            {view.chapters.map((chapter) => (
              <li key={chapter.life_stage}>
                <span>{lifeStage(chapter.life_stage)}</span>
                <ul>
                  {chapter.stories.map((story) => (
                    <li key={story.id}>
                      <a href={`#${story.id}`}>{shown(story.title)}</a>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </nav>
      )}

      {view.chapters.map((chapter, i) => (
        <section key={chapter.life_stage} className="chapter">
          <h2 className="kicker">
            Chapter {i + 1} · {lifeStage(chapter.life_stage)}
          </h2>
          {chapter.stories.map((story) => (
            <article key={story.id} id={story.id} className="told">
              <h3>{shown(story.title)}</h3>
              {story.approx_period && <p className="period">{shown(story.approx_period)}</p>}
              {askedFor(story.id).map((q) => (
                <p key={q.id} className="asked-for">
                  {shown(q.asked_by)} asked: “{shown(q.text)}”
                </p>
              ))}
              <p className="text">{shown(story.summary)}</p>
              <Quotes
                story={story}
                name={name}
                language={view.senior.language}
                english={(text) => (inEnglish ? english(text) : undefined)}
              />
            </article>
          ))}
        </section>
      ))}

      <section id="asking" className="asking">
        <h2 className="kicker">
          {view.showcase ? 'Questions from the family' : `Ask ${name} something`}
        </h2>
        {view.showcase ? (
          <p className="read-only">
            This page is shown to every visitor, so it takes no questions. To ask one, start a
            conversation of your own from the <a href="/">start page</a>: your family page will take
            questions, and your next conversation opens with them.
          </p>
        ) : (
          <form className="ask" onSubmit={ask}>
            <p className="step">
              <span>1</span>Who are you to {name}?
            </p>
            <Who name={name} onChange={(asked_by) => setDraft({ ...draft, asked_by })} />
            <p className="step">
              <span>2</span>What would you like to ask?
            </p>
            <textarea
              aria-label="Your question"
              placeholder="What did you wear on your wedding day?"
              maxLength={300}
              rows={3}
              value={draft.text}
              onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            />
            {draft.asked_by.trim() && draft.text.trim() && (
              <p className="preview">
                {name} will hear something like: “Your {draft.asked_by.trim()} would love to know:{' '}
                {draft.text.trim()}” It is asked in a coming conversation, gently, and if they would
                rather not answer, it is not pressed.
              </p>
            )}
            <button
              type="submit"
              className="start"
              disabled={sending || !draft.asked_by.trim() || !draft.text.trim()}
            >
              Send question
            </button>
            {unsent && <p className="unsent">{unsent}</p>}
          </form>
        )}

        {view.questions.length > 0 && (
          <>
            <p className="kicker sent-head">Questions sent</p>
            <ul className="questions">
              {view.questions.map((q) => {
                const answer = q.answered_in.find((id) => titles.has(id));
                return (
                  <li key={q.id} className={`question ${answer ? 'answered' : q.status}`}>
                    <span className="stamp">
                      {answer ? 'Answered' : q.status === 'waiting' ? 'Waiting' : 'Asked'}
                    </span>
                    <p className="from">From {shown(q.asked_by)}</p>
                    <p className="asked">“{shown(q.text)}”</p>
                    {answer ? (
                      <a href={`#${answer}`}>Read the answer: {shown(titles.get(answer) ?? '')} →</a>
                    ) : (
                      <p className="state">
                        {q.status === 'waiting'
                          ? `Waiting to be asked: ${name} will hear it in a coming conversation.`
                          : 'Asked. No reply has been shared.'}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </section>

    </div>
  );
}

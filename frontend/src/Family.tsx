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
  senior: { name: string; birth_year: number | null; birthplace: string; language: string };
  chapters: Chapter[];
  withheld: number;
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
  const player = useRef<HTMLAudioElement | null>(null);

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

  const play = (quote: Quote) => {
    const audio = player.current;
    if (!audio || !quote.audio) return;
    if (!audio.src.endsWith(quote.audio)) audio.src = quote.audio;
    audio.currentTime = 0;
    void audio.play();
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

  return (
    <div className="family">
      <header>
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
        <h1>{view.senior.name}</h1>
        {inEnglish && english(view.senior.name) && (
          <p className="translation name">{english(view.senior.name)}</p>
        )}
        <p className="life">
          {view.senior.birth_year && `Born in ${view.senior.birth_year}`}
          {view.senior.birthplace && ` · ${shown(view.senior.birthplace)}`}
        </p>
        {inEnglish && (
          <p className="translated-note">
            Told in {SPOKEN[view.senior.language] ?? 'their own language'}, and translated into
            English by AI so that you can follow. Each quote keeps {shown(view.senior.name)}’s own
            words, with the English beneath.
          </p>
        )}
        {view.visitor && (
          <p className="yours">
            Your own page, reachable only by its link. <a href={`/talk/${seniorId}`}>Talk again</a>{' '}
            · <a href="/">Start page</a>
          </p>
        )}
      </header>

      <audio ref={player} preload="none" />

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

      {view.chapters.map((chapter) => (
        <section key={chapter.life_stage} className="chapter">
          <h2>{lifeStage(chapter.life_stage)}</h2>
          {chapter.stories.map((story) => (
            <article key={story.id} id={story.id} className="told">
              {askedFor(story.id).map((q) => (
                <p key={q.id} className="asked-for">
                  {shown(q.asked_by)} asked: {shown(q.text)}
                </p>
              ))}
              <h3>
                {shown(story.title)}
                {story.approx_period && <em>{shown(story.approx_period)}</em>}
              </h3>
              <p>{shown(story.summary)}</p>
              {story.quotes.map((quote, i) => (
                <blockquote key={i}>
                  {quote.audio && (
                    <button className="listen" onClick={() => play(quote)} aria-label="Listen">
                      ▶
                    </button>
                  )}
                  <span>
                    「{quote.text}」
                    {inEnglish && english(quote.text) && (
                      <span className="translation">“{english(quote.text)}”</span>
                    )}
                    {quote.said && quote.said !== quote.text && (
                      <details className="said">
                        <summary>All they said</summary>
                        <span lang={view.senior.language}>
                          <Answer said={quote.said} quoted={quote.text} />
                        </span>
                        {inEnglish && english(quote.said) && (
                          <span className="translation">{english(quote.said)}</span>
                        )}
                      </details>
                    )}
                  </span>
                </blockquote>
              ))}
              {[...story.people, ...story.places].length > 0 && (
                <p className="tags">{[...story.people, ...story.places].map(shown).join(' · ')}</p>
              )}
            </article>
          ))}
        </section>
      ))}

      <section className="asking">
        {view.showcase ? (
          <h2>Questions from the family</h2>
        ) : (
          <>
            <h2>Ask {shown(view.senior.name)} something</h2>
            <p className="how">
              Your question is put to {shown(view.senior.name)} in a coming conversation, gently and in
              their own time, and they will hear that it came from you. If they would rather not
              answer, it is not pressed.
            </p>
          </>
        )}

        {view.questions.length > 0 && (
          <ul className="questions">
            {view.questions.map((q) => (
              <li key={q.id} className={`question ${q.status}`}>
                <p>
                  <span className="who">{shown(q.asked_by)}</span>
                  {shown(q.text)}
                </p>
                <p className="state">
                  {q.status === 'waiting' && 'Waiting to be asked'}
                  {q.status === 'asked' && q.answered_in.length > 0 && (
                    <>
                      Answered in{' '}
                      {q.answered_in.map((id, i) => (
                        <span key={id}>
                          {i > 0 && ', '}
                          <a href={`#${id}`}>{shown(titles.get(id) ?? '')}</a>
                        </span>
                      ))}
                    </>
                  )}
                  {q.status === 'asked' &&
                    q.answered_in.length === 0 &&
                    'Asked. No reply has been shared.'}
                </p>
              </li>
            ))}
          </ul>
        )}

        {view.showcase ? (
          <p className="read-only">
            This page is shown to every visitor, so it takes no questions. To ask one, start a
            conversation of your own from the <a href="/">start page</a>: your family page will take
            questions, and your next conversation opens with them.
          </p>
        ) : (
          <form onSubmit={ask}>
            <input
              aria-label="Who is asking"
              placeholder="Relation and name, e.g. granddaughter Yuka"
              maxLength={40}
              value={draft.asked_by}
              onChange={(e) => setDraft({ ...draft, asked_by: e.target.value })}
            />
            <textarea
              aria-label="Your question"
              placeholder="What did you wear on your wedding day?"
              maxLength={300}
              rows={3}
              value={draft.text}
              onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            />
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
      </section>

      {view.withheld > 0 && (
        <p className="withheld">
          {view.withheld === 1
            ? 'One story has been kept private.'
            : `${view.withheld} stories have been kept private.`}{' '}
          Only the person who told them can choose to share them.
        </p>
      )}
    </div>
  );
}

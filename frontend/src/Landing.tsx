import { useEffect, useState, type FormEvent } from 'react';

import './App.css';
import './Landing.css';

/** The start page, for strangers on the public URL: judges, mostly.
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

export default function Landing() {
  const [start, setStart] = useState<Start | null>(null);
  const [visitor, setVisitor] = useState<Remembered | null>(remembered);
  const [draft, setDraft] = useState({ name: '', language: 'en', ...QUESTIONS.en });
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const supported = canConverse();

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
      <header>
        <h1>
          Kataribe <span lang="ja">語り部</span>
        </h1>
        <p className="lede">
          A voice AI that talks with an elderly person for a few minutes a day, and turns their
          memories into a life story their family can read and hear.
        </p>
        <p className="aside">
          It is built for Japanese seniors. A <em>kataribe</em> is a traditional keeper of oral
          history: the one who remembers the stories and passes them on.
        </p>
      </header>

      {/* First, so a judge can see it at work before talking to it. */}
      {(start?.showcase || start?.video) && (
        <section className="showcase">
          <h2>See how it works</h2>
          {start.showcase && (
            <p>
              The family page of the person in our demo: their life story as their family reads it,
              told in Japanese with English under each passage. Only the stories they agreed to share
              are there, and every quote plays in their own voice.
            </p>
          )}
          {start.video && (
            <p>A whole conversation in Japanese, with English subtitles, in the demo video.</p>
          )}
          <p className="actions">
            {start.showcase && (
              <a className="secondary" href={`/family/${start.showcase}`}>
                Open the family page
              </a>
            )}
            {start.video && (
              <a className="secondary" href={start.video}>
                Watch the demo video
              </a>
            )}
          </p>
        </section>
      )}

      <section className="try">
        <h2>Try it on your own life</h2>
        <p>
          The interviewer asks about your memories for two minutes or so, then writes up what you
          told it the way a family would see it.
        </p>
        <ol className="steps">
          <li>Allow the microphone. The interviewer speaks first.</li>
          <li>Talk as yourself. It follows where you go, one question at a time.</li>
          <li>
            At two minutes it asks whether you want to go on. When you are done, say so or press{' '}
            <strong>Finish</strong>: it asks whether your family may read today’s story. Answer
            aloud, or press <strong>Share with my family</strong> or{' '}
            <strong>Keep it private</strong>.
          </li>
          <li>Your story then appears on your own family page, with your voice behind each quote.</li>
        </ol>

        {!supported && (
          <p className="notice" role="alert">
            This browser cannot hold a conversation here. Please open this page in Chrome or Edge on
            a computer.
          </p>
        )}
        {start && !open && (
          <p className="notice" role="status">
            Today’s conversations are used up. They start again at midnight, Japan time. Meanwhile,
            the video and the life story below show it at work.
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

            <fieldset className="family-question">
              <legend>A question from someone who would love to hear your stories</legend>
              <p className="hint">
                Optional. Your first conversation opens with it, the way a relative’s question
                would.
              </p>
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
            </fieldset>

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

        <p className="privacy">
          Your conversation is recorded and processed by Google’s Gemini. Your family page is
          reachable only by its link, kept in this browser, and shows only what you agree to share,
          though the Kataribe team can see full conversations to fix problems. Everything recorded
          from this page is deleted once judging ends.
        </p>
      </section>

      <footer>
        {start?.repo && <a href={start.repo}>Source code</a>}
      </footer>
    </div>
  );
}

import { useEffect, useRef, useState, type CSSProperties } from 'react';

import './App.css';
import './Talk.css';
import { StartRefused, startInterview, type Interview, type Phase, type Speaker } from './interview';

/** The senior's own screen: their name, one button, and the interviewer's
 *  words in large type while it speaks. Everything the console shows the team
 *  — tuning, transcripts, statuses — stays off it.
 *
 *  It speaks the person's language, since it is theirs.
 *
 *  A visitor's screen, for a persona made from the start page, does a little
 *  more, since a visitor talks for a few minutes and may never come back:
 *  Finish asks the interviewer to wrap up rather than hanging up, so they are
 *  asked about sharing; and afterwards it waits for the writing-up, asks about
 *  any story the interviewer never got to, and links to their family page. */

type Stage = 'loading' | 'unavailable' | 'ready' | 'starting' | 'live' | 'ending' | 'done';
type Problem = 'full' | 'busy' | 'lost';

interface Person {
  name: string;
  language: string;
  visitor: boolean;
}

interface WritingUp {
  state: 'writing' | 'written' | 'failed';
  shared: number;
  unasked: { id: string; title: string }[];
}

interface Words {
  name: (name: string) => string;
  hint: string;
  talk: string;
  connecting: string;
  phase: Record<Phase, string>;
  stop: string;
  ending: string;
  thanks: string;
  later: string;
  again: string;
  full: string;
  busy: string;
  lost: string;
  unsaved: string;
  download: string;
}

const WORDS: Record<string, Words> = {
  ja: {
    name: (name) => `${name}さん`,
    hint: 'ボタンを押すと、聞き手が話しかけます。',
    talk: 'お話しする',
    connecting: 'つないでいます…',
    phase: { listening: '聞いています', thinking: '…', speaking: 'お話ししています' },
    stop: 'おわる',
    ending: 'お話を残しています…',
    thanks: 'ありがとうございました。',
    later: 'また今度、お話を聞かせてください。',
    again: 'もう一度お話しする',
    full: '今日はたくさんお話しいただきました。また明日、お待ちしています。',
    busy: 'いまは、お話しできません。少し時間をおいて、もう一度どうぞ。',
    lost: '途中で切れてしまいました。ここまでのお話は残してあります。',
    unsaved: '録音を送れませんでした。この画面を閉じる前に、録音を保存してください。',
    download: '録音を保存する',
  },
  en: {
    name: (name) => name,
    hint: 'Press the button, and the interviewer will start.',
    talk: 'Talk',
    connecting: 'Connecting…',
    phase: { listening: 'Listening', thinking: '…', speaking: 'Speaking' },
    stop: 'Finish',
    ending: 'Keeping what you said…',
    thanks: 'Thank you.',
    later: 'I would love to hear more another time.',
    again: 'Talk again',
    full: 'That is a lot of talking for today. Come back tomorrow.',
    busy: 'Talking is not possible just now. Please try again in a little while.',
    lost: 'The connection dropped. Everything said until then has been kept.',
    unsaved: 'The recording could not be sent. Save it before closing this screen.',
    download: 'Save the recording',
  },
  fr: {
    name: (name) => name,
    hint: 'Appuyez sur le bouton, et votre interlocuteur commencera.',
    talk: 'Parler',
    connecting: 'Connexion…',
    phase: { listening: 'J’écoute', thinking: '…', speaking: 'Je parle' },
    stop: 'Terminer',
    ending: 'J’enregistre ce que vous avez dit…',
    thanks: 'Merci.',
    later: 'J’aimerais beaucoup en entendre davantage une prochaine fois.',
    again: 'Parler à nouveau',
    full: 'Nous avons beaucoup parlé aujourd’hui. À demain.',
    busy: 'Impossible de parler pour l’instant. Réessayez dans un moment.',
    lost: 'La connexion a été coupée. Tout ce qui a été dit jusque-là est conservé.',
    unsaved: 'L’enregistrement n’a pas pu être envoyé. Gardez-le avant de fermer cet écran.',
    download: 'Garder l’enregistrement',
  },
};

/** Only on a visitor's screen. Visitors may pick English or Japanese. */
interface VisitorWords {
  endNow: string;
  closing: string;
  writing: string;
  slow: string;
  written: (shared: number) => string;
  failed: string;
  ask: string;
  share: string;
  keep: string;
  read: string;
  full: string;
  home: string;
}

const VISITOR_WORDS: Record<string, VisitorWords> = {
  en: {
    endNow: 'End now',
    closing:
      'Wrapping up. It will ask whether your family may read today’s story: answer aloud, then press End now.',
    writing: 'Writing up your story…',
    slow: 'This is taking longer than usual. Your family page will show it once it is ready.',
    written: (shared) =>
      shared === 0
        ? 'Nothing was shared with your family. A story appears there only once you say yes, aloud, when asked.'
        : shared === 1
          ? 'One story is now on your family page.'
          : `${shared} stories are now on your family page.`,
    failed: 'Your story could not be written up this time.',
    ask: 'Before you go: may your family read these?',
    share: 'Let my family read them',
    keep: 'Keep them private',
    read: 'Open your family page',
    full: 'Today’s conversations are used up. They start again at midnight, Japan time.',
    home: 'Back to the start page',
  },
  ja: {
    endNow: '今すぐおわる',
    closing:
      'お話をしめくくっています。今日のお話をご家族が読んでもよいか、お尋ねします。お答えになってから「今すぐおわる」を押してください。',
    writing: 'お話をまとめています…',
    slow: 'いつもより時間がかかっています。まとまり次第、ご家族のページに載ります。',
    written: (shared) =>
      shared === 0
        ? 'ご家族と共有されたお話はありません。お尋ねしたときに、声で「はい」とお答えいただいたお話だけが載ります。'
        : `${shared}つのお話が、ご家族のページに載りました。`,
    failed: '今回は、お話をまとめられませんでした。',
    ask: 'お帰りの前に、こちらのお話を、ご家族が読んでもよいですか？',
    share: 'ご家族に読んでもらう',
    keep: '自分だけのものにする',
    read: 'ご家族のページを開く',
    full: '本日お話しできる回数は終わりました。日本時間の午前0時に、また始まります。',
    home: '最初のページへ',
  },
};

/** How often the end screen asks after the writing-up, and when it says it is
 *  taking longer than it should. Writing one up takes tens of seconds. */
const POLL_MS = 3000;
const SLOW_MS = 180_000;

export default function Talk({ seniorId }: { seniorId: string }) {
  const api = `/api/talk/${seniorId}`;
  const [person, setPerson] = useState<Person | null>(null);
  const [stage, setStage] = useState<Stage>('loading');
  const [phase, setPhase] = useState<Phase>('listening');
  const [level, setLevel] = useState(0);
  const [caption, setCaption] = useState('');
  const [problem, setProblem] = useState<Problem | null>(null);
  const [unsaved, setUnsaved] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const [writingUp, setWritingUp] = useState<WritingUp | null>(null);
  const [slow, setSlow] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const interview = useRef<Interview | null>(null);
  const lastSpeaker = useRef<Speaker | null>(null);
  const saved = useRef<boolean | null>(null);
  const awake = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    fetch(api)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((found) => {
        setPerson(found);
        setStage('ready');
      })
      .catch(() => setStage('unavailable'));
  }, [api]);

  useEffect(() => {
    if (person) document.documentElement.lang = person.language;
  }, [person]);

  useEffect(() => () => void awake.current?.release(), []);

  // A visitor's conversation, once kept, is followed until it is written up.
  const following = stage === 'done' && !!person?.visitor && !unsaved && !!sessionId;
  const written = writingUp?.state === 'written' || writingUp?.state === 'failed';
  useEffect(() => {
    if (!following || written) return;
    const begun = Date.now();
    const look = () =>
      fetch(`${api}/sessions/${sessionId}`)
        .then((r) => (r.ok ? (r.json() as Promise<WritingUp>) : null))
        .then((seen) => seen && setWritingUp(seen))
        .catch(() => undefined)
        .finally(() => setSlow(Date.now() - begun > SLOW_MS));
    void look();
    const timer = setInterval(look, POLL_MS);
    return () => clearInterval(timer);
  }, [following, written, api, sessionId]);

  const words = WORDS[person?.language ?? 'ja'] ?? WORDS.ja;
  const visitorWords = VISITOR_WORDS[person?.language ?? 'en'] ?? VISITOR_WORDS.en;

  /** However the conversation ended. A recording that never reached the server
   *  is offered for saving, since this screen then holds the only copy. */
  const ended = (wav: Blob | undefined) => {
    if (wav && saved.current === false) setUnsaved(URL.createObjectURL(wav));
    void awake.current?.release();
    awake.current = null;
    interview.current = null;
    setStage('done');
  };

  const start = async () => {
    setStage('starting');
    setProblem(null);
    setCaption('');
    setUnsaved(null);
    setPhase('listening');
    setClosing(false);
    setWritingUp(null);
    setSlow(false);
    lastSpeaker.current = null;
    saved.current = null;
    setSessionId(null);
    try {
      interview.current = await startInterview(
        {},
        {
          onTranscript: (speaker, delta) => {
            // A new turn of the interviewer's replaces the caption; the rest of
            // the same turn adds to it. Their own words stay off the screen.
            const continuing = lastSpeaker.current === 'ai';
            lastSpeaker.current = speaker;
            if (speaker === 'ai') setCaption((shown) => (continuing ? shown + delta : delta));
          },
          // Status lines are for the console. This screen says it in its own words.
          onStatus: () => undefined,
          onLevel: setLevel,
          onPhase: setPhase,
          onSaved: (ok) => {
            saved.current = ok;
          },
          onClosing: () => setClosing(true),
          onClosed: (_reason, kept) => {
            setProblem('lost');
            setStage('ending');
            kept.then(ended, () => ended(undefined));
          },
        },
        undefined,
        seniorId,
        api,
      );
      setSessionId(interview.current.sessionId);
      setStage('live');
      // A tablet on a shelf must not go dark mid-sentence.
      if ('wakeLock' in navigator) {
        awake.current = await navigator.wakeLock.request('screen').catch(() => null);
      }
    } catch (error) {
      setProblem(error instanceof StartRefused && error.status === 429 ? 'full' : 'busy');
      setStage('ready');
    }
  };

  /** A visitor's first press asks the interviewer to close, so they are asked
   *  about sharing; the second, or a real person's, ends it there and then. */
  const finish = () => {
    if (person?.visitor && !closing) interview.current?.close();
    else void stop();
  };

  const share = async (yes: boolean) => {
    setChoosing(true);
    try {
      const response = await fetch(`${api}/sessions/${sessionId}/sharing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ share: yes }),
      });
      if (response.ok) setWritingUp(await response.json());
    } finally {
      setChoosing(false);
    }
  };

  const stop = async () => {
    setStage('ending');
    try {
      ended(await interview.current?.stop());
    } catch {
      ended(undefined);
    }
  };

  if (stage === 'loading') return null;

  if (stage === 'unavailable' || !person) {
    return (
      <main className="talk">
        <p className="talk-message" lang="ja">
          このページは開けません。
        </p>
        <p className="talk-hint" lang="en">
          This page is not available.
        </p>
      </main>
    );
  }

  return (
    <main className={`talk ${stage === 'live' ? phase : stage}`}>
      <h1 className="talk-name">{words.name(person.name)}</h1>

      {(stage === 'ready' || stage === 'starting') && (
        <section className="talk-start">
          {problem && (
            <p className="talk-message" role="status">
              {person.visitor && problem === 'full' ? visitorWords.full : words[problem]}
            </p>
          )}
          <button className="talk-button" onClick={start} disabled={stage === 'starting'}>
            {stage === 'starting' ? words.connecting : words.talk}
          </button>
          {!problem && <p className="talk-hint">{words.hint}</p>}
          {person.visitor && (
            <p className="talk-links">
              <a href={`/family/${seniorId}`}>{visitorWords.read}</a>
              <a href="/">{visitorWords.home}</a>
            </p>
          )}
        </section>
      )}

      {stage === 'live' && (
        <section className="talk-live">
          <div
            className="talk-presence"
            style={{ '--level': Math.min(1, level * 4) } as CSSProperties}
            aria-hidden
          />
          <p className="talk-phase" role="status">
            {words.phase[phase]}
          </p>
          <p className="talk-caption" aria-live="polite">
            {caption}
          </p>
          {person.visitor && closing && <p className="talk-hint">{visitorWords.closing}</p>}
          <button className="talk-stop" onClick={finish}>
            {person.visitor && closing ? visitorWords.endNow : words.stop}
          </button>
        </section>
      )}

      {stage === 'ending' && (
        <p className="talk-message" role="status">
          {problem === 'lost' ? words.lost : words.ending}
        </p>
      )}

      {stage === 'done' && following && (
        <section className="talk-done" aria-live="polite">
          <p className="talk-thanks">{problem === 'lost' ? words.lost : words.thanks}</p>
          {writingUp?.state === 'written' && writingUp.unasked.length > 0 ? (
            <div className="talk-ask">
              <p className="talk-message">{visitorWords.ask}</p>
              <ul className="talk-titles">
                {writingUp.unasked.map((story) => (
                  <li key={story.id}>{story.title}</li>
                ))}
              </ul>
              <div className="talk-choices">
                <button className="talk-button" onClick={() => share(true)} disabled={choosing}>
                  {visitorWords.share}
                </button>
                <button className="talk-quiet" onClick={() => share(false)} disabled={choosing}>
                  {visitorWords.keep}
                </button>
              </div>
            </div>
          ) : writingUp?.state === 'written' ? (
            <>
              <p className="talk-message">{visitorWords.written(writingUp.shared)}</p>
              <a className="talk-button" href={`/family/${seniorId}`}>
                {visitorWords.read}
              </a>
            </>
          ) : writingUp?.state === 'failed' ? (
            <p className="talk-message">{visitorWords.failed}</p>
          ) : (
            <p className="talk-message" role="status">
              {slow ? visitorWords.slow : visitorWords.writing}
            </p>
          )}
          <p className="talk-links">
            <button className="talk-quiet" onClick={start}>
              {words.again}
            </button>
            <a href="/">{visitorWords.home}</a>
          </p>
        </section>
      )}

      {stage === 'done' && !following && (
        <section className="talk-done">
          <p className="talk-thanks">{problem === 'lost' ? words.lost : words.thanks}</p>
          <p className="talk-hint">{words.later}</p>
          {unsaved && (
            <p className="talk-unsaved" role="alert">
              {words.unsaved}{' '}
              <a href={unsaved} download="kataribe-session.wav">
                {words.download}
              </a>
            </p>
          )}
          <button className="talk-button talk-again" onClick={start}>
            {words.again}
          </button>
        </section>
      )}
    </main>
  );
}

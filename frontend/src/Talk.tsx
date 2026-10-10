import { useEffect, useRef, useState, type CSSProperties } from 'react';

import './App.css';
import './Talk.css';
import { StartRefused, startInterview, type Interview, type Phase, type Speaker } from './interview';

/** The senior's own screen: their name, one button, and the interviewer's
 *  words in large type while it speaks. Everything the console shows the team
 *  — tuning, transcripts, statuses — stays off it.
 *
 *  It speaks the person's language, since it is theirs. */

type Stage = 'loading' | 'unavailable' | 'ready' | 'starting' | 'live' | 'ending' | 'done';
type Problem = 'full' | 'busy' | 'lost';

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

export default function Talk({ seniorId }: { seniorId: string }) {
  const api = `/api/talk/${seniorId}`;
  const [person, setPerson] = useState<{ name: string; language: string } | null>(null);
  const [stage, setStage] = useState<Stage>('loading');
  const [phase, setPhase] = useState<Phase>('listening');
  const [level, setLevel] = useState(0);
  const [caption, setCaption] = useState('');
  const [problem, setProblem] = useState<Problem | null>(null);
  const [unsaved, setUnsaved] = useState<string | null>(null);

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

  const words = WORDS[person?.language ?? 'ja'] ?? WORDS.ja;

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
    lastSpeaker.current = null;
    saved.current = null;
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
              {words[problem]}
            </p>
          )}
          <button className="talk-button" onClick={start} disabled={stage === 'starting'}>
            {stage === 'starting' ? words.connecting : words.talk}
          </button>
          {!problem && <p className="talk-hint">{words.hint}</p>}
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
          <button className="talk-stop" onClick={stop}>
            {words.stop}
          </button>
        </section>
      )}

      {stage === 'ending' && (
        <p className="talk-message" role="status">
          {problem === 'lost' ? words.lost : words.ending}
        </p>
      )}

      {stage === 'done' && (
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

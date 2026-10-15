import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';

import './App.css';
import './Talk.css';
import {
  StartRefused,
  startInterview,
  type Interview,
  type Phase,
  type Speaker,
} from './interview';
import Path from './Path';
import { mark } from './pathSteps';
import SiteBar from './SiteBar';

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
  /** Before it starts: who they are about to talk with, and what follows. */
  kicker: string;
  hello: (name: string) => string;
  intro: string;
  opensWith: (askedBy: string) => string;
  returning: string;
  begin: string;
  microphone: string;
  expect: string;
  steps: [string, string][];
  page: string;
  closing: string;
  checkIn: string;
  /** Asked on screen while it closes, as the interviewer asks it aloud. */
  question: string;
  shareNow: string;
  keepNow: string;
  endLater: string;
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
  homeShort: string;
}

const VISITOR_WORDS: Record<string, VisitorWords> = {
  en: {
    kicker: 'Your conversation',
    hello: (name) => `Hello, ${name}.`,
    intro:
      'You are about to talk with Kataribe about your own life, as an elder would. It speaks first, and asks one thing at a time.',
    opensWith: (askedBy) =>
      `It opens with a question from ${askedBy.toLowerCase() === 'your family' ? 'your family' : askedBy}:`,
    returning: 'It remembers what you told it last time, and carries on from there.',
    begin: 'Start talking',
    microphone: 'Your browser will ask to use the microphone.',
    expect: 'What to expect',
    steps: [
      [
        'Take your time',
        'Answer as you would a curious grandchild, at your own pace. A pause to remember is fine.',
      ],
      [
        'Two minutes or so',
        'At two minutes it asks whether you want to go on. Carry on as long as you like.',
      ],
      [
        'You choose what is shared',
        'To end, say so or press Finish. It asks whether your family may read today’s story: answer aloud, or press the button.',
      ],
      [
        'Then read it',
        'Within a minute or two, your story is on your family page, with your own words beneath it.',
      ],
    ],
    page: 'Your family page',
    closing: 'Wrapping up. Answer its question aloud, or choose here.',
    checkIn: 'Keep talking if you like. When you are done, tell it so, or choose here.',
    question: 'May your family read today’s story?',
    shareNow: 'Share with my family',
    keepNow: 'Keep it private',
    endLater: 'End now, choose later',
    writing: 'Writing up your story…',
    slow: 'This is taking longer than usual. Your family page will show it once it is ready.',
    written: (shared) =>
      shared === 0
        ? 'Nothing was shared with your family: today’s story stays private.'
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
    homeShort: 'Start page',
  },
  ja: {
    kicker: 'お話の時間',
    hello: (name) => `${name}さん、ようこそ。`,
    intro:
      '語り部の聞き手と、ご自身の人生についてお話しします。聞き手から話しかけ、ひとつずつお尋ねします。',
    opensWith: (askedBy) => `${askedBy}からのご質問で始まります。`,
    returning: '前回のお話を覚えていて、その続きからお聞きします。',
    begin: 'お話を始める',
    microphone: 'マイクの使用を求められたら、許可してください。',
    expect: 'お話の流れ',
    steps: [
      [
        'ゆっくりで大丈夫です',
        'お孫さんに話すように、ご自分のペースでお話しください。思い出す間があっても大丈夫です。',
      ],
      ['二分ほどで', '二分たつと、続けるかどうかをお尋ねします。好きなだけ続けられます。'],
      [
        '載せるかどうかは、ご自分で',
        '終わるときは、そうおっしゃるか「おわる」を押してください。今日のお話をご家族が読んでもよいか、お尋ねします。声でも、ボタンでもお答えいただけます。',
      ],
      ['ご家族のページで読めます', '一、二分ほどで、ご自身の言葉とともにページに載ります。'],
    ],
    page: 'ご家族のページ',
    closing: 'お話をしめくくっています。声でお答えいただくか、こちらでお選びください。',
    checkIn:
      '続けたいときは、そのままお話しください。終わるときは、そうおっしゃるか、こちらでお選びください。',
    question: '今日のお話を、ご家族が読んでもよいですか？',
    shareNow: 'ご家族に読んでもらう',
    keepNow: '自分だけのものにする',
    endLater: '今すぐおわって、あとで決める',
    writing: 'お話をまとめています…',
    slow: 'いつもより時間がかかっています。まとまり次第、ご家族のページに載ります。',
    written: (shared) =>
      shared === 0
        ? 'ご家族と共有されたお話はありません。今日のお話は、ご自分だけのものとしてお預かりします。'
        : `${shared}つのお話が、ご家族のページに載りました。`,
    failed: '今回は、お話をまとめられませんでした。',
    ask: 'お帰りの前に、こちらのお話を、ご家族が読んでもよいですか？',
    share: 'ご家族に読んでもらう',
    keep: '自分だけのものにする',
    read: 'ご家族のページを開く',
    full: '本日お話しできる回数は終わりました。日本時間の午前0時に、また始まります。',
    home: '最初のページに戻る',
    homeShort: '最初のページ',
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
  const [checkedIn, setCheckedIn] = useState(false);
  /** Chosen with the buttons while it closed, applied once it is written up. */
  const [chosen, setChosen] = useState<boolean | null>(null);
  const [writingUp, setWritingUp] = useState<WritingUp | null>(null);
  const [slow, setSlow] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const interview = useRef<Interview | null>(null);
  const lastSpeaker = useRef<Speaker | null>(null);
  const saved = useRef<boolean | null>(null);
  const awake = useRef<WakeLockSentinel | null>(null);
  const applied = useRef(false);

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

  // What a visitor's conversation opens with: the family question still
  // waiting, from their own family page. And whether they have talked before,
  // so it can say it carries on.
  const [opening, setOpening] = useState<{ asked_by: string; text: string } | null>(null);
  const [returning, setReturning] = useState(false);
  useEffect(() => {
    if (!person?.visitor) return;
    fetch(`/api/family/${seniorId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(
        (
          page: {
            chapters: unknown[];
            questions: { asked_by: string; text: string; status: string }[];
          } | null,
        ) => {
          if (!page) return;
          setOpening(page.questions.find((q) => q.status === 'waiting') ?? null);
          setReturning(
            page.chapters.length > 0 || page.questions.some((q) => q.status === 'asked'),
          );
        },
      )
      .catch(() => undefined);
  }, [person?.visitor, seniorId]);

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
    setCheckedIn(false);
    setChosen(null);
    applied.current = false;
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
          onCheckIn: () => setCheckedIn(true),
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
      if (person?.visitor) mark('talk');
      // A tablet on a shelf must not go dark mid-sentence.
      if ('wakeLock' in navigator) {
        awake.current = await navigator.wakeLock.request('screen').catch(() => null);
      }
    } catch (error) {
      setProblem(error instanceof StartRefused && error.status === 429 ? 'full' : 'busy');
      setStage('ready');
    }
  };

  /** A visitor's press asks the interviewer to close, so they are asked about
   *  sharing; a real person's ends it there and then. */
  const finish = () => {
    if (person?.visitor) interview.current?.close();
    else void stop();
  };
  /** Closing, or asked by the clock whether to go on: the question about
   *  sharing is on screen too, and either answer ends it. */
  const wrapping = Boolean(person?.visitor && (closing || checkedIn));
  const choose = (yes: boolean) => {
    setChosen(yes);
    void stop();
  };

  const share = useCallback(
    async (yes: boolean, everything = false) => {
      setChoosing(true);
      try {
        const response = await fetch(`${api}/sessions/${sessionId}/sharing`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ share: yes, everything }),
        });
        if (response.ok) setWritingUp(await response.json());
      } finally {
        setChoosing(false);
      }
    },
    [api, sessionId],
  );

  // A choice made with the buttons while it closed, once there are stories to
  // apply it to. Keep it private is the last word, even over a yes said aloud.
  useEffect(() => {
    if (chosen === null || applied.current || writingUp?.state !== 'written') return;
    applied.current = true;
    void share(chosen, !chosen);
  }, [chosen, writingUp?.state, share]);

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

  // A visitor arrives from the start page knowing nothing of what follows:
  // who they will talk with, what it opens with, and how it ends. A senior's
  // own screen stays one name and one button.
  if (person.visitor && (stage === 'ready' || stage === 'starting')) {
    return (
      <>
        <SiteBar
          back={{ label: visitorWords.home, short: visitorWords.homeShort }}
          on={{ href: `/family/${seniorId}`, label: visitorWords.page }}
        />
        <main className="welcome">
          <div className="welcome-main">
            <section>
              <p className="kicker">{visitorWords.kicker}</p>
              <h1>{visitorWords.hello(person.name)}</h1>
              <p className="intro">{visitorWords.intro}</p>
              {opening ? (
                <div className="opens">
                  <p className="by">{visitorWords.opensWith(opening.asked_by)}</p>
                  <p className="asked">“{opening.text}”</p>
                </div>
              ) : (
                returning && <p className="intro">{visitorWords.returning}</p>
              )}
              {problem && (
                <p className="notice" role="status">
                  {problem === 'full' ? visitorWords.full : words[problem]}
                </p>
              )}
              <button className="go" onClick={start} disabled={stage === 'starting'}>
                {stage === 'starting' ? words.connecting : visitorWords.begin}
              </button>
              <p className="microphone">{visitorWords.microphone}</p>
            </section>
            <aside className="expect">
              <h2>{visitorWords.expect}</h2>
              <ol>
                {visitorWords.steps.map(([title, text]) => (
                  <li key={title}>
                    <strong>{title}</strong>
                    <span>{text}</span>
                  </li>
                ))}
              </ol>
            </aside>
          </div>
        </main>
        <Path />
      </>
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
          {wrapping ? (
            <div className="talk-wrap">
              <p className="talk-hint">{closing ? visitorWords.closing : visitorWords.checkIn}</p>
              <p className="talk-question">{visitorWords.question}</p>
              <div className="talk-choices">
                <button className="talk-button" onClick={() => choose(true)}>
                  {visitorWords.shareNow}
                </button>
                <button className="talk-button" onClick={() => choose(false)}>
                  {visitorWords.keepNow}
                </button>
              </div>
              <button className="talk-quiet" onClick={() => void stop()}>
                {visitorWords.endLater}
              </button>
            </div>
          ) : (
            <button className="talk-stop" onClick={finish}>
              {words.stop}
            </button>
          )}
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
          {writingUp?.state === 'written' && writingUp.unasked.length > 0 && chosen === null ? (
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
      {/* After a visitor's conversation: what is left of their path. Never
          while talking, and never on a senior's own screen. */}
      {person.visitor && stage === 'done' && <Path />}
    </main>
  );
}

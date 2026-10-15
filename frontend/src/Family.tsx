import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react';

import './App.css';
import './Family.css';
import { lifeStage } from './lifeStages';
import Path from './Path';
import { GO, mark, type Place } from './pathSteps';
import SiteBar from './SiteBar';

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

/** The page's own words, in the language it is read in: English, or the
 *  language the story was told in when the reader chose it, so that a Japanese
 *  family reads a page that is Japanese throughout. The Japanese is still to be
 *  reviewed by a native speaker. */
interface Words {
  lifeStory: string;
  born: (year: number | null, place: string) => string;
  contents: string;
  chapter: (n: number) => string;
  stage: (stored: string) => string;
  quotes: (count: number, name: string) => string;
  hideQuotes: string;
  noRecording: string;
  listen: string;
  pause: string;
  allTheySaid: string;
  askedFor: (by: string, text: string) => string;
  /** Quotation marks as the language sets them: “…” or 「…」. */
  quoted: (text: string) => string;
  writing: string;
  empty: string;
  yours: string;
  talkAgain: string;
  startPage: string;
  /** Its short forms, for the bar on a phone. */
  startPageShort: string;
  tryIt: string;
  tryItShort: string;
  askButton: (name: string) => string;
  familyQuestions: string;
  /** The corner button's short forms, so it shares a phone's last line. */
  askShort: string;
  questionsShort: string;
  sent: string;
  askHead: (name: string) => string;
  step1: (name: string) => string;
  step2: string;
  placeholder: string;
  preview: (name: string, by: string, text: string) => string;
  send: string;
  unsent: string;
  stamp: { answered: string; waiting: string; asked: string };
  from: (by: string) => string;
  readAnswer: (title: string) => string;
  waitingNote: (name: string) => string;
  askedNote: string;
  readOnly: [string, string, string];
  relations: Record<string, string[]>;
  other: string;
  otherPlaceholder: string;
  relationLabel: string;
  nameLabel: string;
  namePlaceholder: string;
  who: (relation: string, person: string) => string;
  whoGroup: (name: string) => string;
}

const WORDS: Record<string, Words> = {
  en: {
    lifeStory: 'A life story',
    born: (year, place) => [year && `Born in ${year}`, place].filter(Boolean).join(', '),
    contents: 'Contents',
    chapter: (n) => `Chapter ${n}`,
    stage: lifeStage,
    quotes: (count, name) =>
      `${count === 1 ? 'The quote' : `All ${count} quotes`}, in ${name}’s own words and voice`,
    hideQuotes: 'Hide the quotes',
    noRecording: 'No recording',
    listen: 'Listen',
    pause: 'Pause',
    allTheySaid: 'The whole answer',
    askedFor: (by, text) => `${by} asked: “${text}”`,
    quoted: (text) => `“${text}”`,
    writing: 'A conversation is still being written up. Its stories will appear here shortly.',
    empty:
      'There is nothing here yet. Stories appear once they have been told, and only once they have been agreed to be shared.',
    yours: 'Your own page, reachable only by its link.',
    talkAgain: 'Talk again',
    startPage: 'Back to the start page',
    startPageShort: 'Start page',
    tryIt: 'Try it on your own life',
    tryItShort: 'Try it yourself',
    askButton: (name) => `Ask ${name} a question`,
    familyQuestions: 'Questions from the family',
    askShort: 'Ask a question',
    questionsShort: 'Questions',
    sent: 'Questions sent',
    askHead: (name) => `Ask ${name} something`,
    step1: (name) => `Who are you to ${name}?`,
    step2: 'What would you like to ask?',
    placeholder: 'What did you wear on your wedding day?',
    preview: (name, by, text) =>
      `${name} will hear something like: “Your ${by} would love to know: ${text}” It is asked gently in a coming conversation, and never pressed.`,
    send: 'Send question',
    unsent: 'Your question could not be sent just now. Please try again in a moment.',
    stamp: { answered: 'Answered', waiting: 'Waiting', asked: 'Asked' },
    from: (by) => `From ${by}`,
    readAnswer: (title) => `Read the answer: ${title} →`,
    waitingNote: (name) => `Waiting to be asked: ${name} will hear it in a coming conversation.`,
    askedNote: 'Asked. No reply has been shared.',
    readOnly: [
      'This example is shown to every visitor, so nothing is sent from it. ',
      'Try it on your own life',
      ': your own family page takes questions, and your next conversation opens with them.',
    ],
    relations: {
      Grandchildren: ['granddaughter', 'grandson', 'great-granddaughter', 'great-grandson'],
      Children: ['daughter', 'son'],
      Partner: ['wife', 'husband', 'partner'],
      'Brothers & sisters': ['sister', 'brother'],
      'In-laws': ['daughter-in-law', 'son-in-law', 'sister-in-law', 'brother-in-law'],
      'Wider family': ['niece', 'nephew', 'cousin'],
      'Friends & others': ['friend', 'neighbour', 'carer', 'former colleague'],
    },
    other: 'Other…',
    otherPlaceholder: 'e.g. goddaughter',
    relationLabel: 'Your relation',
    nameLabel: 'Your name',
    namePlaceholder: 'Your first name',
    who: (relation, person) => [relation, person].filter(Boolean).join(' '),
    whoGroup: (name) => `Who you are to ${name}`,
  },
  ja: {
    lifeStory: '人生の物語',
    born: (year, place) =>
      [year && `${year}年生まれ`, place && `${place}出身`].filter(Boolean).join('・'),
    contents: '目次',
    chapter: (n) => `第${n}章`,
    stage: (stored) => stored,
    quotes: (count, name) => `${name}さんご本人の言葉と声で（${count}件）`,
    hideQuotes: 'ご本人の言葉を閉じる',
    noRecording: '録音はありません',
    listen: '聞く',
    pause: '一時停止',
    allTheySaid: 'このときのお話をすべて読む',
    askedFor: (by, text) => `${by}さんからのご質問：「${text}」`,
    quoted: (text) => `「${text}」`,
    writing: 'お話をまとめているところです。まもなく、ここに載ります。',
    empty:
      'まだお話は載っていません。お話しいただき、ご家族に読んでもらってよいとおっしゃったお話だけが、ここに載ります。',
    yours: 'このページは、リンクを知っている方だけが開けます。',
    talkAgain: 'もう一度お話しする',
    startPage: '最初のページに戻る',
    startPageShort: '最初のページ',
    tryIt: 'ご自分のお話で試してみる',
    tryItShort: '試してみる',
    askButton: (name) => `${name}さんに質問する`,
    familyQuestions: 'ご家族からのご質問',
    askShort: '質問する',
    questionsShort: 'ご質問',
    sent: '送ったご質問',
    askHead: (name) => `${name}さんに聞いてみる`,
    step1: (name) => `${name}さんとのご関係は？`,
    step2: '何を聞いてみたいですか？',
    placeholder: '結婚式のときのお着物は、どんなものでしたか？',
    preview: (name, by, text) =>
      `${name}さんには、たとえば「${by}さんが『${text}』と知りたがっていらっしゃいますよ」と伝わります。次のお話のときにそっとお尋ねし、答えたくないときは無理にはお聞きしません。`,
    send: '質問を送る',
    unsent: 'ただいま質問を送れませんでした。少し時間をおいて、もう一度お試しください。',
    stamp: { answered: 'お答えあり', waiting: 'これから', asked: 'お尋ね済み' },
    from: (by) => `${by}より`,
    readAnswer: (title) => `お答えを読む：${title} →`,
    waitingNote: (name) => `まだお尋ねしていません。次のお話のときに、${name}さんにお伝えします。`,
    askedNote: 'お尋ねしました。共有されたお答えは、まだありません。',
    readOnly: [
      'この見本のページはどなたにも公開しているため、ここからは送られません。',
      'ご自分のお話で試してみる',
      'と、ご自身のページから質問を送ることができ、次のお話はその質問から始まります。',
    ],
    relations: {
      孫: ['孫', 'ひ孫'],
      子ども: ['娘', '息子'],
      配偶者: ['妻', '夫', 'パートナー'],
      きょうだい: ['姉', '妹', '兄', '弟'],
      義理の家族: ['息子の妻', '娘の夫', '義理のきょうだい'],
      親戚: ['姪', '甥', 'いとこ'],
      '友人・その他': ['友人', 'ご近所の方', '介護の方', '元同僚'],
    },
    other: 'その他…',
    otherPlaceholder: '例：いとこの子',
    relationLabel: 'ご関係',
    nameLabel: 'お名前',
    namePlaceholder: 'お名前（下のお名前）',
    who: (relation, person) => [relation, person].filter(Boolean).join('の'),
    whoGroup: (name) => `${name}さんとのご関係`,
  },
};

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
function Player({ audio, w }: { audio: string | null; w: Words }) {
  const sound = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [done, setDone] = useState(0);
  const [length, setLength] = useState<number | null>(null);
  if (!audio) {
    return (
      <div className="player none">
        <button className="listen" disabled aria-label={w.noRecording}>
          ▶
        </button>
        <span className="bar" />
        <span className="time">{w.noRecording}</span>
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
      <button className="listen" onClick={toggle} aria-label={playing ? w.pause : w.listen}>
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
  w,
}: {
  story: Story;
  name: string;
  language: string;
  english: (text: string) => string | undefined;
  w: Words;
}) {
  const [open, setOpen] = useState(false);
  const count = story.quotes.length;
  if (count === 0) return null;
  return (
    <div className="quotes">
      <button className="toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? w.hideQuotes : w.quotes(count, name)}
      </button>
      {open &&
        story.quotes.map((quote, i) => (
          <blockquote key={i}>
            <span lang={language}>「{quote.text}」</span>
            {english(quote.text) && <span className="translation">“{english(quote.text)}”</span>}
            <Player audio={quote.audio} w={w} />
            {quote.said && quote.said !== quote.text && (
              <details className="said">
                <summary>{w.allTheySaid}</summary>
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

/* Relations by group, so finding yours is two presses among few, and Other
   for whatever is not here: see `relations` in WORDS. The interviewer says it
   aloud: "Your daughter-in-law Aiko would love to know…". */

/** Who is asking, as the interviewer will say it: a relation, then a name. */
function Who({
  name,
  w,
  onChange,
}: {
  name: string;
  w: Words;
  onChange: (askedBy: string) => void;
}) {
  const [group, setGroup] = useState<string | null>(null);
  const [relation, setRelation] = useState('');
  const [other, setOther] = useState(false);
  const [person, setPerson] = useState('');
  const update = (r: string, n: string) => {
    setRelation(r);
    setPerson(n);
    onChange(w.who(r.trim(), n.trim()));
  };
  return (
    <>
      <div className="relations" role="group" aria-label={w.whoGroup(name)}>
        {Object.keys(w.relations).map((g) => (
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
          {w.relations[group].map((r) => (
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
            {w.other}
          </button>
        </div>
      )}
      {other && (
        <input
          aria-label={w.relationLabel}
          placeholder={w.otherPlaceholder}
          maxLength={30}
          value={relation}
          onChange={(e) => update(e.target.value, person)}
        />
      )}
      {group && (
        <input
          aria-label={w.nameLabel}
          placeholder={w.namePlaceholder}
          maxLength={25}
          value={person}
          onChange={(e) => update(relation, e.target.value)}
        />
      )}
    </>
  );
}

export default function Family({
  seniorId,
  startOn,
}: {
  seniorId: string;
  /** The questions' tab first, when the judge's path asked for them. */
  startOn?: 'questions';
}) {
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({ asked_by: '', text: '' });
  const [sending, setSending] = useState(false);
  const [unsent, setUnsent] = useState<string | null>(null);
  /** The life story, or the family's questions and the form for asking. */
  const [tab, setTab] = useState<'story' | 'questions'>(() =>
    startOn === 'questions' || window.location.hash === '#questions' ? 'questions' : 'story',
  );
  const pages = useRef<HTMLDivElement | null>(null);
  /** English for the page's text, by the text, when they speak another
   *  language. Shown under the original, never in its place. */
  const [translations, setTranslations] = useState<Record<string, string>>({});
  /** The reader's own choice of language, once they have made one. */
  const [picked, setReading] = useState<'en' | 'original' | null>(null);
  // The judge's path: the demo's page read, its questions seen, their own page
  // read; and its Go to the questions when already here.
  useEffect(() => {
    if (view?.showcase) mark('read');
    if (view?.visitor) mark('own');
  }, [view?.showcase, view?.visitor]);
  useEffect(() => {
    if (view?.showcase && tab === 'questions') mark('asked');
  }, [view?.showcase, tab]);
  useEffect(() => {
    const onGo = (event: Event) => {
      if ((event as CustomEvent<Place>).detail === 'questions') setTab('questions');
    };
    window.addEventListener(GO, onGo);
    return () => window.removeEventListener(GO, onGo);
  }, []);

  /** The story being read, which the contents show: the last one whose title
   *  has passed the top third of the screen, or the last one once the page
   *  has scrolled to its end, however short that story is. One chosen from the
   *  contents stays chosen until the reader scrolls on their own. */
  const [here, setHere] = useState<string | null>(null);
  const root = useRef<HTMLDivElement | null>(null);
  const chosen = useRef(false);
  useEffect(() => {
    const page = root.current;
    if (!page) return;
    // The window, or whatever the page scrolls within, as over the start page.
    let scroller: Element | null = page.parentElement;
    while (scroller && !/(auto|scroll)/.test(getComputedStyle(scroller).overflowY)) {
      scroller = scroller.parentElement;
    }
    const scrolled = scroller ?? document.scrollingElement;
    const follow = () => {
      if (chosen.current || !scrolled) return;
      const stories = [...page.querySelectorAll<HTMLElement>('.told')];
      if (stories.length === 0) return;
      const atEnd =
        scrolled.scrollTop > 0 &&
        scrolled.scrollTop + scrolled.clientHeight >= scrolled.scrollHeight - 2;
      const passed = stories.filter((s) => s.getBoundingClientRect().top <= innerHeight / 3);
      setHere((atEnd ? stories[stories.length - 1] : (passed.pop() ?? stories[0])).id);
    };
    const release = () => {
      chosen.current = false;
    };
    follow();
    document.addEventListener('scroll', follow, { capture: true, passive: true });
    window.addEventListener('wheel', release, { passive: true });
    window.addEventListener('touchmove', release, { passive: true });
    window.addEventListener('keydown', release);
    return () => {
      document.removeEventListener('scroll', follow, { capture: true });
      window.removeEventListener('wheel', release);
      window.removeEventListener('touchmove', release);
      window.removeEventListener('keydown', release);
    };
  }, [view]);

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
      setUnsent('failed');
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
    picked ??
    (navigator.language.toLowerCase().startsWith(view.senior.language) ? 'original' : 'en');
  // One language at a time, except in a quote: the English where there is one,
  // or the original. A quote keeps the original, which is what their voice says.
  const inEnglish = translated && reading === 'en';
  const shown = (text: string) => (inEnglish && english(text)) || text;

  const name = shown(view.senior.name);
  const w = (!inEnglish && WORDS[view.senior.language]) || WORDS.en;
  // The example and a visitor's own page are reached from the start page, so
  // they lead back to it, the example also opened over it. A family's own
  // page is theirs alone.
  const back = view.showcase || view.visitor;

  const questions = (
    <section id="asking" className="asking">
      {view.questions.length > 0 && (
        <>
          <h2 className="kicker">{view.showcase ? w.familyQuestions : w.sent}</h2>
          <ul className="questions">
            {view.questions.map((q) => {
              const answer = q.answered_in.find((id) => titles.has(id));
              return (
                <li key={q.id} className={`question ${answer ? 'answered' : q.status}`}>
                  <span className="stamp">
                    {answer
                      ? w.stamp.answered
                      : q.status === 'waiting'
                        ? w.stamp.waiting
                        : w.stamp.asked}
                  </span>
                  <p className="from">{w.from(shown(q.asked_by))}</p>
                  <p className="asked">{w.quoted(shown(q.text))}</p>
                  {answer ? (
                    <a href={`#${answer}`}>{w.readAnswer(shown(titles.get(answer) ?? ''))}</a>
                  ) : (
                    <p className="state">
                      {q.status === 'waiting' ? w.waitingNote(name) : w.askedNote}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}

      {/* On the example too, so a judge sees how a question is put; but it
          sends nothing, since every visitor reads that page and nobody would
          ever answer there. */}
      <h2 className="kicker ask-head">{w.askHead(name)}</h2>
      <form className="ask" onSubmit={view.showcase ? (e) => e.preventDefault() : ask}>
        <p className="step">
          <span>1</span>
          {w.step1(name)}
        </p>
        <Who name={name} w={w} onChange={(asked_by) => setDraft({ ...draft, asked_by })} />
        <p className="step">
          <span>2</span>
          {w.step2}
        </p>
        <textarea
          aria-label={w.step2}
          placeholder={w.placeholder}
          maxLength={300}
          rows={3}
          value={draft.text}
          onChange={(e) => setDraft({ ...draft, text: e.target.value })}
        />
        {draft.asked_by.trim() && draft.text.trim() && (
          <p className="preview">{w.preview(name, draft.asked_by.trim(), draft.text.trim())}</p>
        )}
        <button
          type="submit"
          className="start"
          disabled={view.showcase || sending || !draft.asked_by.trim() || !draft.text.trim()}
        >
          {w.send}
        </button>
        {view.showcase && (
          <p className="read-only">
            {w.readOnly[0]}
            <a href="/#try">{w.readOnly[1]}</a>
            {w.readOnly[2]}
          </p>
        )}
        {unsent && <p className="unsent">{w.unsent}</p>}
      </form>
    </section>
  );

  const languages = translated && (
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
  );

  // The way on from here: the example leads to trying it, a visitor's own
  // page to talking again.
  const bar = back && (
    <SiteBar
      back={{ label: w.startPage, short: w.startPageShort }}
      on={
        view.showcase
          ? { href: '/#try', label: w.tryIt, short: w.tryItShort }
          : { href: `/talk/${seniorId}`, label: w.talkAgain }
      }
    />
  );

  const coverNotes = (
    <>
      {inEnglish && (
        <p className="translated-note">
          Told in {SPOKEN[view.senior.language] ?? 'their own language'}, and translated into
          English by AI so that you can follow. The quotes are {name}’s own words.
        </p>
      )}
      {view.visitor && <p className="yours">{w.yours}</p>}
    </>
  );

  const notices = (
    <>
      {view.writing && (
        <p className="writing" role="status">
          {w.writing}
        </p>
      )}
      {told === 0 && !view.writing && <p className="empty">{w.empty}</p>}
    </>
  );

  const quotesOf = (story: Story) => (
    <Quotes
      w={w}
      story={story}
      name={name}
      language={view.senior.language}
      english={(text) => (inEnglish ? english(text) : undefined)}
    />
  );

  // The questions are a tab beside the life story, chosen on 2026-10-14 so a
  // judge sees them from the first screen, over a panel behind a button, a
  // last chapter, and a card above the first one. Asking, from the guide or
  // the button in a phone's corner, opens that tab.
  const toQuestions = () => {
    setTab('questions');
    requestAnimationFrame(() => pages.current?.scrollIntoView());
  };
  /** A story, from the contents or a question's answer, back in the life story. */
  const toStory = (id: string) => {
    setTab('story');
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView());
  };
  const answerLink = (event: MouseEvent) => {
    const href = (event.target as HTMLElement).closest('a')?.getAttribute('href');
    if (tab !== 'questions' || !href?.startsWith('#')) return;
    event.preventDefault();
    toStory(href.slice(1));
  };

  // A guide beside the stories: who this is, the language, and the contents,
  // in view all the way down on a desktop, showing where the reader is.
  return (
    <>
      {bar}
      <div className="family" ref={root}>
        <aside className="side">
          <header className="cover">
            <p className="kicker">{w.lifeStory}</p>
            <h1>{name}</h1>
            {inEnglish && english(view.senior.name) && (
              <p className="original" lang={view.senior.language}>
                {view.senior.name}
              </p>
            )}
            <p className="life">{w.born(view.senior.birth_year, shown(view.senior.birthplace))}</p>
          </header>
          {languages}
          {told > 0 && (
            <nav className="contents" aria-label={w.contents}>
              {view.chapters.map((chapter, i) => (
                <div key={chapter.life_stage}>
                  <p className="stage">
                    <span>{i + 1}</span>
                    {w.stage(chapter.life_stage)}
                  </p>
                  <ul>
                    {chapter.stories.map((story) => (
                      <li key={story.id}>
                        <a
                          href={`#${story.id}`}
                          aria-current={
                            tab === 'story' && here === story.id ? 'location' : undefined
                          }
                          onClick={(event) => {
                            chosen.current = true;
                            setHere(story.id);
                            if (tab === 'questions') {
                              event.preventDefault();
                              toStory(story.id);
                            }
                          }}
                        >
                          {shown(story.title)}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </nav>
          )}
          <button className="side-ask" aria-pressed={tab === 'questions'} onClick={toQuestions}>
            {view.showcase ? w.familyQuestions : w.askButton(name)}
            {view.questions.length > 0 && <span className="count">{view.questions.length}</span>}
          </button>
        </aside>

        <div className="pages" ref={pages} onClick={answerLink}>
          {coverNotes}
          <div className="page-tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'story'} onClick={() => setTab('story')}>
              {w.lifeStory} {told > 0 && <span>{told}</span>}
            </button>
            <button
              role="tab"
              aria-selected={tab === 'questions'}
              onClick={() => setTab('questions')}
            >
              <i className="long">{w.familyQuestions}</i>
              <i className="short">{w.questionsShort}</i>
              {view.questions.length > 0 && <span>{view.questions.length}</span>}
            </button>
          </div>
          {tab === 'questions' ? (
            questions
          ) : (
            <>
              {notices}
              {view.chapters.map((chapter, i) => (
                <section key={chapter.life_stage} className="chapter">
                  <h2>
                    <span className="kicker">{w.chapter(i + 1)}</span>
                    {w.stage(chapter.life_stage)}
                  </h2>
                  {chapter.stories.map((story) => (
                    <article key={story.id} id={story.id} className="told">
                      <h3>{shown(story.title)}</h3>
                      {story.approx_period && (
                        <p className="period">{shown(story.approx_period)}</p>
                      )}
                      {askedFor(story.id).map((q) => (
                        <p key={q.id} className="asked-for">
                          {w.askedFor(shown(q.asked_by), shown(q.text))}
                        </p>
                      ))}
                      <p className="text" lang={inEnglish ? 'en' : view.senior.language}>
                        {shown(story.summary)}
                      </p>
                      {quotesOf(story)}
                    </article>
                  ))}
                </section>
              ))}
            </>
          )}
        </div>

        {/* On a phone, where the guide has scrolled away: the questions from
            anywhere in the story. */}
        <button className="ask-button" aria-pressed={tab === 'questions'} onClick={toQuestions}>
          <span className="long">{view.showcase ? w.familyQuestions : w.askButton(name)}</span>
          <span className="short">{view.showcase ? w.questionsShort : w.askShort}</span>
          {view.questions.length > 0 && <span className="count">{view.questions.length}</span>}
        </button>
      </div>
      {/* On its own page; over the start page, the start page shows it. */}
      {back && window.location.pathname.startsWith('/family/') && <Path />}
    </>
  );
}

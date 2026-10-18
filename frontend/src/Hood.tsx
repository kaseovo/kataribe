import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react';

import './Hood.css';

/** The start page's Under the hood: the five steps from a voice to a family
 *  page, for a technical judge. All five stay in view; the one chosen shows
 *  what it does in full, beside a picture of it at work on the demo's first
 *  conversation. Chosen on 2026-10-16 to match the video's under-the-hood
 *  segment, which shows the same five panels, over five cards of a line each,
 *  which said what each step is for but never showed one working.
 *
 *  Nothing here names a tool but Gemini, as in the video. */

interface Step {
  name: string;
  /** The line on its card, as the video has it. */
  short: string;
  /** What it does, in full. */
  more: string[];
  /** Where it happens: the file, its path in the repository, and what is in it. */
  code: [string, string, string][];
  picture: () => ReactNode;
}

const STEPS: Step[] = [
  {
    name: 'Talk',
    short: 'Live, by voice. It waits through a pause for thought.',
    more: [
      'The browser talks with Gemini Live directly, on a single-use token made for this conversation. The interviewer’s instructions, its voice and its patience are sealed into the token on the server, so nothing in the browser can change them.',
      'It speaks first and asks one thing at a time. When the person stops to remember, it waits: five seconds of silence in Japanese, since in tests a shorter wait cut into a pause for thought, and four in English. Both voices are recorded on one timeline.',
    ],
    code: [
      ['interviewer_ja.en.md', 'backend/src/kataribe/prompts/interviewer_ja.en.md', 'its instructions, glossed in English'],
      ['gemini.py', 'backend/src/kataribe/gemini.py', 'the token, with everything sealed into it'],
      ['interview.ts', 'frontend/src/interview.ts', 'the browser’s side of the conversation'],
    ],
    picture: () => <Voices />,
  },
  {
    name: 'Write',
    short: 'The conversation becomes stories, with the quotes they rest on.',
    more: [
      'When the conversation ends, a Gemini text model reads the whole transcript and writes it up as stories: each with a title, a short retelling, the time of life it belongs to, the people and places in it, and the person’s own sentences it rests on.',
      'It writes in the language spoken, and is told never to add a detail. The quotes are what the next step checks.',
    ],
    code: [['brain.py', 'backend/src/kataribe/brain.py', 'extract(): the transcript into stories']],
    picture: () => <Written />,
  },
  {
    name: 'Check',
    short: 'Every quote found word for word, then heard in the recording.',
    more: [
      'Every quote must appear, word for word, in the person’s own turns of the transcript, ignoring only punctuation and spacing.',
      'Then Gemini listens to the clip the family would play for it, and says whether it hears the same words. Spelling is forgiven, kana for kanji or 18 for 十八; a different name, place or number is not. A quote that fails either test is dropped.',
      'A yes to sharing goes through the same two checks. One that cannot be confirmed leaves the story private, to be asked about again.',
    ],
    code: [
      ['brain.py', 'backend/src/kataribe/brain.py', 'verify() and confirm(): word for word, then heard'],
      ['processing.py', 'backend/src/kataribe/processing.py', '_bear_out(): what a clip does not bear out is held back'],
    ],
    picture: () => <Checked />,
  },
  {
    name: 'Share',
    short: 'Only what she agreed to reaches the family.',
    more: [
      'At the close, the interviewer asks whether the family may read today’s stories, and the person answers aloud; a visitor can also press a button. Only a story with a yes reaches the family page, in Japanese or in English, each quote with its own clip: the person’s voice alone, in the one turn it came from.',
      'A story kept private is not shown, or counted, anywhere on the family page. Nothing else of the recording is ever linked.',
    ],
    code: [
      ['api/sessions.py', 'backend/src/kataribe/api/sessions.py', 'read_family_view(): only what was shared'],
      ['clips.py', 'backend/src/kataribe/clips.py', 'one turn of the person’s voice, and nothing else'],
    ],
    picture: () => <Shared />,
  },
  {
    name: 'Plan',
    short: 'What is still untold, and the family’s question, become next time’s.',
    more: [
      'After each conversation it reads the whole life told so far, finds the times of life with no story yet, and plans the next questions.',
      'A relative’s question goes first, two at most in a conversation, saying who asked; the answer appears under it on the family page. Whatever was refused is never raised again, and a family question that touches it is held back.',
    ],
    code: [
      ['brain.py', 'backend/src/kataribe/brain.py', 'plan_next() and screen(): what to ask, and what not to'],
      ['processing.py', 'backend/src/kataribe/processing.py', 'process_session(): the loop after each conversation'],
    ],
    picture: () => <Planned />,
  },
];

export default function Hood({ repo }: { repo?: string }) {
  const [chosen, setChosen] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const step = STEPS[chosen];

  // The tabs pattern: arrows move along the steps, Home and End to either end.
  const onKey = (event: KeyboardEvent) => {
    const to = {
      ArrowRight: (chosen + 1) % STEPS.length,
      ArrowLeft: (chosen + STEPS.length - 1) % STEPS.length,
      Home: 0,
      End: STEPS.length - 1,
    }[event.key];
    if (to === undefined) return;
    event.preventDefault();
    setChosen(to);
    tabs.current[to]?.focus();
  };

  return (
    <section className="hood" aria-labelledby="hood-title">
      <h2 id="hood-title">Under the hood</h2>
      <p className="note">
        From a voice to a family page, in five steps. Choose one to see it at work on the demo’s
        first conversation.
      </p>

      <div className="hood-steps" role="tablist" aria-label="The five steps" onKeyDown={onKey}>
        {STEPS.map((s, i) => (
          <button
            key={s.name}
            ref={(el) => {
              tabs.current[i] = el;
            }}
            id={`hood-tab-${i}`}
            type="button"
            role="tab"
            aria-selected={i === chosen}
            aria-controls="hood-panel"
            tabIndex={i === chosen ? 0 : -1}
            className={i === chosen ? 'on' : ''}
            onClick={() => setChosen(i)}
          >
            <span className="n" aria-hidden>
              {i + 1}
            </span>
            <strong>{s.name}</strong>
            <span className="short">{s.short}</span>
          </button>
        ))}
      </div>

      <div
        className="hood-detail"
        id="hood-panel"
        role="tabpanel"
        aria-labelledby={`hood-tab-${chosen}`}
      >
        <div className="hood-text">
          <h3>
            <span aria-hidden>{chosen + 1}</span> {step.name}
          </h3>
          {step.more.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
          {repo && (
            <div className="in-code">
              <p className="pic-label">In the code</p>
              <ul>
                {step.code.map(([file, path, what]) => (
                  <li key={path + what}>
                    <a href={`${repo}/blob/main/${path}`}>{file}</a> {what}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <figure className="hood-figure">
          {step.picture()}
          <figcaption>From the demo: Setsuko’s first conversation.</figcaption>
        </figure>
      </div>

      {repo && (
        <p className="stack">
          Open source, under the MIT licence, with every choice explained where it is made.
          <a href={repo}>
            Browse the code on GitHub <span aria-hidden>→</span>
          </a>
        </p>
      )}
    </section>
  );
}

/* ---- The pictures, one per step. Drawn, not recorded: the demo's own lines. */

/** Bar heights for a voice, the same on every visit. */
function bars(count: number, seed: number): number[] {
  return Array.from({ length: count }, (_, i) => {
    const x = Math.sin((i + 1) * 12.9898 + seed * 78.233) * 43758.5453;
    return 0.25 + 0.75 * (x - Math.floor(x));
  });
}

const HER = bars(46, 1.7);
const ITS = bars(14, 4.1);

/** How long Setsuko stopped to remember in the demo's first conversation, from
 *  0:35 to 0:39, as her recording has it and the video's pause bar shows it. */
const PAUSE_SECONDS = 4.0;
/** How long the interviewer waits through silence in Japanese before it speaks. */
const PATIENCE_SECONDS = 5;

function Voices() {
  return (
    <div className="pic voices">
      <p className="pic-head">
        <span className="live">
          <i aria-hidden /> Live
        </span>
        <span className="clock">Session 1 · 0:35</span>
      </p>
      <div className="lane">
        <span className="speaker her">Setsuko</span>
        <span className="wave">
          <span className="lead">
            {HER.slice(0, 26).map((h, i) => (
              <i key={i} className="her" style={{ height: `${h * 100}%` }} />
            ))}
          </span>
          <span className="gap">
            <span className="silence">
              <span className="word">silence · </span>
              {PAUSE_SECONDS.toFixed(1)} s
            </span>
          </span>
          <span className="tail">
            {HER.slice(26).map((h, i) => (
              <i key={i} className="her" style={{ height: `${h * 100}%` }} />
            ))}
          </span>
          <span className="gap short" />
        </span>
      </div>
      <div className="lane">
        <span className="speaker its">Kataribe</span>
        <span className="wave">
          {/* Silent through her pause, up to its limit. */}
          <span className="rest before" />
          <span className="gap">
            <span className="limit">max {PATIENCE_SECONDS} s</span>
          </span>
          <span className="rest" />
          <span className="reply">
            {ITS.map((h, i) => (
              <i key={i} className="its" style={{ height: `${h * 100}%` }} />
            ))}
          </span>
        </span>
      </div>
      <p className="pause">
        She stopped for {PAUSE_SECONDS} seconds to remember. It waits through up to{' '}
        {PATIENCE_SECONDS} seconds of silence before it speaks, so it let her finish.
      </p>
    </div>
  );
}

function Written() {
  return (
    <div className="pic written">
      <div className="lines">
        <p>
          <b className="her">Setsuko</b>
          <span lang="ja">
            主人の和夫さんとはね、郡上おどりで知り合ったんですよ。昭和四十年の夏。わたし、二十一でした。
          </span>
          <small>
            I met my husband Kazuo at the Gujo Odori, you see. The summer of Showa 40. I was
            twenty-one.
          </small>
        </p>
        <p>
          <b className="her">Setsuko</b>
          <span lang="ja">あの晩に踊ってたのは……そう、『かわさき』。</span>
          <small>What was being danced that night was… yes, ‘Kawasaki’.</small>
        </p>
      </div>
      <span className="becomes" aria-hidden>
        ↓
      </span>
      <div className="story-card">
        <p className="kicker">Marriage · Summer of Showa 40</p>
        <p className="title">Gujo Odori and Meeting Kazuo</p>
        <p className="retold">
          In the summer of Showa 40, when Setsuko was twenty-one, she met her husband Kazuo at the
          Gujo Odori. What they danced that night was ‘Kawasaki’.
        </p>
        <p className="quotes">
          <span lang="ja">
            「主人の和夫さんとはね、郡上おどりで知り合ったんですよ。昭和四十年の夏。わたし、二十一でした。」
          </span>
          <span lang="ja">「あの晩に踊ってたのは……そう、『かわさき』。」</span>
        </p>
      </div>
    </div>
  );
}

function Checked() {
  return (
    <div className="pic checked">
      <p className="pic-label">Session 1 · transcript</p>
      <p className="row">
        <span className="tm">0:18</span>
        <span>
          <span lang="ja">
            <mark>主人の和夫さんとはね、郡上おどりで知り合ったんですよ。昭和四十年の夏。わたし、二十一でした。</mark>
          </span>
          <span className="ok">✓ word for word · ✓ heard</span>
        </span>
      </p>
      <p className="row">
        <span className="tm">0:33</span>
        <span>
          <span lang="ja">
            <mark>あの晩に踊ってたのは……そう、『かわさき』。</mark>
          </span>
          <span className="ok">✓ word for word · ✓ heard</span>
        </span>
      </p>
      <p className="held">Had a clip said another name or year, its quote would have been dropped.</p>
    </div>
  );
}

function Shared() {
  return (
    <div className="pic shared">
      <ul className="decided">
        <li className="sent">
          Gujo Odori and Meeting Kazuo<small>✓ To her family</small>
        </li>
        <li className="sent">
          Jumping into the River from Shinbashi Bridge<small>✓ To her family</small>
        </li>
        <li className="kept">
          Nursing Kazuo and Saying Goodbye
          <small>
            <span className="lock" aria-hidden /> Kept between us
          </small>
        </li>
      </ul>
      <p className="gate">agreed aloud, checked in the recording</p>
      <div className="mini-cover">
        <p className="kicker">A life story</p>
        <p className="name">Ogawa Setsuko</p>
        <p className="toc">
          <span>1 · Childhood</span> Jumping into the River from Shinbashi Bridge
        </p>
        <p className="toc">
          <span>2 · Marriage</span> Gujo Odori and Meeting Kazuo
        </p>
      </div>
    </div>
  );
}

const STAGES: [string, boolean][] = [
  ['Childhood', true],
  ['School years', false],
  ['Work', false],
  ['Marriage', true],
  ['Raising children', false],
  ['Later years', false],
];

function Planned() {
  return (
    <div className="pic planned">
      <ul className="stages">
        {STAGES.map(([stage, told]) => (
          <li key={stage} className={told ? 'has-story' : ''}>
            {stage}
            <small>{told ? 'told' : 'not yet'}</small>
          </li>
        ))}
      </ul>
      <p className="next-h">Next time</p>
      <ol className="next">
        <li>
          <span className="tag family">From Yuka</span>
          Grandma, did you ever jump off the Shinbashi bridge?
        </li>
        <li>
          <span className="tag">Not told yet</span>
          What work did you do, after school?
        </li>
      </ol>
      <p className="never">
        <span className="lock" aria-hidden /> Never raised: Nursing Kazuo and Saying Goodbye
      </p>
    </div>
  );
}

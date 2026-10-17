import { useRef, useState, type KeyboardEvent } from 'react';

import './Who.css';

/** Who it's for, on the start page, after the opening: the person telling,
 *  their family, and next, their town, one at a time. It answers what a judge
 *  watching someone talk to a device wonders first, whether this stands in for
 *  the people around them: it is the reverse, a way for those people to know
 *  the person better and have more to ask. Chosen on 2026-10-17 from five
 *  prototypes, over a conversation drawn as arrows between her, Kataribe and
 *  her granddaughter, ending on a call Kataribe has no part in; an imagined
 *  week; a quiz on what you know of your grandmother's life; and rings of who
 *  hears the story, today and next.
 *
 *  Each audience's example is a line from the demo's family page, word for
 *  word, so it follows whoever the demo persona is and never quotes what
 *  nobody said. The town is marked Next: sharing beyond the family is not
 *  built. */

/** A line from the demo's family page, as said, with its English. */
export interface Line {
  said: string;
  /** Empty when there is no translation of it. */
  english: string;
  /** The story it is in, or for a question the story it led to. */
  story?: string;
}

export interface Lines {
  lang: string;
  told?: Line;
  asked?: Line & { by: string };
  remembered?: Line;
}

interface Example {
  line: Line;
  caption: string;
}

interface Audience {
  tab: string;
  who: string;
  line: string;
  next?: boolean;
  points: [string, string][];
  example: (lines: Lines, name: string, their: string) => Example | null;
}

const AUDIENCES: Audience[] = [
  {
    tab: 'For them',
    who: 'The person telling',
    line: 'A few minutes a day that are theirs, about their own life.',
    points: [
      [
        'Part of the day',
        'After breakfast, or whenever suits. The interviewer speaks first, so there is nothing to learn or set up.',
      ],
      [
        'Remembering, out loud',
        'One question at a time, with someone who waits while they search for a name or a year.',
      ],
      [
        'Sometimes, a question waiting',
        'A grandchild’s question opens the conversation, saying who asked.',
      ],
      [
        'Theirs to give',
        'Nothing reaches the family until they say so, and any story can be taken back later.',
      ],
    ],
    example: ({ told }, name) =>
      told ? { line: told, caption: told.story ? `${name}, in “${told.story}”` : name } : null,
  },
  {
    tab: 'For their family',
    who: 'Children and grandchildren, near or far',
    line: 'Find out who they were before you knew them, and you’ll have more to ask.',
    points: [
      [
        'The stories you never asked for',
        'Not for lack of love: there is rarely a moment, and it is hard to know where to start.',
      ],
      [
        'In their own words',
        'Each story retold to read, every quote word for word, with their voice behind it.',
      ],
      [
        'Something to talk about',
        'Read it on the train, then call. Or bring it up at Sunday lunch, and ask what happened next.',
      ],
      [
        'Or ask through the page',
        'Send a question: Kataribe asks it next time, and the answer appears under it.',
      ],
    ],
    example: ({ asked }, _name, their) =>
      asked
        ? {
            line: asked,
            caption: `${asked.by}, on ${their} family page${asked.story ? `. It led to “${asked.story}”.` : ''}`,
          }
        : null,
  },
  {
    tab: 'For their town',
    who: 'Friends, carers, a local archive',
    line: 'What a town lived through, kept in the voices of the people who lived it.',
    next: true,
    points: [
      [
        'Whoever they choose',
        'Next, the teller chooses who else may read: a friend, a care worker who knows them better for it, a local archive.',
      ],
      [
        'The oldest meaning of the word',
        'In Japan, 語り部 tell what they lived through, the war, the bombings, the disasters, so that it is not forgotten. Fewer are left each year.',
      ],
      [
        'Faithful enough to keep',
        'Every quote is checked against the recording, and the AI never adds a detail.',
      ],
    ],
    example: ({ remembered }, name) =>
      remembered
        ? {
            line: remembered,
            caption: `One telling among many: ${name}${remembered.story ? `, in “${remembered.story}”` : ''}`,
          }
        : null,
  },
];

export default function Who({
  name,
  pronouns,
  lines,
}: {
  name?: string;
  pronouns?: string;
  lines?: Lines;
}) {
  const [chosen, setChosen] = useState(0);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const audience = AUDIENCES[chosen];
  const their =
    { she: 'her', he: 'his', they: 'their' }[pronouns ?? ''] ?? (name ? `${name}’s` : 'their');
  const example = lines && name ? audience.example(lines, name, their) : null;

  // The tabs pattern, as Under the hood has it.
  const onKey = (event: KeyboardEvent) => {
    const to = {
      ArrowRight: (chosen + 1) % AUDIENCES.length,
      ArrowLeft: (chosen + AUDIENCES.length - 1) % AUDIENCES.length,
      Home: 0,
      End: AUDIENCES.length - 1,
    }[event.key];
    if (to === undefined) return;
    event.preventDefault();
    setChosen(to);
    tabs.current[to]?.focus();
  };

  return (
    <section className="who-for" aria-labelledby="who-title">
      <h2 id="who-title">Who it’s for</h2>
      <p className="note">
        Not a companion that stands in for anyone: a way for the people around them to know them
        better.
      </p>

      <div className="who-tabs" role="tablist" aria-label="Who it’s for" onKeyDown={onKey}>
        {AUDIENCES.map((a, i) => (
          <button
            key={a.tab}
            ref={(el) => {
              tabs.current[i] = el;
            }}
            id={`who-tab-${i}`}
            type="button"
            role="tab"
            aria-selected={i === chosen}
            aria-controls="who-panel"
            tabIndex={i === chosen ? 0 : -1}
            className={i === chosen ? 'on' : ''}
            onClick={() => setChosen(i)}
          >
            {a.tab}
            {a.next && (
              <span className="who-next" title="Not in this build">
                Next
              </span>
            )}
          </button>
        ))}
      </div>

      <div
        className={`who-panel${example ? ' with-example' : ''}`}
        id="who-panel"
        role="tabpanel"
        aria-labelledby={`who-tab-${chosen}`}
      >
        <div>
          <p className="who-audience">{audience.who}</p>
          <p className="who-line">{audience.line}</p>
          <dl className="who-points">
            {audience.points.map(([title, text]) => (
              <div key={title}>
                <dt>{title}</dt>
                <dd>{text}</dd>
              </div>
            ))}
          </dl>
        </div>
        {example && lines && (
          <figure className="who-example">
            <span className="kicker">From the demo</span>
            <blockquote>
              <p lang={lines.lang}>「{example.line.said}」</p>
              {example.line.english && <p className="en">{example.line.english}</p>}
            </blockquote>
            <figcaption>{example.caption}</figcaption>
          </figure>
        )}
      </div>
    </section>
  );
}

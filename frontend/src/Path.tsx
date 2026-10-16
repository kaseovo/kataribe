import { useEffect, useState } from 'react';

import { done as doneSoFar, go, onMarked, visitorId, type Place, type Step } from './pathSteps';
import './Path.css';

const OPEN_KEY = 'kataribe.path.open';

/** A judge's path through the site, in the corner of every page a stranger
 *  reaches from the start page, ticking itself off as they go: the demo, its
 *  family page and a family question, their own conversation, and their own
 *  page. Chosen on 2026-10-14 over a guided tour, often skipped, and the start
 *  page as numbered steps, which says least about the family page. The video's
 *  step shows before there is a video, its place waiting on the start page, so
 *  the path reads the same as it will; the family page's once there is one. */
export default function Path() {
  const [ticked, setTicked] = useState(doneSoFar);
  const [start, setStart] = useState<{ video: string; showcase: string | null } | null>(null);
  const onStart = window.location.pathname === '/';
  const [open, setOpen] = useState(() => {
    try {
      const kept = localStorage.getItem(OPEN_KEY);
      if (kept !== null) return kept === '1';
    } catch {
      // Below, as if never chosen.
    }
    return onStart && window.innerWidth > 900;
  });

  useEffect(() => onMarked(() => setTicked(doneSoFar())), []);
  useEffect(() => {
    fetch('/api/try')
      .then((r) => (r.ok ? r.json() : null))
      .then((found) => found && setStart(found))
      .catch(() => undefined);
  }, []);

  const toggle = (now: boolean) => {
    setOpen(now);
    try {
      localStorage.setItem(OPEN_KEY, now ? '1' : '0');
    } catch {
      // Remembered for as long as the page is open.
    }
  };

  if (!start) return null;
  const showcase = start.showcase;
  const visitor = visitorId();

  /** On the start page it is asked to take the reader there; elsewhere, the
   *  reader goes to the page it is on. */
  const to = (place: Place) => {
    if (onStart) return go(place);
    if (place === 'example') return window.location.assign(`/family/${showcase}`);
    if (place === 'questions') {
      if (window.location.pathname === `/family/${showcase}`) return go('questions');
      return window.location.assign(`/family/${showcase}#questions`);
    }
    window.location.assign(`/#${place}`);
  };

  const steps: { step: Step; title: string; time: string; act: () => void }[] = [
    { step: 'watch', title: 'Watch the demo', time: '2 min', act: () => to('watch') },
    ...(showcase
      ? [
          {
            step: 'read' as Step,
            title: 'Read a family page from our demo',
            time: '2 min',
            act: () => to('example'),
          },
          {
            step: 'asked' as Step,
            title: 'See a question the family asked',
            time: '30 s',
            act: () => to('questions'),
          },
        ]
      : []),
    {
      step: 'talk',
      title: 'Talk about your own life',
      time: '3 min',
      act: () => (visitor ? window.location.assign(`/talk/${visitor}`) : to('try')),
    },
    {
      step: 'own',
      title: 'Read your own family page',
      time: '1 min',
      act: () => (visitor ? window.location.assign(`/family/${visitor}`) : to('try')),
    },
  ];
  const count = steps.filter(({ step }) => ticked[step]).length;
  const all = count === steps.length;

  if (!open) {
    return (
      <button className="path-pill" onClick={() => toggle(true)}>
        <span className="path-long">{all ? 'Your path: done' : 'Your path'}</span>
        <span className="path-short">Path</span>
        <span className="path-tally">
          {count}/{steps.length}
        </span>
      </button>
    );
  }
  return (
    <aside className="path" aria-label="Your path through Kataribe">
      <div className="path-head">
        <div>
          <p className="path-title">Your path through Kataribe</p>
          <p className="path-count">
            {all ? 'All done. Thank you for trying it!' : `${count} of ${steps.length} done`}
          </p>
        </div>
        <button className="path-min" onClick={() => toggle(false)} aria-label="Make smaller">
          –
        </button>
      </div>
      <div className="path-bar">
        <span style={{ width: `${(count / steps.length) * 100}%` }} />
      </div>
      <ol>
        {steps.map(({ step, title, time, act }, i) => (
          <li key={step} className={ticked[step] ? 'done' : ''}>
            <span className="path-check" aria-hidden>
              {ticked[step] ? '✓' : i + 1}
            </span>
            <span className="path-step">
              {title}
              <small>{ticked[step] ? 'Done' : time}</small>
            </span>
            {!ticked[step] && (
              <button className="path-go" onClick={act}>
                Go <span aria-hidden>→</span>
              </button>
            )}
          </li>
        ))}
      </ol>
    </aside>
  );
}

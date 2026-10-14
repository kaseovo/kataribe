/** A stranger's path through the site, kept in their browser: what they have
 *  done of watching the demo, reading its family page, seeing a family
 *  question, talking, and reading their own page. The card that shows it is
 *  Path.tsx; the pages say when a step is done. */

export type Step = 'watch' | 'read' | 'asked' | 'talk' | 'own';

const KEY = 'kataribe.path';
const CHANGED = 'kataribe:path';
/** Where the start page is asked to take the reader: see Landing.tsx. */
export const GO = 'kataribe:go';
export type Place = 'watch' | 'example' | 'questions' | 'try';

export function done(): Partial<Record<Step, boolean>> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '{}');
  } catch {
    return {};
  }
}

export function mark(step: Step) {
  const was = done();
  if (was[step]) return;
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...was, [step]: true }));
  } catch {
    // A private window: the path is forgotten, which is all it costs.
  }
  window.dispatchEvent(new Event(CHANGED));
}

/** Calls back whenever a step is done, here or in another tab. */
export function onMarked(then: () => void) {
  window.addEventListener(CHANGED, then);
  window.addEventListener('storage', then);
  return () => {
    window.removeEventListener(CHANGED, then);
    window.removeEventListener('storage', then);
  };
}

export function go(place: Place) {
  window.dispatchEvent(new CustomEvent<Place>(GO, { detail: place }));
}

/** Whoever this browser started a conversation as, from the start page. */
export function visitorId(): string | null {
  try {
    const raw = localStorage.getItem('kataribe.visitor');
    return raw ? (JSON.parse(raw) as { id: string }).id : null;
  } catch {
    return null;
  }
}

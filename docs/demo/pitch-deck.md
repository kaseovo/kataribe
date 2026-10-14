# Pitch deck

Live deck: https://claude.ai/artifact/2LPwKqBnhN8Ey7o3u8EUQK

The deck itself is hosted (not exportable as static files), so this is the content in version-controlled form — edit here first for wording changes, then apply them on the live deck.

## 1. Cover

**Kataribe** — 語り部, the keeper of stories
A voice AI that talks with an elderly person for a few minutes a day, and turns their memories into a life story their family can read and hear.

Team Kataribe

## 2. Why this exists

Many seniors spend their days alone — and their families never find the time or courage to ask about their lives.

- **¥220,000** — to have a professional write a 自分史 (self-history), and it happens once.
- For the senior: memory work, a sense of purpose, and the knowledge their story will last.
- For the family: stories they never had time to ask about, and a reason to call and ask more.

## 3. The concept

A kataribe (語り部) is a traditional keeper of oral history — the person who remembers the stories and passes them to the next generation.

That is the job this does.

## 4. How it works

The device is only a channel. The product is the loop.

Session ends → Store audio + transcript → Extract stories, people, places → Update life timeline
Find gaps → Plan next questions → Back into the next session

## 5. Why it's different

- **Japanese, zero effort** — a voice conversation in natural Japanese, with nothing to install or type. Presence detection to auto-start it is on the roadmap, not in this build.
- **Faithful by design** — every passage links back to the real audio. The AI never speaks for the person and never invents a detail.
- **A family loop, not a companion** — relatives read new stories and send back questions the AI asks next time. A bridge between people, not a replacement for one.
- **Affordable** — a self-history for every family, not a one-off for the few.

## 6. Demo

*Placeholder — [demo recording](demo-script.md) not yet captured.*

## 7. Stack

| Part | Tech |
| --- | --- |
| Kiosk + family view | React, Vite, TypeScript; on-device face detection |
| Voice | Gemini Live API, native audio with built-in transcription |
| Backend | FastAPI (Python 3.13, uv) |
| Processing | Gemini text model — extraction, timeline, gap analysis, question planning |
| Storage | SQLite + local disk now; Firestore + Cloud Storage when deployed |

Offline checks (lint, types, unit tests) pass on every push. A live eval, run on demand, streams real Japanese audio at the Live API end to end.

## 8. Where we are

Prototype, built in the open over four weeks.

The interview loop works end to end: sessions save, stories extract, gaps get found, the next questions get planned — and the family reads only what was agreed to share.

語り部 — someone should remember, before no one can ask anymore.

*[Team Kataribe — contact / repo link]*

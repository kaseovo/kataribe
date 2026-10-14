# Roadmap

Built as vertical slices. Every slice ends with something you can run and show — never a half-wired layer waiting on the next one.

See [plan.md](plan.md) for the product thinking behind this.

## Decisions taken

| Decision | Choice | Why |
| --- | --- | --- |
| Gemini access | Developer API (key + ephemeral tokens) first | Gets a Japanese conversation running in week 1, before any GCP setup. The provider sits behind one adapter, so Vertex is a config swap when the data-residency story matters. |
| Storage | SQLite + local disk, behind a storage port | Zero cloud setup, fast tests, works offline. Firestore and Cloud Storage adapters land when we deploy. |
| Family loop | Family can suggest questions | Relatives submit a question, the AI weaves it into the next session, the answer comes back to them. This is the demo moment that separates us from a memoir app. |
| Repo layout | `backend/` (FastAPI, uv) + `frontend/` (Vite, React, TS) | One Vite app serves kiosk, family view and dev view on separate routes. |
| VAD patience | Tunable in the console, not hardcoded | Default 800 ms of silence ends a turn — far too short for someone retrieving a sixty-year-old memory. The right number is an empirical question about real speech, so we find it with a real speaker and bake in what wins. |
| Interviewer prompt | Full first draft, Japanese source with an English gloss | A test session with a toy prompt tells us nothing about whether the interview *feels* right. The Japanese file ships; the English one exists so the team can review changes and the dev view can show them. |
| Session recording | Stereo WAV built in the browser | Senior left, AI right, aligned on a shared timeline. Without it the first real session is unreviewable after the fact. |
| Token security | Config locked server-side into the ephemeral token | The interviewer persona is the product; the browser gets a token that cannot rewrite it. Tuning values are requested by the client but validated and locked by the backend. |
| Japanese review | With the demo take, Oct 14–15, by a native speaker on the team | Postponed on 2026-09-30, when nobody was free, and French stayed the working language meanwhile (see *French and English are for testing*). A native Japanese speaker joined the team on 2026-10-10; decided the same day that the review waits for the final part rather than coming ahead of it. |
| Judge access | A public start page; each judge talks to a persona of their own | Decided 2026-10-12. A judge who can hold a conversation themselves is stronger evidence than a video, and a shared persona would greet the second judge with the first one's memories. See *Judges try it themselves*. |

## Demo must-haves

These have to be working on camera. Everything else is cut first if week 4 gets tight.

- ~~Presence detection auto-invite~~ — **cut**, see below
- Per-story consent to share — the AI asks, the family view obeys ✅
- Cross-session memory — the AI opens by recalling last time and asking what it planned ✅

### Why presence detection was cut

It was a must-have from the first day and it no longer earns the place.

Browser face detection impresses nobody; the technically interesting work here is the brain, not MediaPipe. It is also the worst thing to put in front of a camera — lighting, angle and distance decide whether the one moment that is meant to look effortless works on the take.

And the plan's own risk table points elsewhere: the mitigation listed for *"seen as an AI companion"* is showing the family view and the call-her-and-ask-more moment. A judge watching a person talk to a device sees Cotomo. The family loop is what makes this not Cotomo, and that is slices 5 and 6.

The Talk button stays, and presence becomes a line in the pitch: today a button, tomorrow the device notices her. Nobody will dispute that it is buildable — which is exactly why building it wins little.

### Japanese validation is deferred, deliberately

Everything stays testable in French so the work is not blocked on a Japanese speaker being free. The cost is real and worth naming: the interviewer prompt now carries changes nobody has judged in the language that ships, and the naturalness change made that worse rather than better — the warmer reactions it produces are close to the restatements rule 3 forbids. This is a debt. From 2026-09-30 it had no due date; it is now due with the demo take on Oct 14–15, when a native speaker on the team settles the pause length and the voice, and judges every prompt change made in French since. Whatever that finds has to be fixed and retaken before the deadline.

## Judges try it themselves

Decided 2026-10-12, for the evaluation from Oct 19 to Nov 6. Judges get the video, a family page that is already full, and a conversation of their own. Until now the live URL asked a stranger for a password at its root, and no stranger could talk to anyone.

**The start page is `/`, and the console moves to `/console`.** It says what this is, offers *Try it*, links a showcase family page, the video and the repository, and says what happens to what they say.

**Redesigned on 2026-10-14, from three prototypes,** in the order a judge needs it: what it is, the loop in four steps, one story from the demo's family page shown in English, and then *Your turn*. The story opens with its first quote and shows every other one on a press, since its summary is a retelling and a judge should be able to check each thing in it against what was said, and hear it where there is a recording. The form is a name and *Start talking*; the family question is filled in already, behind a disclosure. The other two prototypes were two side-by-side doors, quickest for a judge who has already decided, and a guided tour, step by step, clearest but the most clicks.

**Each judge gets a persona of their own.** Memory is per person: with one shared persona the second judge would be greeted with the first judge's childhood, and asked the first judge's family questions. *Try it* asks for a name and a language and creates a visitor persona, remembered in that browser. The judge talks as themselves. A second conversation recalls the first, on their own words.

- Its id is 128 random bits, since the link is the only key, as a family page's link already is. Nothing public lists people.
- The family question is filled in already, and can be changed or cleared: from "Your family", which place from their childhood they still think about. The first conversation then opens with it. No past is invented for them: the interviewer would be recalling something they never said.
- English, and Japanese once the native-speaker review passes. French is for testing.

**Short conversations still end with the question about sharing.** A judge will talk for two minutes, and a closing cue at six would never come, so nothing would be shared and the family page would stay empty. For visitor personas:

- At two minutes the interviewer asks only whether they want to keep going or stop there. Keeping going carries on and is not asked again.
- Once they want to stop, because they said so or pressed *Finish*, it asks one thing, alone in its turn: may their family read today's story, named in a few words, or would they rather keep it private. Then a sentence of thanks and goodbye. A senior's close is unchanged: it is the one the native-speaker review judges.
- From then on the screen asks the same question, with *Share with my family* and *Keep it private*. Either ends the conversation, and the choice is applied once the story is written up. *Keep it private* has the last word even over a yes said aloud, since private is the safe way to be wrong; *Share* never overrides a no said aloud.
- *End now, choose later* ends it without choosing. If a story still has no answer, the end screen asks once, naming the stories, after they have been written up: let the family read them, or keep them private. Neither is private. A story they kept private in the conversation is not offered. A choice made on screen is recorded as one, apart from consent in their own words.

Decided 2026-10-13, after trying it as a judge would. At the three-minute cue the interviewer asked a question and closed in the same breath, and the question about sharing was lost in the middle of the goodbye: "…Do you recall any particular programs or movies you watched together? Thank you so much for sharing these memories today. May your family read these stories…? Next time, I would love to hear more about growing up and school. I look forward to hearing more another time." The reply was "So do you want to… make it private or not?" And the buttons to choose were never seen, since they came only on the end screen, only for a story with no answer. The same trial also opened its first conversation with "so good to see you again"; the trial rules say a first conversation is a first.

Measured once each way on live audio, with the check-in brought forward to 30 seconds: asked to go on or stop, "I think I'm done for today" got "Before we stop: may your family read what you told me about your childhood in Brittany and your grandfather's boat, or would you rather keep it private?", and "Yes, my family can read it" a one-line goodbye and the story on their family page, from the words said. "I'd like to keep going a little" got "What kind of fish did you and your grandfather usually catch?". The buttons have a browser test of their own.

**The end screen waits for the writing-up,** then links to their family page. The family page says when a conversation is still being written up.

**The showcase family page is read-only.** It holds stories from the demo take and one family question already answered. Questions sent from it would wait forever, and every judge would read the others'.

**Limits and money.** At most 30 visitor conversations a day across all visitors, about $0.10 each, so the worst case over the evaluation is under $60 and the likely one a few dollars. The Gemini key moves to the paid tier (the Cloud trial credit does not cover Gemini), and the nightly eval gets a key of its own so testing cannot use up what judges need. One instance stays warm until Nov 6: a cold start measured 4.6 s, of which the app's own imports are under a second, and startup CPU boost was already on.

**Watching it.** An uptime check on `/api/health`, Error Reporting by email, a budget alert, and `make smoke` by hand every morning, since a health check cannot see a broken key.

**Frozen after submission.** The submitted commit is tagged and deployed; `main` stays as submitted until Nov 6. Only an outage is fixed, and each fix is noted in the README.

**Their data.** The start page says that the conversation is recorded and processed by Gemini, that the family page shows only what they agree to share while the team can see everything, and when it is deleted: every visitor persona goes on Nov 7, unless the project is shortlisted.

**Only an answer settles the question.** Decided 2026-10-12. Extraction used to count a story as asked "whatever the answer", so a judge who pressed *End now* while the interviewer was asking left it private, never offered again, and their family page empty; a senior whose conversation ended on the question was never asked again either. Now a question with no reply leaves the story to be asked again: at the next close, or on a visitor's end screen. Yes, no and hesitation are answers, and stand. For a story from an earlier conversation asked about again, no reply is no decision rather than a decline. The screen and the start page still say to answer aloud first.

This changed the extraction prompt, whose consent cases were measured 12 of 12 and 12 of 12. `tests/live/test_consent.py` gains four cases (no reply asked again, a no and a hesitation not asked again, an earlier story with no reply left waiting). Measured on 2026-10-13, once the credits were topped up: all twelve, three runs, 36 of 36.

**Built on 2026-10-12, and what is not yet proven.** Offline checks pass. The visitor's whole path has a browser test (`e2e/visitor.spec.ts`) and a smoke test against the live service, and neither has passed yet: the Gemini key's prepaid credits ran out the same day, and every live connection was refused. That showed one fault, now fixed: a connection refused after opening left the screen on "Connecting…" forever, since the SDK's connect never settles; it now fails at once, or after 20 seconds, with the screen's "not possible just now". Audio capture was probed in Chromium and WebKit, where it works; Firefox would not start in the sandbox, so capture now falls back to the device's own rate if a browser refuses a microphone in a 16 kHz context, which is Firefox's known refusal. Firefox, Safari with a real microphone, and phones are still to be tried by hand.

**Run against the real API on 2026-10-13.** The visitor's browser test passes, from the start page to a quote on their own family page. It first failed on how it spoke, not on what it tested: the recording standing in for the microphone started the moment the microphone opened, which is the moment the greeting starts, and those words were lost. The interviewer finished its greeting and waited for an answer that had been given. Started a second into the greeting, the same words interrupted it and were answered; started after it, they were answered. A judge hears the greeting before answering it, so the visitor test and the smoke test now answer after it. Words said at the very instant the greeting starts can still be lost, seen once; a person would hear its question and answer it. It then failed once on its own check: the interviewer asked "What was the water like in the early morning?", a good question that named none of the words the test looked for, so it now accepts the plain words for them as well (`HEARD_EN`). Every browser test passes, the visitor's three runs in three since. Deployed the same day as revision `kataribe-00007`, and `make smoke` passed 3 of 3 on the live service, a judge's whole path included. The six-minute session test passed. Of the live API suite, one check failed once in two runs: told to cut in after 400 ms of silence, the interviewer said nothing at all through a 13 second memory. It is the control for the patience test, and passed on the rerun.

## Slices

| # | Slice | What you can show at the end | Week |
| --- | --- | --- | --- |
| 0 | Walking skeleton | `make dev` runs API and web together; CI green | 1 |
| 1 | It talks | A Japanese voice conversation with Gemini Live in the browser, transcripts on screen | 1 |
| 2 | It remembers the session | Audio and transcripts saved and replayable from a session list | 1 |
| 3 | It has a brain | Stories extracted onto a timeline; gaps found; next questions planned; the AI opens session two by recalling session one | 2 |
| 4 | It notices you | Kiosk mode, presence detection, daily invitation, backing off, big Talk fallback | 3 |
| 5 | It asks permission | Consent requested per story in conversation; family view shows only what was shared, with audio | 3 |
| 6 | The family asks back | Relatives submit questions; the AI asks them next session; answers surface in the family view | 4 |
| 7 | Ready to judge | English dev view, deployed, demo video with subtitles, pitch deck | 4 |

## Schedule

Prototype deadline **2026-10-18**. A real senior tests from week 2.

| Week | Dates | Slices |
| --- | --- | --- |
| 1 | Sep 22–28 | 0, 1, 2 |
| 2 | Sep 29–Oct 5 | 3, plus the first session with a real senior |
| 3 | Oct 6–12 | 4, 5 |
| 4 | Oct 13–18 | 6, 7, second real-senior test, demo video |

## Status

- [x] **0 — Walking skeleton**
- [~] **1 — It talks** — built; the live test with a Japanese speaker is with the demo take on Oct 14–15, see *Japanese validation is deferred*
- [x] **2 — It remembers the session** — sessions, transcripts and audio stored and replayable
- [x] **3 — It has a brain** — stories extracted and verified, timeline, gaps, next questions, context carried into the following session
- [~] 4 — It notices you — **cut from the hackathon**, see below
- [x] **5 — It asks permission** — consent asked in conversation, evidenced by the person's own words; family view shows only shared stories, with audio
- [x] **6 — The family asks back** — relatives send questions from the family page; the interviewer opens with one, saying who asked; the answer links back to the story, if she shared it
- [~] **7 — Ready to judge** — deployed on Cloud Run in Tokyo, with Firestore and Cloud Storage, and checked end to end by `make smoke` (see [deploy.md](deploy.md)); the senior's own screen is at `/talk/{senior_id}`; the start page and visitor personas for judges went live on 2026-10-13, and `make smoke` takes a judge's whole path on the live service (see *Judges try it themselves*); still to do are the demo video, the showcase family page from the demo take, the deck's slide for the video, and monitoring

## Running the week-1 test

```bash
make dev          # API on :8000, console on :5173
```

Open <http://localhost:5173> in Chrome, then **hard-reload** (Cmd-Shift-R). The audio worklet is served from `public/` and browsers cache it across restarts.

### Pre-flight, on your own, before anyone else is in the room

Press **Start conversation**, allow the microphone, say anything for ten seconds, and watch the browser console:

```
[kataribe] mic 16000 Hz -> 16000 Hz
[kataribe] sent 5.0s, peak 34%
```

- **`peak 0%`** means the microphone is delivering silence. Nothing else will work; fix the input device first.
- **`peak 99%`** every time means it is clipping. Move back from the mic.
- **Anything about "Closed 1007"** means the session is being rejected. Stop and report it rather than continuing.

Do not spend a native speaker's time until this reads sensibly and Japanese words appear in the transcript.

### The session itself

Pick a voice, set the pause slider, press **Start conversation**. Changing a tuning value starts a fresh session, because the values are locked into the token when it is minted — so work in short runs rather than one long one.

What the tester is judging — a native Japanese speaker, not necessarily elderly:

1. **Does it interrupt?** Pause mid-sentence for two or three seconds, as if retrieving a memory. Raise the slider until the interviewer waits. That number is the main output of this test. Measured against synthesized speech, for a starting point:

   | Patience | Pause | Result |
   | --- | --- | --- |
   | 3500 ms | 1.5 s | waited |
   | 3500 ms | 2.5 s | **cut in** |
   | 6000 ms | 2.5 s | waited |
   | 6000 ms | 4.0 s | waited |

   The gap the model sees is longer than the pause itself, so budget roughly double. The default is now 5000 ms and the slider reaches 8000 ms.
2. **Does it stay in Japanese?** It should never drift to English, even after a long silence.
3. **Is the transcription good enough to build stories from?** Names and place names especially — those become the timeline in slice 3.
4. **Does the interviewer behave?** One question at a time, short turns, follows a change of subject, backs off when told to, closes warmly with a topic for next time.
5. **Which voice?** Seven are shortlisted. Pick by ear.

Download the recording afterwards — senior on the left channel, interviewer on the right.

### Replaying a session

The console takes a downloaded recording in place of the microphone, so a prompt edit or a new slider value can be tried against the same words rather than asking someone to sit down again. Only the left channel is sent, so the interviewer never hears its own previous answers.

It is the fastest way to iterate, and the only way to compare two prompts on identical input. It does not replace a live session: a replay cannot react, so it tells you nothing about interruption or turn-taking.

A recording worth keeping belongs in `backend/tests/live/recordings/`, where `make eval` will replay it as a fixture — that is how this suite stops being graded on synthesized speech.

### Slice 1 is done when

- [ ] A five-minute Japanese conversation runs with no disconnect
- [ ] The interviewer does not talk over a three-second pause for thought, at a known slider value
- [ ] It never drifts out of Japanese
- [ ] A native speaker says the transcript matches what was actually said, names and places included
- [ ] A voice is chosen
- [ ] The recording downloads and plays back as a conversation

Write the slider value and the voice into the defaults once they are known: `InterviewTuning` in `backend/src/kataribe/gemini.py`.

### Sparring with a simulated interviewee

`make spar` puts the interviewer in a live conversation with an AI playing the person being interviewed, so timing can be worked on without asking anyone to sit down. Both sides are real audio, so pauses, barge-in and turn-taking are genuine.

```bash
make spar                                    # 田中ハル, the default
make spar PERSONA=shigeru SECONDS=90         # a longer session
make spar PERSONA=kimiko PATIENCE=2500       # sweep the slider
```

Three personas, each pressing a different rule:

| Persona | Exercises |
| --- | --- |
| `haru` | Pauses two or three seconds mid-memory — the interviewer must not fill them |
| `shigeru` | Refuses to discuss the war — the interviewer must drop it |
| `kimiko` | Drifts to another subject — the interviewer must follow rather than steer back |

Each prints who spoke when, flags any moment the interviewer talked over the other side, and saves a stereo recording under `backend/var/spar/`. Their biographies are fixed, so once stories are being extracted the extraction can be graded against facts we already know.

#### Why sessions used to die after two minutes

Worth recording, because it was nearly missed and it bears on the 5–10 minute sessions the product needs.

Sparring sessions kept dying around 70–130 seconds with `1011 keepalive ping timeout`. It looked like a quirk of the test harness. It was not: the same thing killed the interviewer's own session at 130s, and no test had ever run long enough to notice, since every one of them finished inside a minute.

The cause was ours. The SDK hands the Python websockets library its default 20 second ping timeout, and the Live API does not reliably pong inside that window, so a healthy connection was being hung up on by our own client. The server was never asking us to leave — it sent no `go_away` at any point. With the timeout disabled, one connection ran 391 seconds.

Two things follow:

- Harness clients are built through `tests/live/connection.py`, which turns the ping timeout off.
- The browser does its own keepalive and exposes no such setting, so the product path was never affected by this particular cause. Confirmed rather than assumed: a browser session ran a full six minutes with 34 transcript entries and no drop. `pnpm test:endurance` keeps it that way, nightly.

Session resumption was also verified to work — `SessionResumptionConfig`, a handle on every `session_resumption_update`, and a reconnect that carries the conversation across. It is not needed for this cause, but it is the documented answer for a genuine server-side drop and the mechanism is proven should a long session need it.

### What `make eval` already checks for you

Before spending anyone's time, `make eval` streams synthesized Japanese at the real API and asserts the transcript is accurate, the interviewer waits through a pause, cuts in when patience is lowered, replies in Japanese asking one thing, backs off when a topic is refused, and that the whole loop works in a real browser.

It leaves exactly one thing it cannot judge, which is the point of the human session: **whether the Japanese is good.** A native speaker has not yet reviewed `interviewer_ja.md`, and one known issue is already marked `xfail` — the interviewer sometimes recaps what it heard before asking, which its own prompt forbids. Whether that reads as natural aizuchi or as presumptuous is a call only a native speaker can make.

## Linking a quote to its audio needs a separate pass

Slice 5 shows every passage with the senior's own voice behind it, which needs to know where in the recording each phrase sits.

The Live API takes `word_timestamp` on its transcription config and then ignores it: the transcription comes back with text and an empty `words` list, on a raw key as well as through an ephemeral token, with and without `VERBATIM` mode. It is still requested, so offsets arrive free if that changes, but nothing may be built on it.

Stored turns carry a `started_at`, and it is honest about what it is: the moment the transcript *arrived*, which is when the turn ended. In a thirteen second session both turns were stamped at 0:12 and 0:13. Useful for ordering, useless for seeking.

So slice 5 needs the offsets from somewhere else — most likely a transcription pass over the stored recording during slice 3's processing, which would also be a second opinion on accuracy. `gemini-3.5-transcribe-live` is the obvious candidate to try first.

## French and English are for testing, not for shipping

The product is Japanese. French and English exist so the whole loop can be exercised without a Japanese speaker in the room: pick a language when creating a person, and the interview, the extraction and the planning all run in it.

**What a green run in French tells you.** Turn-taking and interruption, whether it follows a change of subject, whether it backs off when refused, whether it invents details, whether it over-recaps, and that extraction, gaps, planning and cross-session memory work. That is most of the behaviour, and it can be judged by anyone who speaks the language.

**What it does not tell you.** Honorific register has no French equivalent, and the kanji homophones that make a name come back misspelled do not exist outside Japanese — the defect does not get fixed there, it simply cannot occur. Neither does it say whether the Japanese sounds warm or stiff to a Japanese ear.

So "it works in French" must never be read as "it works". The Japanese session with a native speaker is still the one that decides.

**Settings are per language** for the same reason. Each language keeps its own voice and pause length, and only the Japanese pause figure was measured against real speech — the others are starting guesses, and the console says so when one is selected. A value that feels right in a French test cannot become the one an elderly Japanese speaker gets.

The extraction and planning instructions are written once, in English, and told which language to write in. Three translated copies would drift apart, and the rules they carry — do not invent, do not paraphrase inside a quotation — are the same in any language. The Japanese live tests were run before and after that change to confirm the Japanese behaviour did not move.

## Summaries in sentences, and English beside the Japanese

Both decided 2026-10-13, after trying it as a judge would.

**A summary is written, not stitched.** The rule was that the title and summary use the speaker's own words, and the model took it to the letter: "Childhood house lived in from birth until 11 years old, smaller than the one got after it, with a swimming pool." In Japanese a summary came back as the quote itself, in the first person. The rule now says what it meant: no fact, feeling or judgement they did not give, and their word for each thing, but in plain sentences about them, by name, with grammar where theirs faltered. Never "I", since the AI does not speak for them, and never "he" or "she", since nothing says which. The same conversation now gives "Alex grew up in a small town by the sea in Brittany. Alex's grandfather had a boat, and every summer he took Alex out fishing at dawn." A live test feeds it halting speech and judges both halves: 3 of 3 on the first wording, then 2 of 3 once the rule also allowed fixing faltering grammar, the third ending "…around eight people, swimming by day and night, and watching TV on Friday night", which the judge took for phrases strung together. A later failure showed why the phrases stuck: "smaller than the one got after it", from "the one we got after it". Barred from guessing a pronoun, the model dropped the "we" and kept the rest. The rule now says their names for things are kept and their verbs and grammar are not, and that a "we" nobody identified is rephrased away ("There was a dog called Pip"). 3 of 3 since; samples still turn up "the one obtained afterwards" now and then, which reads stiffly but is grammatical. The test that summaries add nothing, and the one that the recap adds nothing, failed at first on her name: it comes from her profile, which extraction is given and the judges were not. Given the profile too, 3 of 3 each. The consent cases, rerun on the new prompt: 36 of 36 over three runs.

For the native speaker: the Japanese summaries moved from です/ます to だ/である, and her 「やっておりました」 came back as 営んでおり.

**A family page in another language comes with English.** The showcase page will be Japanese, and judges may not read it. Under each title, summary, quote, family question, name and place, a grey line of English, and a note at the top saying they are translations made by AI and that the quotes are the person's own words, with their voice behind the play button. Never in place of the original.

- Translated once, the first time the page shows a text, and kept per person, so forgetting them removes it too. Only what the page shows goes to be translated: never a private story.
- Read after the page rather than with it. The first version put it in the page's own request, and a page opened blank for over five seconds while the English was written; the browser tests caught it. Now the page appears at once and the English follows.
- Translated as said: names in the Latin alphabet, family name first, and nothing made more precise than the original. The live test caught the prompt's own example teaching it to guess: 孫のゆか was "granddaughter Yuka", where 孫 is a grandchild. 3 of 3 since.

**Every fact in a summary has a quote behind it.** On the example page "it was snowing" had no quote, and a judge would wonder whether it was said. The gap was in the made-up example, written by hand with two quotes; the real extraction, given the same conversation, quoted all three answers, the snow included. The rule is written down all the same, since it is what the page promises: everything the summary says is found in a quote, in the order said, none twice. A live test of a wedding told over three answers passes on the old rule and the new, 3 of 3 each, so it guards the promise rather than proving the change. The consent cases, rerun: 12 of 12.

**One language at a time.** With English under every passage the page read twice. Now titles, summaries, names, places and questions are in one language, and only a quote keeps both: the words as said, which is what the play button plays, with the English beneath. A switch at the top changes language; until it is used the page follows the reader's browser, so a judge reads English and a Japanese family reads the words as told, with no English at all.

**Asked, not guessed: how English refers to someone.** Told never to guess "he" or "she" from a name, the translation wrote "Father ran a small weaving mill", then, told to give the word an owner, "Their father's weaving workshop", which reads oddly in a memoir. A person's profile now says how to refer to them, she, he or they, as whoever entered them said, in the console. Unset, as for a visitor, English uses their name and no pronoun: "Haru's father". Summaries follow the same rule. Live tests: a summary with no pronoun given uses none, 3 of 3; with "she" given, "her", 3 of 3; the translation test, its lines now labelled for the judge, who took a title for her own words, 3 of 3.

**Read as a book.** Chosen on 2026-10-14 from prototypes: a timeline, a scrapbook, and four books (on screen, on paper, page by page, an open spread). The page is a cover, contents by life stage, and chapters to read through. Each story is its text; its quotes are behind one button, "All 3 quotes in Haru's own words, with their voice", for whoever wants to check the retelling or hear it said. Each quote has its own player, play, progress and length, greyed with "No recording" where there is none, as on a page made up for a demo.

**Asking from anywhere in the book.** Chosen on 2026-10-14 from four layouts: tabs, contents in a side column, a sticky bar, and this. The page is only the book; a button in the corner, "Ask Tanaka Haru a question" with the number of questions sent, opens a panel from the right: the questions already sent first, stamped, then the form. Asking sits beside the story that made someone want to ask, rather than at the end of the book.

**Asking, in two steps.** Chosen on 2026-10-14 from prototypes. A relative says who they are first, by group (grandchildren, children, partner, brothers and sisters, in-laws, wider family, friends and others) and then exactly, with Other for anything not there, then their first name; then the question. A line shows how it will be heard: "Your daughter-in-law Aiko would love to know: …". It replaces one box asking for "relation and name", which nobody would fill in as the interviewer needs it. Questions sent are listed beneath, each stamped Answered, with a link to the answer, or Waiting. The other forms tried were a letter, a message box, suggestions from the life stages not yet told, and relation buttons of other kinds: fixed, from the profile's family, or more of them. Who is asking may now be 60 characters, for a relation and a first name.

**All they said.** Under each quote, *All they said* opens the whole answer it was taken from, with the quoted words marked, so a reader can check a quote against what was said. That is exactly what the play button plays, and nothing more: not the interviewer's question before it, since a question can name what they refused to talk about.

## Consent is evidence, not inference

A story reaches the family only when the person agreed and the agreement survives as their own words. Extraction is asked for the words they used to agree; `verify` then checks them against the transcript exactly as it checks quotes. No words, or words that are not in the transcript, and the story stays private. Stories are private by default, and a missing, declined, hesitant or unclear answer all leave them there.

Measured against the real model, three runs each: a clear yes shared it, and a no, a hesitation (「うーん、そうですねえ……どうしましょうかねえ」) and never being asked all kept it private — 12 of 12.

The family page is `/family/{senior_id}`. Filtering happens in the query, so there is no route by which a private story arrives and is merely not rendered; a browser test checks that not a word of one reaches the page. Private stories do not appear at all, not even as a count: until 2026-10-14 the page said "One story has been kept private", which invites asking what it was. A family question she declined is treated the same way, looking exactly like one still waiting.

There is deliberately no endpoint that writes stories. The browser tests seed the store through `backend/seed_story.py`, which uses the same code as the processing pipeline, rather than through a test-only route into the one part of the API whose job is to keep things out.

Each quote has a play button, and it plays a clip, never the session. The whole recording holds every story told in it, private ones included, so the family page is not told where it is. The server cuts the turn the quote came from out of the left channel, where only she speaks, and serves it only for a shared story. Word-level offsets are not returned by the model, so the clip runs from the interviewer's turn before to the one after, with the silence trimmed off: her whole answer, not just the quoted words.

The session list in the console still plays whole recordings. That is the team's view; it must not be reachable from a public URL.

The family page's own words follow the language it is read in: English when the reader chooses English, Japanese throughout otherwise, from 目次 and 第1章 to the question panel, where a relative is named the way the interviewer says it, 孫のゆか. Done on 2026-10-14; until then the page's labels were English over Japanese stories. Its Japanese is still to be reviewed by a native speaker.

## Asked once, at the close, and taken back at any time

The consent check held; the asking did not. The interviewer was told to ask after a story had been heard through, at most once a conversation. In a six-minute sparring session on 2026-10-10 the moment never came: it asked nothing, so both stories stayed private and the family would have received nothing. And the senior's own screen has a finish button, which can end a conversation before any close at all.

So the question moved, and the bookkeeping grew to match:

- **One question, at the close.** The interviewer names today's stories in a few words and asks whether the family may read them, and whether there is one to keep. One yes covers every story it names; a story kept out stays private. Nothing is asked in the middle of a memory.
- **A painful story is asked about on its own,** worded so that keeping it is the easy answer: 「ご主人のお話は、ここだけのお話にしておきましょうか」. Closing because they are upset skips the question entirely.
- **A story never asked about waits.** Extraction records whether each story was asked about and answered (`asked_to_share`). One that was not, because the session ended early, because of distress, because the question got no reply, or because the yes could not be evidenced, goes to the next conversation's close: the latest three, so the question stays one question. A story they answered about and kept private is never offered again; that was the answer. A hesitation is an answer too: asking again someone who already hesitated would be pressing them.
- **Taking a story back works from any later conversation.** 「あの話は家族に見せないで」 makes it private when that session is processed. It needs no evidence, since the safe direction is private, and the interviewer agrees at once without asking why.

Measured against the real model, three runs each: one yes at the close shared both stories it named; 「工場の話はいいですよ。でも川の話は、私だけのことにしておいてください」 shared the factory and kept the river; a story from last time was taken back; a story never asked about was agreed to at the next close. 12 of 12, alongside the original four consent cases, still 12 of 12.

The same seven-and-a-half-minute sparring session, rerun with the new prompt on 2026-10-11: the interviewer closed by naming the three things it had heard and asking, she agreed, and both stories were shared on her words. One run, and three things came with it, all open:

- It closed about a third of the way in, well short of five minutes, without being asked to.
- It then traded goodbyes with the simulated interviewee for the rest of the session. Partly the harness, since the persona cannot hang up, but nothing tells the interviewer to stop once it has said goodbye.
- The marriage story, which ends on her husband's death ten years ago, went into the general question rather than being asked about on its own. Told warmly, so arguably not a painful story; a judgement for the native-speaker review.

The first two have a fix in place, not yet measured. The model keeps no clock, so the screen now says when: after `KATARIBE_CLOSE_AFTER_SECONDS` (six minutes) it sends a closing cue, a stage direction like the opening one, and the prompt closes only on that cue or when the person wants to stop, waits for a pause in their story, and answers a further goodbye with a word or two. Finishing before the cue still works; the stories are asked about next time. `make spar CLOSE=240` sends the cue in a sparring session.

Measured once, cue at four minutes of six and a half: it did not close before the cue, and on the cue it thanked her, named both stories, asked whether the family may read them and whether one should stay hers, and proposed next time's topic, all in one turn. She agreed and both were shared on her words. The goodbyes after it got shorter but did not stop; with a persona that cannot hang up that is partly the harness, and a person would press finish.

It also showed what closing early had been hiding. From the eighth turn to the cue the interviewer asked nothing: seven turns in a row of praise alone (「素敵ですね」「尊いものですね」), and two stories in six and a half minutes.

The rule that let a turn end without a question had no limit, and the prompt never said what to do when a story runs out. Now it says both: never two acknowledgement-only turns in a row; no stacked praise, which reads as judging a life rather than hearing it; and when a story has come to rest, the same feeling repeated and nothing new coming, ask one concrete thing around it: another scene from that time, a person who came up in it, what came before or after. Always from the last thing she said.

The first version said to move on with a question from today's planned list, or from a period not yet told. It ended the stall and broke something else: following a change of subject passed 1 run in 3, against 3 in 3 on the prompt before it. Twice the interviewer acknowledged her drift to the cat and went back to the cosmetics counter; once it turned "the neighbour's dog wants its walk" into "walks with your family as a child?". A list of subjects of its own was a reason to steer. Anchored to her last words instead, it passes 3 in 3.

Measuring that took a fix to the test. A session that runs out of time on her turn handed the judge a drift the interviewer never had the chance to answer, and the judge failed the reply before it. The script now stops at the interviewer's last turn (`script(through_last_reply=True)`).

The sparring session with the anchored rule: a question every turn before the cue, each built on the last answer, and the story went from the factory to its cloth, to the old women who hung it in their doorways against the winter, to the pouch they sewed her from the scraps, to the white pebble she kept in it. 64% of her words came back as quotes, against 30% before. The cue arrived just after a question, and the interviewer asked for the answer before it closed: 「お話の途中ですが、そろそろお開きの時間となりました。巾着の宝物について、最後にお聞かせいただけますか」.

Still open, both small: the goodbyes trail on, six turns against a persona that cannot hang up; and it says aloud that it is time to close, which is a paraphrase of the note rather than the note, and reads naturally.

## Quotes are checked against the recording, not only the transcript

The word-for-word check compares a quote with the transcript, and the transcript can be wrong. A quote copied from a wrong transcript is found in it all the same. The same sparring session produced 「みんなで食卓를囲んでいるときが一番です」: a Korean particle in the middle of Japanese, and it passed.

Two guards now sit after it:

- **Script check.** A quote, or a yes, holding a character its language is never written in is held back. Each language carries its alphabet (`languages.py`): kana, kanji, Japanese punctuation and ASCII for Japanese; Latin for French and English.
- **The recording's own say.** Every quote that survives, and every yes, is played to Gemini Flash as the clip the family would hear for it, with the words it claims. Spelling is not judged, so 十八 and 18 are the same words; a different name, place or number is not. A quote that fails is dropped. A yes that fails leaves the story private and still to be asked about. Several clips go in one request, batched under the API's size limit; a clip too long to send is held back, not waved through.

Measured against synthesized speech, three runs each: the words said were confirmed, the same words written with figures were confirmed, a changed place (長野 to 新潟) was caught, and three clips in one request were each judged on their own. 12 of 12.

It has since caught a real transcription fault, unprompted. In the console's browser test on 2026-10-13 the Live API wrote the sample's 「私は昭和22年に」 as 「私を昭和22年に」, twice in two runs; the recording check heard 私は and held the quote back, and the story reached the console with no quote at all. Correct, and it broke the test, which expected one: the sample now leaves out 私は.

What it cannot do: tell homophone kanji apart. 佐藤繁 and 佐藤茂 sound the same, so listening settles nothing; that remains the profile's job, and the family's. It does not give word timings either, so clips still run turn to turn (see *Linking a quote to its audio needs a separate pass*). And a session without a recording is not checked against one; there is no clip to play for it either, and processing logs it.

## The family asks back

A relative opens the family page, writes who they are and what they want to know, and sends it. The next session opens with it — after a word about last time:

> こんにちは、田中ハルさん。前回伺ったお父様の織物の工場のお話を、今もよく覚えています。今日はお孫さんのゆかさんが、結婚式のときのお着物のことを知りたがっていらっしゃいましたよ。どんなお着物でしたか?

Afterwards, extraction reports which family questions were put to her and which stories hold the answer. The family page shows the question as asked, and her answer beneath it.

**Who is asking is the point.** The interviewer always says who the question is from. That her granddaughter is thinking about her matters more than the kimono does, so the form asks for the relation as well as the name (孫のゆか, not ゆか).

**It is asked in the opening line.** The first prompt said to ask "when the conversation allows" and that it could wait. Given the choice of topic, the interviewer ignored it and asked about memorable experiences in general. Making the family question the one topic the opening proposes fixed that — and then pushed the recall of last time out of the opening in 3 runs of 3, which is a demo must-have. The opening now has an order: a word about last time, then the family question. 6 of 6 since, three first sessions and three second ones.

**At most two per session, oldest first.** A session is five to ten minutes and it is her story, not a queue to get through. The session records which questions it carried, and only those are judged afterwards: a question sent while she was talking never reached the interviewer, and "asked" must mean the interviewer asked it.

**Nothing she refused is asked, even by family.** Relatives do not know what she has declined to talk about. Each question is screened against the avoid list before it is stored, and everything still waiting is screened again whenever she refuses something new. If screening cannot run, the question is not taken at all rather than stored unchecked. A question that is held back looks exactly like one still waiting, since saying anything else would tell them what she refused. One leak remains: a question that stays waiting while newer ones get asked says something by its silence.

**The answer is linked, not copied.** A question points at the stories that answer it, and the family page shows only those that are shared. If she answered and kept it private, the relative sees "asked, no reply has been shared" — which is also exactly what they see if she declined. They learn that it was asked and nothing about what she said.

Measured against the real models, three runs each: screening held a question about the war and one about evacuation — the obvious road there — and passed the kimono and the first salary, 3 of 3. Extraction reported an answered question with its answer, a question never put as not raised even when she talked about the same subject unprompted, and one she let pass as raised with no answer: 9 of 9.

For the native speaker, two things from these runs. 「とても心に残っております」 in a recall is an impression of the kind the planning prompt forbids; whether it is warm or presumptuous is theirs to say. And one opening came out as 「知りたがるといらっしゃいました」, which is not Japanese — it is not yet known whether that was the voice or the transcript.

**Not done:**

- Correcting the spelling of names. The page is where a relative could fix 佐藤繁 to 佐藤茂 in one tap, as proposed below; it has not been built.
- Telling the family when an answer lands. They have to come back and look.

## The interviewer speaks first

Nobody should have to work out that they are meant to start, least of all someone sitting in front of a device they did not ask for. When a session opens, a short stage direction is sent — "they have just sat down, speak to them gently" — and the interviewer greets them. It is never spoken aloud and never reaches the transcript.

**It has to be sent as realtime input, not as client content.** A `sendClientContent` turn produces a perfectly good greeting and then leaves the session deaf: it stops answering the audio that follows, and sometimes closes outright with 1006. `sendRealtimeInput({ text })` greets just as well and the conversation continues normally.

This was already known and forgotten. The sparring harness carries a comment saying that seeding the interviewee with client content left it answering once and then silent — and the same mechanism was then used in the product, where it broke two browser tests before anyone noticed.

Worth recording alongside it: an earlier finding that client content returns 1007 on a locked token was wrong. That was `enable_affective_dialog`, which was set at the time. A capability was written off on the strength of a test polluted by a different bug.

## Making it sound like a conversation

The first French session was reported as stiff, slow, and relentlessly interrogative. A sparring run showed exactly that — four turns, every one of them the same shape:

> そうでしたか。…もう少しお聞かせいただけますか。
> そうですか。…どんなお料理にされるのですか。
> そうでしたか。…もう少し伺ってもよいですか。
> そうでしたか。…どんな料理に使われたのですか。

Acknowledge, then ask. Every time, with the same acknowledgement. The prompt told it to keep acknowledgements short but never said a turn was *allowed* to be only an acknowledgement, so it always asked.

Three changes, in all three languages: a turn may end without a question, the same acknowledgement must not be reused, and a reaction should say what it did to you rather than repeat what was said. French also dropped from 2500 ms to 1500 ms, and its prompt was told to drop the ceremonious constructions.

The same run afterwards: six turns, three of them with no question at all, and the acknowledgements varied — 「それは立派な柿ですね」「まあ、それは愛らしいですね」.

One tension came with it. Some of those warmer reactions — 「ミケちゃん、お腹が空いた時間なんですね」 — are light restatements, which rule 3 forbids. Whether 〜なんですね reads as warm aizuchi or as parroting is the same native-speaker question that is still open below.

## Known prompt gaps

Measured with `tests/live/test_conversation.py`, which now runs a real multi-turn conversation. Before the harness fix below it only ever reached one exchange, so every earlier figure here described first-turn behaviour and has been discarded.

| What it does | Status |
| --- | --- |
| Raises a refused topic again | **Fixed.** Broken by the prompt rewrite itself, then fixed by giving rule 2 its exception. |
| Steers back instead of following a change of subject | **Mostly works.** Over nine turns it followed her from sunbathing to the weather to the department store to the neighbour to the cat, then repeated an earlier question once. A lapse rather than a rule it ignores. |
| Uses the wrong kanji for a name | **Fix in place, not yet proven.** The name now reaches the prompt from the senior's profile instead of being transcribed. Whether the model always uses the spelling it is given is a separate question, and one run is not an answer. |
| Recaps what it heard before asking | **Open**, and a native speaker's call: whether 〜のですね reads as natural aizuchi or as presumptuous is not something the harness can settle. |

Note that a per-conversation pass rate is harsher than a per-turn one: nine turns give four or five chances to slip, so one lapse fails the whole run.

### Deferred: names come back with the wrong kanji

He introduced himself as 佐藤**茂**; the interviewer called him 佐藤**繁**. Both read *Shigeru*. The model hears a sound and picks a plausible spelling for it.

This matters more than it looks. The output of this product is a memoir a family keeps, and misspelling a grandfather's name in it is not a cosmetic defect. It is also the same failure as naming a town that was never named — the model filling a gap with something plausible.

**No prompt instruction can fix a homophone**, so this is not a wording problem and should not be attacked as one. The fix is to stop transcribing what we already know: the senior's name, birthplace and family names belong in their profile as seed facts, and the interviewer should be given them rather than inferring them from audio. `seniors/{id}` in [plan.md](plan.md#data-model-sketch) already carries them.

Slice 3 introduced that profile and the fix is now in: `brain.context_for` puts the name, its reading, the birth year and the birthplace into the prompt, and the interviewer is told to use that spelling. Recordings made before this may still carry the wrong characters.

The profile only covers the people it lists — the senior, and the family members entered with them. Everyone else arrives through audio alone: the first boss, the neighbour, the schoolteacher, the friend who moved away. Those names have the same homophone problem and nothing to check them against, and they are most of the names a life story contains.

Three things could help, none of them yet built:

- **Do not assert a spelling we do not have.** A name heard once could be stored in kana, as it was heard, rather than in kanji the model chose. An honest 「しげるさん」 is better than a confident, wrong 佐藤繁.
- **Let the family correct them.** Relatives know how their grandfather's friend's name is written. This fits the family loop already planned for slice 6 — a name the senior cannot easily spell out is exactly the kind of thing a family member can fix in one tap, and it turns a defect into a reason for them to open the page.
- **Confirm in conversation, carefully.** The prompt already asks the interviewer to check names lightly, but confirming a *sound* does not settle a *spelling*, and asking an eighty-year-old which characters they mean is not a warm question. This is the weakest of the three.

What remains unproven is whether the model reliably uses the spelling it is handed. It did in one run and greeted with the wrong-name-free 「田中ハルさん」; in another it greeted without using the name at all. Being given a fact is not the same as honouring it, and that needs measuring over several runs rather than asserting.

A name that arrives by ear alone did worse on 2026-10-13. `test_invents_nothing_the_person_did_not_say` gives the interviewer no profile, so it learns 佐藤茂 only by hearing him say it, as it learns every name in a story. It passed 1 run in 4. Once it called him 「佐藤誠さん」: a different name, not another spelling of the same one. Once the judge failed 「佐藤さん」 for not being the full name, and 「どのようなお魚を捕まえていらしたのですか」, after he had spoken of his fishing boat, as an invented detail; both readings are stricter than the test's own wording, and whether a surname with さん is right is the native speaker's call. The fourth failure's reason was lost with its output. Not touched before the review, since any prompt change has to be measured again and judged in Japanese anyway. Names from a profile are not this path: the senior's own, and a judge's, typed on the start page.

### The harness was only testing the first exchange

Worth recording, because every conversational figure reported before this was wrong.

`session.receive()` completes at the end of a turn rather than running for the life of the session. The listener task therefore exited after one turn and stopped forwarding audio, so each side answered exactly once and the conversation stopped dead at two turns. Re-entering `receive()` in a loop fixes it: the same 130 second run went from 2 turns to 9.

Two smaller faults fell out of the same investigation. The interviewee was seeded with `send_client_content`, and mixing that with realtime audio left its turn state such that it never spoke again — it is now started with a synthesized hello played to the interviewer, so both sides only ever see audio. And the hesitancy instruction was being given to every persona, which made their turns so long that no conversation reached a second exchange; it now belongs only to the persona whose test is about patience.

## Open questions

Tracked in [plan.md](plan.md#open-questions-and-risks).

Model choice is settled: **`gemini-3.8-live`** (GA) for voice, `gemini-3.8-flash` for the extraction and planning passes. The remaining question that gates slice 1 is empirical — does it handle elderly Japanese speech well, and does it hold the language steady across a long pause?

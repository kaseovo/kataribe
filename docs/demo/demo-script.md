# Demo video

Published on 2026-10-18: <https://youtu.be/wg3SdraT2Oo>, 3:48, public on YouTube. Planned on 2026-10-15; it was made differently from the plan below, see *As made*.

Between 3 and 4 minutes, public on YouTube, in English, and it has to show the solution working (see *Submission rules* in [plan.md](../plan.md)). The target is 3:30: the middle of the window, so a take that runs long or short still lands inside it.

## As made

- **Setsuko is voiced by AI, not recorded.** A live take with a person playing her proved unworkable: the interviewer asks what an invented person cannot answer. Her lines follow [setsuko-script.md](setsuko-script.md), voiced with Gemini text-to-speech: Callirrhoe for her, Sulafat for the interviewer (the product's own voice), Iapetus for the narrator. The video and the live family page say she is made up and voiced by AI.
- **Her family page is the product's own.** Both conversations were assembled as the product records them and uploaded through the console, and the pipeline wrote her page from them. It is the start page's example, `b0902602320c`, and the video's family page and phone shots are taken from it.
- **Your turn is played as Alex**, on the live site, with the conversation scripted; the family page Alex reaches is recorded in the same take.
- **The edit** was assembled from rendered sections, in order, outside the repository; the end card names the site, not the repository.

## Shape

A demo-centred pitch. It opens cold on a conversation, the footage carries the loop, a short look under the hood sits just before the second session, and Tanguy then tries it on the live site, in English, before it ends on the URL. Many judges will watch only this, so it has to make the case on its own. Second by second, it is in [storyboard.md](storyboard.md).

| Time | Picture | Sound | Narration |
| --- | --- | --- | --- |
| 0:00 | The お話しする button pressed; the interviewer greets 節子さん; she answers | Session | — |
| 0:13 | A slow push in on the screen; a *Kataribe 語り部* title at 0:24 | Session lowered, no subtitles; music | 1 |
| 0:30 | Session 1: a name and a place, the pause, a change of subject | Session | 2, 3 |
| 1:18 | Session 1, six minutes in: the close and the answers about sharing | Session | 4 |
| 1:43 | Family page: cover, Japanese to English, the chapter, one quote played | Her voice in the quote | 5 |
| 2:05 | Family page on a phone: 由佳 sends her question | — | 6 |
| 2:16 | Under the hood: five steps, a console shot under *Check* | Music | 7 |
| 2:36 | Session 2 opens with 由佳's question; her answer; the question stamped answered | Session | 8 |
| 2:58 | Your turn: Tanguy on the live site in English, from the start page to Tanguy's own family page | Tanguy and the interviewer | 9, 10 |
| 3:31 | End card: kataribe.kaseovo.com, the repository | Music | 11 |

Music, if any, plays only under the opening narration, the five steps and the end card, never under a conversation.

## The speaker

小川節子, a persona: who she is in [persona.md](persona.md), and what she says when in [setsuko-script.md](setsuko-script.md). The plan was a live take, unscripted on the interviewer's side; she was voiced by AI instead (see *As made*).

In *Your turn*, Tanguy plays no one: a real life, on the live site, in English, exactly as a judge would try it.

## Recording

- **Picture:** Cmd+Shift+5, full screen, with the DJI mic selected so the file has a guide track.
- **Her voice:** the DJI mic, plugged into the Mac as the browser's microphone, so the interviewer hears it too. If the transmitter can record on its own, that is a second copy.
- **The interviewer:** the session's WAV, downloaded from the console afterwards. Its right channel is the interviewer, its left her microphone, on one timeline.
- **Headphones** on her, so the interviewer's voice never reaches the DJI mic.

## In the edit (CapCut)

- **Subtitles are burned in, and there are no caption tracks.** The start page embeds the video with captions on, so a burned-in line and a caption track would show twice.
  - Dialogue: once the cut is locked, auto-caption the session audio in Japanese and export it as SRT. Each line gets its English, on the same timings, and the native speaker checks both. In the conversations they become the side transcript (below); elsewhere, a caption track in plain white with a speaker label.
  - Narration: auto-caption the narration track in English, correct it, and set it in italic in another colour. Narration sits between exchanges, never over a subtitled one, so the two never overlap. Under narration 1 the conversation goes on, lowered and without subtitles.
- **The conversations run beside a transcript.** Chosen on 2026-10-16 over a subtitle band under the screen and a subtitle in place of the おわる button, since a viewer who misses a line can catch up. The screen recording sits at 60% in a window on the left; on the right, the last three turns, each in Japanese and in English, the current one marked. One image per state of the transcript, made from the real transcript after the take. Each session, and the close, starts it empty.
- **In *Your turn*, only Tanguy is subtitled.** The visitor's screen already shows the interviewer's words in large type.
- **Session 2's opening is one long turn.** The screen's caption grows through the whole turn, and two sentences run past the bottom of the screen. Cut to the second sentence, or crop.
- **The pause:** in the transcript, her line breaks off at `…`, a counter inside it ticks up while the screen shows it is listening, and it stops on the length of the silence when she goes on. Narration 2 follows.
- **No tool names on screen.** The five steps are only *Talk, Write, Check, Share, Plan*.

## Wording

- Nothing presents Setsuko as a real person or a real user: the narration gives no age or town as fact, and never says "our user".
- One spoken "Gemini", in narration 7. Judges score the use of generative AI, and this is a Google Cloud hackathon.
- No comparison that hasn't been measured, such as "faster than" or "most assistants would…".
- ¥220,000 is "from ¥220,000", as its source ([親の雑誌](https://oyanozasshi.jp/price/)) says.
- The pause length in narration 2 is whatever the review settles; 5 seconds is today's default.

## Narration draft

Short sentences, for reading aloud. About 200 words, about 85 seconds of a 3:43 cut.

1. *(0:13, over session 1)* "Every family has someone whose stories nobody has asked for yet. A professional life story in Japan costs from 220,000 yen, and it's made once. Kataribe asks: by voice, a few minutes a day."
2. *(0:56, after the pause)* "It waits. Five seconds, tuned for someone searching their memory."
3. *(1:14, after the change of subject)* "One question at a time. It follows where she goes."
4. *(1:38, at the close)* "At the end, it asks what her family may read. She keeps one story to herself."
5. *(1:47, family page)* "Her family gets a chapter. Every line of it rests on something she said, in her own voice." *(1:59, after the quote plays)* "The story she kept isn't there, and nothing says it ever was."
6. *(2:12, the question)* "And the family can ask back."
7. *(2:16, five steps)* "Under the hood: the conversation runs live on Gemini. Afterwards, it writes the stories, checks every quote word for word against the transcript and the recording, shares only what she agreed to, and plans what to ask next, the family's question first."
8. *(2:55, the question stamped answered)* "Her answer goes back to Yuka." Narration 7 has already said that the family's question comes first.
9. *(2:58, the start page)* "And you can try it too: on your own life, in English."
10. *(3:27, Tanguy's family page)* "A minute or two later, it's on your own family page."
11. *(3:32, end card)* "Today, for families. Next, for a town's memory, in its elders' own voices. Someone should remember, before no one can ask." The URL is on the card, so it is not read out. "Next" keeps it honest: sharing beyond the family is not built yet.

## Length

The window is 3:00 to 4:00. Spoken at a natural pace, the storyboard runs 3:43; the animatic measured it with synthesized voices. Real takes drift, so check the cut against both ends.

Over 3:50, cut in this order: the change of subject (narration 3 moves onto another exchange), then the console shot (the five steps stay), then the switch from Japanese to English on the family page (go straight to English).

Never cut: the cold open, the pause, the answer about sharing, the quote in her voice, session 2's opening, *Your turn*.

Under 3:10, let session 1 run an exchange longer before the close.

## Steps

Steps 1–15 and 19 were the plan for a live take with a native speaker, which did not happen; *As made* says what was done instead. Steps 16–18 were done.

Before the take:

1. **Native speaker:** the review that the camera will hear: step 1 of [japanese-review.md](japanese-review.md) (pause and voice), and its questions 1–4 and 6–10.
2. **Tanguy:** the fixes, `make eval`, then a deploy, with `TRY_LANGUAGES=en,ja` if the review passed.
3. **Tanguy:** the DJI as the Mac's microphone, tried in a one-minute conversation with a throwaway person in the console. Not with Setsuko, whose memory has to start empty.
4. **Tanguy:** create Setsuko with the command in [persona.md](persona.md).
5. **Native speaker:** read persona.md and make it hers.

The take:

6. **Both:** session 1 from `/talk/{id}`, recorded as above. Download its WAV from the console.
7. **Tanguy:** once it is written up, record the family page: the cover, the chapter, the switch to English, one quote played. Check that the story kept private isn't there.
8. **Native speaker:** send 由佳's question, the one prepared in [setsuko-script.md](setsuko-script.md), from the family page in English, as granddaughter Yuka, at phone size (Chrome's device toolbar, 390 × 680), recorded. The steps are in [persona.md](persona.md).
9. **Both:** session 2, the same way. Once it is written up, record at the same phone size her question stamped Answered, and the story it opens.
10. **Tanguy:** record the console's session 1: the transcript with its quoted lines lit.
11. **Tanguy:** *Your turn*, on the live site, in Chrome full screen, as Tanguy: the start page, the name, *Start talking*, an exchange or two in English, *Finish*, *Share with my family*, then the new family page once it is written. Clear the site's data in the browser first, so the start page offers the form rather than *Welcome back*. On a laptop the sharing buttons run off the bottom of the screen; zoom the page out until both show.

The edit:

12. **Claude:** the five steps as a page to screen-record, and the pause counter as a clip.
13. **Tanguy:** the cut in CapCut, between 3:00 and 4:00, aiming at 3:30 to 3:45. Her voice from the DJI, the interviewer from the WAV's right channel, lined up on her first words.
14. **Claude:** the English dialogue subtitles, from the exported SRT. **Native speaker:** checks them.
15. **Tanguy:** record the narration on the DJI, place it, caption it. Export at 1080p.

Publishing:

16. **Tanguy:** upload to YouTube as public, and turn off its automatic captions. *Uploaded on 2026-10-18: <https://youtu.be/wg3SdraT2Oo>.*
17. **Tanguy:** set `SHOWCASE` to Setsuko's id and `VIDEO_URL` to the video as the Makefile's defaults, since every deploy replaces the service's settings, then deploy. Check that the start page plays it and the judge's path offers it. The showcase takes no questions, so this comes after step 9. *Done on 2026-10-18, revision kataribe-00024: the start page plays it with captions on, and the judge's path offers it.*
18. **Claude:** the README (it says the video "shows a whole conversation"; it shows parts of two), this file, and slide 6 of [pitch-deck.md](pitch-deck.md) and the live deck. *Done on 2026-10-18, with the submission deck's links slide.*
19. **Native speaker, during the edit:** the rest of the review: questions 5 and 11–14, and step 5.

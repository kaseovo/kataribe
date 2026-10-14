# Japanese review and demo take

The product is Japanese, and until now nobody has judged it in Japanese. Every prompt change since 2026-09-30 was tested in French and English. This settles the pause length and the voice, judges the Japanese, and records the conversations the demo video and the showcase family page are made from. Whatever the review finds has to be fixed and retaken before the submission. See *Japanese validation is deferred* in [roadmap.md](../roadmap.md).

Everything here runs on the live service, <https://kataribe-uxxefqeqqq-an.a.run.app>, so the showcase persona ends up in the cloud store the start page links to. The console is at `/console`, behind the team password.

## 1. Pause and voice (console, about 20 minutes)

Open `/console`, create a test person in Japanese, and hold short conversations. Changing a setting starts a fresh session.

- **Pause.** Stop mid-sentence for two or three seconds, as if searching for a memory. Raise *Pause before replying* until the interviewer waits. Measured against synthesized speech, 3500 ms cut into a 2.5 s pause and 6000 ms waited through a 4 s one; the default is 5000 ms. The gap the model sees is roughly double the pause, so the right number is a judgement on real speech.
- **Voice.** Seven are shortlisted: Sulafat (current), Vindemiatrix, Achird, Gacrux, Callirrhoe, Despina, Kore. Pick the one an eighty-year-old would find easiest to listen to.

If either changes, the new defaults go in the `ja` entry of `backend/src/kataribe/languages.py` and get deployed **before the take**, since the senior's screen uses the defaults, not the console's slider.

## 2. Read the prompt (about 30 minutes)

[`interviewer_ja.md`](../../backend/src/kataribe/prompts/interviewer_ja.md), with its English gloss [`interviewer_ja.en.md`](../../backend/src/kataribe/prompts/interviewer_ja.en.md) beside it. Read it as an elderly person would hear the result: warm or stiff, polite or ceremonious, a neighbour or a clerk.

Then these specific questions, each from a test run:

| # | What came out | The question |
| --- | --- | --- |
| 1 | 「ミケちゃん、お腹が空いた時間なんですね」 | Rule 3 forbids restating what was heard. Is 〜なんですね warm aizuchi or parroting? |
| 2 | Recapping before asking, 〜のですね | The same question for the recap. A test is marked as an expected failure until someone decides. |
| 3 | 「素敵ですね」「尊いものですね」, turn after turn | The prompt now forbids stacked praise. Is what remains natural? |
| 4 | 「前回伺った…お話を、今もよく覚えています」, 「とても心に残っております」 | Recalling last time. Warm, or presumptuous? |
| 5 | 「知りたがるといらっしゃいました」 | Not Japanese. Listen to whether the voice said it or only the transcript wrote it. |
| 6 | 「お孫さんのゆかさんが…知りたがっていらっしゃいましたよ」 | Opening with a family question. Natural? |
| 7 | 「お話の途中ですが、そろそろお開きの時間となりました」 | It says aloud that it is time to close. Fine, or awkward? |
| 8 | 「今日は、お父様の工場のお話と、夏の川のお話を伺いました。ご家族にもお伝えしてよろしいですか。…」 | The question about sharing at the close, as the prompt words it. Clear enough that a yes is a real yes? |
| 9 | 「ご主人のお話は、ここだけのお話にしておきましょうか」 | A painful story, asked about on its own. Does keeping it private sound like the easy answer? And should a warmly told story that ends with a husband's death count as painful? |
| 10 | 「佐藤さん」 for someone who said 佐藤茂 | The prompt says to use the name 一字も変えずに. Is a surname with さん the right way to address someone, or is the full name expected? |
| 11 | 「佐藤誠さん」 for 佐藤茂 | A name heard only by ear came back as a different name. How should the interviewer handle a name it is not sure of? |
| 12 | Goodbyes after the close | It answers each further goodbye with a word or two. Polite, or should it stay silent? |
| 13 | 「田中ハルさんは二十四歳のときに、小学校の先生だった正夫さんと結婚した。」 | Summaries are now sentences about the person, by name, instead of their phrases strung together. です/ます or だ/である, for a family to read? And her 「やっておりました」 came back as 営んでおり: too far from her own word? |
| 14 | 「このまま続けるか、今日はここまでにするか」, then 「ご家族に読んでいただいてもよろしいですか。それとも、ご自分だけのものにしておきましょうか」, and 「毎回、最後のお話についての質問をひとつ添えてください」 | A visitor's short trial (`visitor_rules` in `backend/src/kataribe/languages.py`). Only for judges talking in Japanese: natural? |

## 3. The take, first session (about 10 minutes)

**Decide first:** who speaks, and as whom. The video and the showcase family page are public, so the speaker agrees to their voice and these stories being shown, and tells only stories they are happy for anyone to read.

1. In `/console`, create the person with their real profile: name, reading, birth year, birthplace, family members. Names in the profile are spelled right; names heard only by ear may not be.
2. Open their own screen, `/talk/{id}`, in Chrome, full screen. Start screen recording (QuickTime or OBS) with system audio.
3. Press お話しする. The interviewer speaks first. Talk for six minutes or more: the closing cue comes at six. Answer the question about sharing **aloud**: yes for the stories that should reach the showcase page, and keep one private, so the page shows that private stories stay private.
4. Wait for the writing-up, then open `/family/{id}` and record the new stories, with a quote played.

While it runs, the reviewer notes:

- [ ] It never interrupts a pause for thought
- [ ] It never drifts out of Japanese
- [ ] One question at a time, short turns, follows a change of subject
- [ ] No name, place or year it was not told
- [ ] It closes warmly, names today's stories, asks about sharing, proposes a topic for next time

## 4. The family question, second session (about 10 minutes)

1. On the family page, send a question as a relative: who they are (孫のゆか, not just ゆか) and what they want to know.
2. Start a second session from `/talk/{id}`, recorded. It should open with a word about last time, then the family question, saying who asked.
3. Answer it, agree to share at the close, and record the answer appearing under the question on the family page.

**Only after this** set the showcase. The showcase's family page takes no questions, so the question has to be sent before.

## 5. Read what it wrote (about 15 minutes)

On the family page and in the console:

- [ ] The transcript matches what was said, names and places included
- [ ] Story titles and summaries read naturally in Japanese
- [ ] Every quote is what they actually said, word for word
- [ ] The Japanese screens read well: the senior's screen, and a visitor's question about sharing while it closes and on the end screen (`frontend/src/Talk.tsx`), and the start page's family question 「子どもの頃の場所で、今も思い出すところはどこですか？」 (`frontend/src/Landing.tsx`)
- [ ] The English under each passage on the family page says what the Japanese says, and no more
- [ ] The family page read in Japanese (`WORDS.ja` in `frontend/src/Family.tsx`): 人生の物語, 目次, 第1章, the quotes button 「田中ハルさんご本人の言葉と声で」, the question panel (送ったご質問, お答えあり / これから, 田中ハルさんとのご関係は？ and its relations, the preview 「…と知りたがっていらっしゃいますよ」)

The family page's own labels are English over Japanese content. That stays for the hackathon.

## 6. Fix and retake

The findings become fixes. Each prompt fix is measured again with `make eval` before the retake, since a change that fixes one rule has broken another before (see *Asked once, at the close* in the roadmap).

Retake steps 3 and 4 on a fresh person if the fixes changed what the interviewer says, and the reviewer listens to the new takes against the same checklists.

## 7. Japanese for judges

**Decide whether judges may talk in Japanese.** If the review passes, `TRY_LANGUAGES=en,ja` in the next deploy. If not, judges get English only and the video shows the Japanese.

## What comes out of it

| Output | Where it goes |
| --- | --- |
| Voice and pause | `ja` in `backend/src/kataribe/languages.py`, then deploy |
| Prompt fixes | `interviewer_ja.md` and its gloss, measured with `make eval` |
| The showcase person's id | `SHOWCASE=<id> make deploy` |
| The recordings | Cut to 2–3 minutes with English subtitles, see [demo-script.md](demo-script.md); `VIDEO_URL` in the deploy, slide 6 of the deck, the README |
| Japanese for judges, yes or no | `TRY_LANGUAGES` in the Makefile |
| What was decided, and why | The roadmap, under *Japanese validation is deferred* |

# The demo persona: 小川節子

A made-up grandmother, voiced by AI. The demo video's conversations are hers, and so is the family page the start page shows as its example. Decided on 2026-10-18, after a take with a person playing her proved unworkable: the live interviewer asks things an invented person cannot answer. The video and her page both say she is made up and voiced by AI.

## Profile

| | |
| --- | --- |
| お名前 | 小川 節子（おがわ せつこ）, Ogawa Setsuko |
| 生まれ | 1944年 |
| 出身 | 岐阜県郡上八幡 |
| ご家族 | 夫 和夫（故人）, 長女 美穂, 長男 誠, 孫 由佳（美穂の娘） |

On the live service she is `b0902602320c`, the Makefile's `SHOWCASE`: her page is read-only and takes no questions.

## Her voices

- **Setsuko:** Gemini text-to-speech, the voice Callirrhoe on 3.8 Flash Lite TTS, every line from that one model and kept within one pitch band (163–211 Hz), so she always sounds like the same woman. Names go to the voice in kana (せつこ, かずお, ぐじょう, しんばし, ゆか), since it misreads their kanji.
- **The interviewer:** Sulafat, the voice the live product speaks with.
- **The narrator**, in the video only: Iapetus.

Every take was checked word for word against its script by a listening model.

## How her page was made

Her two conversations, in [setsuko-script.md](setsuko-script.md), were assembled as the product records them: one 24 kHz stereo recording per session, her on the left and the interviewer on the right, each of her turns timed at the end of her speech as the live product times it. Each was uploaded through the console's API (`POST /api/sessions`, then its `/recording` with the transcript and the audio), and the pipeline wrote, checked and shared her stories as it does for anyone. Every quote on her page plays her voice, cut from those recordings.

Granddaughter Yuka's question was sent between the two sessions, so session 2 asks it. Daughter Miho's was sent after, so it waits.

## What her page holds

| Story | Life stage | Shared |
| --- | --- | --- |
| 新橋からの川への飛び込み · Jumping into the River from Shinbashi Bridge | Childhood | With her family |
| 十二のときに飛び込んだ話 · The Story of Jumping When She Was Twelve, answering Yuka | Childhood | With her family |
| 郡上おどりと和夫さんとの出会い · Gujo Odori and Meeting Kazuo | Marriage | With her family |
| 和夫さんの看病と別れ · Nursing Kazuo and Saying Goodbye | Later years | Kept private: not on her page |

| Question | From | State |
| --- | --- | --- |
| Grandma, did you ever jump off the Shinbashi bridge? | Granddaughter Yuka, in English | Answered in session 2 |
| お母さん、郡上おどりの晩は、どんな浴衣を着ていたの？ (Mom, what kind of yukata did you wear on the night of the Gujo Odori?) | Daughter Miho, in Japanese | Waiting |

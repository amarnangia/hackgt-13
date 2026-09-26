# Weave: project overview

What Weave is, what we tested and how, the numbers we measured, the safeguards we built, and what's still open. For
the idea and screen layout see [idea.md](idea.md); for setup see [plan.md](plan.md); for the demo see [demo.md](demo.md).

## What it is
An overlay on the WhatsApp (or Instagram) call in Chrome that lets a grandkid talk with their Telugu-speaking
grandmother:
- **Her side:** her Telugu becomes English captions and her own cloned voice.
- **Learning:** words the grandkid knows stay in Telugu.
- **Understanding:** pictures and proverb meanings appear, and a "Curious?" panel answers questions.
- **Taking part:** "ask her" prompts and replies in Telugu help the grandkid speak.
- **Keeping it:** every call becomes a family story page.
- **Their side:** the grandkid's English reaches her as spoken Telugu.

Everything runs on one MacBook (tested on an M4 MacBook Air, 24 GB). Grandma needs nothing new.

| Job | Model | Where |
|---|---|---|
| Hear her Telugu (and the grandkid's English) | Meta Muse Voice Transcribe | cloud, streaming |
| Telugu → English | IndicTrans2 1B, raced against Meta Muse Spark after 1.2 s | laptop / cloud |
| English → Telugu (`--two-way`) | IndicTrans2 English → Telugu 1B (gated model) | laptop |
| English in her voice | Pocket TTS (voice clone); Kokoro until the clone is ready | laptop |
| Telugu voice for her | Meta MMS Telugu (`facebook/mms-tts-tel`) | laptop |
| Split-second decisions | Laya: question?, topic, which picture, what to ask, which reply | laptop |
| Story pages, "ask her" questions, answers | Meta Muse Spark | cloud |

## Latency (measured)

| Step | Time | How we measured it |
|---|---|---|
| Her sentence → English on screen | ~0.4–0.6 s | latency log, from the moment the speech service delivers her last word |
| The speech service's own delay | ~0.7 s, fixed | Muse has no setting for it |
| Translation on the laptop (IndicTrans2 1B) | ~0.3 s a sentence | translator timings; the 200M model was only ~20 ms faster (266 vs 287 ms) and worse, so we kept 1B |
| English on screen → her cloned voice starts | median 0.11–0.16 s | two runs of the sample call, 11/11 lines voiced |
| Her sentence → her voice in English | median 0.54–0.69 s, max ~1 s | same runs |
| Live draft captions | shown 2–3 s *before* she finishes | the draft test; final English 0.05 s after with drafts vs 0.14 s without (no slowdown) |
| Topic words, "Curious?" questions about her words, the picture of what she named, the "ask her" question | ~2–4 ms after her line is cut (was ~0.6–0.9 s) | `tools/check_decisions.py` on the demo lines; decided from her Telugu words before the English is back |
| How to answer her question in Telugu | with the English (~0.3–0.4 s); keywords, else Laya ~70 ms | same |
| Laya per line, as the call runs | median 52 ms, slowest 171 ms (was 240 ms) | `tools/eval_laya.py`; rules first, then one question at a time: intent (~45 ms), topic only when the rules can't tell (~95 ms). Asking several questions in one pass was *slower* on this Mac (intent + topic: 169 ms together vs 140 ms apart) |
| "Curious?" answer | instant for word-list words; ~1.5 s from Muse Spark, then cached | the answer test |
| Grandkid's English → Telugu speech for her (`--two-way`) | not timed on this Mac yet; the Telugu voice makes ~4 s of speech in ~0.6 s | `tools/check_two_way.py` passes 13/13 checks each way, on Hasini's Mac and on the M4 |
| Story page after the call | ~30 s | real calls |

**What made it faster** (each measured before and after):
- **Voice first:** speaking before Laya and the picture lookup made the voice start ~0.5 s sooner.
- **Streaming the cloned voice** clause by clause, with one-time volume calibration: another ~0.2–0.8 s.
- **Capping the voice model's GPU cache at 256 MB:** before, it grew to ~2 GB, pushed the Mac into swap and made translations take ~10 s.
- **A 1.2 s race against Muse Spark** for slow local translations.
- **Catch-up speed:** a speed-up of up to 1.12× when English lines queue.

## Cost
- **On the laptop, no per-use cost:** Telugu → English translation, both voices, Laya, draft captions, pictures from our library, and the knowledge model.
- **Meta Model API use per call:**
  - **Muse Voice Transcribe** for the call's audio (her side, plus the grandkid's side with `--two-way`).
  - **Muse Spark:**
    - backup translation only when the laptop is slower than 1.2 s (rare);
    - at most one "ask her" question every 25 s, only at pauses after she shares something;
    - one answer per "Curious?" click on something outside the word list;
    - one story page per call.
  - With `--two-way`, the grandkid's English → Telugu translation and voice run on the laptop (no API cost).
- **Wikipedia:** only for things not in our 213-picture library, cached after the first look-up.
- **Evaluation:** comparing against Muse Spark (`tools/eval_laya.py --muse`) costs about 90 API calls per run.
- **Dollars:** we don't have Meta's per-call pricing in hand. The design keeps cloud calls to what needs a big model: the speech service and the writing. Every per-sentence decision stays on the laptop.

## How we tested

**Real calls**
- **Several WhatsApp Web calls** with a family member speaking Telugu, 4 of them saved as story pages.
- **What they found:**
  - the WhatsApp Mac app bypasses the audio routing (so: WhatsApp Web only);
  - the Mac volume below 100% silences what the app hears;
  - WhatsApp Web's speaker setting matters.
- These led to the sound warnings in the app.

**Translation quality**
- **Our 308-word Telugu glossary on vs off,** sentence by sentence. Without it the translator turned *gangireddulu* (decorated bulls) into "the Ganges" and *gavvalu, sunnundalu* into "gavas, limes"; with it they come out right.
- **Four substitutions that made sentences worse,** like "mango orchard by the pond", were found this way and fixed.

**Laya** (`python tools/eval_laya.py [--muse]`), on lines we wrote and labelled plus a held-out sample call:

| Decision | Laya alone | Our rules, then Laya | Muse Spark alone |
|---|---|---|---|
| What is the line about? (11 topics) | 64%, 0.13 s | 91%; 9/10 on the held-out call | 95%, 1.0 s |
| What is she asking you? (for the reply in Telugu) | 78%, 0.10 s | 96% (no reply when Laya is under 50% sure) | 100%, 0.9 s |
| Question, request or statement? | 17/18 as a three-way choice | 97% | — |

Earlier Laya tests that shaped the design:
- **Model choice:** Laya's English checkpoint took ~120–150 ms for 3 questions and got the category right on 6/6 sample lines. The multilingual checkpoint was faster (~45 ms) but much less accurate, so we use the English one.
- **Yes/no questions failed.** "Does this need attention?" got 9/14 and "Is this worth a follow-up?" got 10/18, so those became rules.
- **Picture choice needed rules around it.** Laya alone picked the right picture 14/25 times, so rules decide the obvious cases and Laya chooses between candidates.
- **Requests:** 29/29 with the question rule plus Laya.
- **A rule bug fixed:** "Don't be sad" and "May God keep you happy" were counted as questions until we fixed the rule.

**The whole pipeline without audio**
- Telugu sentences go in as if the speech service heard them, and we checked everything that comes out: English, kept words, cards, pictures, "ask her" questions, "Curious?" questions, topic changes.
- Every line of [demo.md](demo.md) was run this way, and the demo table was corrected to what actually happens.

**Voices**
- **The Telugu voice** was checked by running its speech back through Meta's Telugu transcription: it came back nearly word for word.
- **The cloned voice** was tested for cut-off sentences (fixed: it was carrying over earlier sentences) and volume.

**The overlay**
- **Tested in a browser preview page** against a pretend call (`tools/fake_call.py`), at a narrow (671 px) and a laptop (1440 px) window. That found and fixed:
  - captions covering a panel;
  - the same thing shown twice (picture and card, two questions);
  - wrong picture captions;
  - the question list moving under the mouse.
- **Clicking a question** reaches the engine and shows the answer. Your side of the call shows in the captions, marked "You".

**The knowledge model** (`progress.py`)
- **Simulated histories:** pulihora is kept in Telugu on its 4th mention (2nd with `--keep-at 0.4`); tapping it drops it to 19%; forgetting over days works.
- **The fitting tool,** on a simulated learner who learns twice as fast, recovered that learning rate (2.0).
- **What counts as learning:** three hearings of *ninna* in a row count as one (0.15 → 0.32, not 0.56); a kept word
  left untapped five times in a call counts once; a word the grandkid says on their own mic (`--two-way`) goes 0.20 → 0.85.

**What gets translated**
- **Her Telugu in English letters** ("Bangaram, pulihora tinnava?") went through untranslated, because IndicTrans2 only
  reads Telugu script. Now Muse Spark translates it ("Sweetheart, did you eat pulihora?"); English with a Telugu word
  or two gets the word list's English for that word instead, with no API call. Her words in English letters get cards,
  pictures and questions too.
- **Lines of only words they know** ("Sare, sare" once *sare* is learned) are captioned but not voiced: they understood her.
- **Kept words** are kept every time they come up in a line, not just the first time.
- **A word inside a longer phrase** is part of the phrase: *annam* in *annam tinnava?* no longer brings up a rice card
  or "How do you make rice?".

**Security**
- **Engine:** websites (even WhatsApp's own page) are refused; our extension and local pages connect.
- **Weave server:**
  - other websites can't read its answers or post to it;
  - it's unreachable from the Wi-Fi address unless started with `--lan`.

**Not tested yet**
- The extension on a real WhatsApp or Instagram call (only the preview page).
- `--two-way` on a real call (the scripted check passes on the M4; a live call needs BlackHole 16ch).
- Instagram calls.
- The iPhone app with `--lan`.
- The knowledge model fitted to a real quiz.

## Safeguards

**Privacy and security**
- **The engine only answers our own pages** (`origins.py`): the extension and pages on this laptop. Any website open in Chrome could otherwise read the call as it happens.
- **The Weave server:**
  - lets only our own pages read its answers across sites, and refuses posts from other websites;
  - listens only on this laptop unless `--lan` (for the iPhone app, on a network you trust).
- **Nothing personal is committed:** call recordings, story pages, voice samples, word progress, logs and the picture cache stay on the laptop.
- **The API key** lives in `.env`, which isn't committed, and a pre-commit hook blocks keys. A key once pasted into chat should be rotated.
- **The overlay** only appears when you turn it on, and its panels are extension pages the call site can't touch.
- **Transcription can be switched off** from the overlay (`{"type": "transcribe", "on": false}`) or started off
  (`--transcription-off`): no call audio reaches the speech service or the recordings until it's back on, and the call
  plays at full volume. Tested by replaying a recording and switching it off for 16 s: nothing was transcribed in between.

**Protecting data during tests**
- Test runs use temporary folders for calls and the Weave database, and back up and restore word progress. We added this after a test run deleted early call reports.

**The call experience**
- **The voice never falls far behind:** a line is skipped rather than spoken more than 3 s late (5 s for questions to you). With `--two-way`, a translation waits while its listener talks, fades out if they interrupt, and is dropped after 10 s; a line matching what just played on the speakers is dropped as echo.
- **Warnings:** if no sound reaches the app for 15 s, or the Mac volume is below 100%.
- **The connection stays up:** the speech service connection is kept alive with silence when audio capture stalls.
- **Pictures:**
  - the same one never repeats within 5 minutes;
  - only for things an American kid might not know;
  - Wikipedia only for words not in the dictionary, and never while a line waits: a word that isn't cached yet is
    looked up in the background and gets its picture the next time (`tools/prefetch_pictures.py` downloads ~2,000
    Indian foods, festivals, places and more ahead of time).
- **"Ask her" questions:** at most one every 25 s, never right after she asked you something, and each topic only once per call.
- **"Curious?":**
  - no questions about words you already know or everyday words;
  - reply suggestions only when the keyword or Laya is sure;
  - the list holds still while you point at it.
- **Draft captions** never run while a real translation is waiting.
- **Respect:** anything the grandkid might say to her is in the respectful form (meeru, mimmalni).

## Open items
- **Consent:** she should agree to her voice being recorded for story pages and cloned. There's no consent step yet.
- **The Telugu direction (`--two-way`)** needs the gated IndicTrans2 English → Telugu model (accept it on Hugging Face), and she hears the grandkid in a stock Telugu voice, not a clone of their voice.
- **Full-screen calls** hide the overlay, and the panels can't be moved yet.
- **The knowledge weights are hand-set** until they're fitted to real quizzes.
- **Only Telugu has a word list and pictures;** other languages would need their own.

## Reproduce the numbers
```
python tools/eval_laya.py --muse --wrong    # Laya vs rules vs Muse Spark
python tools/fake_call.py                   # a pretend call for the overlay (preview: extension/dev.html)
python tools/check_decisions.py             # what the overlay gets for each demo line, and how many ms after it's cut
python subtitles.py --file samples/grandma_story.wav --out none --no-open   # the pipeline on a recording, with latency
python tools/check_two_way.py              # both directions on a scripted call (needs the English -> Telugu model)
python tools/fit_progress.py                # fit the knowledge model once there are quiz answers
```

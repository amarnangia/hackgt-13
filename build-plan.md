# Build plan (v2: the call overlay)

What we're building is in [idea.md](idea.md). How to set up and run the engine is in [plan.md](plan.md).
Times are rough estimates for one person.

## 0. Decide (15 min, whole team)
- Answer the open questions at the end of idea.md: which side is which, whether answers are spoken, whether to keep "Ask her about it", panel sizes, and whether Instagram is in the demo.
- Freeze the message format in idea.md so the engine and the overlay can be built at the same time.

## 1. Overlay shell (about 2 h), in `extension/` ✅ built; still needs a test on a real WhatsApp and Instagram call
- **Draw the layout** on the call page: left panel, right panel, and captions at the bottom middle. The call video isn't covered.
- **Turned on by hand** on any tab (toolbar button or Alt+Shift+W), so it works on Instagram too.
- **One button collapses** both panels.
- **Show the connection state** ("Waiting for Weave engine" / "Listening to Ammamma").
- **Replaces Saanvi's caption extension** (`garden/extension`, removed).
- **Done when** the three regions show on a live WhatsApp Web call and an Instagram web call, and existing captions still work.

## 2. Right panel: pictures and meanings (about 1 h) ✅ built
- **Show the existing messages here:** `picture` messages as a picture card, and `details.cards` for idioms, proverbs, slang and customs as meaning cards.
- **Newest on top,** at most 4, fading after about 30 s. Clicking a card keeps it.
- **Done when** saying "gavvalu", "noru manchidaite ooru manchidi" and "NTR" brings up the right cards.

## 3. Left, bottom: topic vocab (about 3 h) ✅ built: 11 topics, vocab.json, her words' topics + keywords + Laya, tools/eval_laya.py
- **Engine: topics.** Define the topics listed in idea.md. Tag every entry in `lexicon.json` with a topic, and write a starter set of about 8 words per topic (greetings first).
- **Engine: Laya picks the topic** of each English line. It switches only when a topic wins 2 of the last 3 lines, then sends a `topic` message. Words she said in this call come first.
- **Overlay: show the words** (Telugu script, how to say it, English), with a hear-it button using the browser's Telugu voice or the romanized word.
- **Check it:** label 50 lines from `calls/*/call.json` with their topic and measure Laya's accuracy. Aim for at least 80%.
- **Done when** a call starts on greetings, moves to food words when she talks about cooking, and doesn't flicker.

## 4. Left, top: "Curious?" questions (about 4 h) ✅ built: curious.py (Laya ranks what to ask and recognizes her questions for the reply helper), LLM answers in subtitles.py
- **Engine: candidates.** Build them from each line: word-list matches, proverbs, picture candidates, and the nouns `pictures.py` already finds.
- **Engine: Laya picks the stem** for each candidate (what does ___ mean / what is ___ / who is ___ / why do people say ___), then ranks the candidates to keep the top 3. Also generate "How do I say ___ in Telugu?" from the reply the grandkid would likely give.
- **Engine: send and expire.** Send `curious` messages, drop duplicates, and let questions expire after about 60 s.
- **Engine: answer clicks.** On an `ask` message, answer at once from the word list's note if the word is in the list; otherwise ask Muse Spark with the last 5 lines as context. Send `answer`, and cache answers for the rest of the call.
- **Overlay:** show the questions, open the answer on click (Telugu word, pronunciation, 2–3 sentences), and show a loading state while the model answers.
- **Feed the knowledge model** (`progress.py`): an `ask` for a word calls `observe(id, "asked")`, and showing the answer calls `observe(id, "answer")`. Don't suggest "What does ___ mean?" for words that are already 70% or more known.
- **Check it:** on 30 real lines, count how often the 3 shown questions include the one a person would pick. Time the answers (instant from the list; about 1.5 s from the model).
- **Done when** clicking "What is Bhogi?" during a call shows a correct, short answer within about 2 s.

## 5. Laya numbers for the judges (about 1.5 h) ✅ `python tools/eval_laya.py --muse`; table in idea.md
- **Put one labelled test set in `tools/eval_laya.py`,** covering intent, topic, stem choice and question ranking.
- **Report accuracy and time per decision,** next to Muse Spark doing the same job. Put the table in the README and on a slide.

## 6. Demo and submission (about 3 h) ✏️ drafted: demo.md (checked through the pipeline), writeup.md, README.md; still to do: record the video
- **Script a 2–3 minute call** that triggers each part:
  - a greeting (vocab on greetings);
  - cooking (vocab switches to food, gavvalu picture, "What does gavvalu mean?");
  - a proverb (meaning card);
  - a question to you ("Asked you" tag);
  - hang up (story page).
- **Record the demo video,** plus a backup recording.
- **Write-up:** who it's for, how it strengthens connection, why AI is essential. Include the Laya table. Make sure the public repo README says how to run it.

## Reverse direction ✅ first version
`subtitles.py --to-telugu`: the grandkid's English → Muse Spark → Meta MMS Telugu voice → BlackHole 16ch (WhatsApp Web's
mic). Tested from a recording: all lines voiced, ~3 s from the end of a sentence to her hearing it (max ~5 s when lines
pile up). Next: IndicTrans2 en→indic (gated: accept it on Hugging Face) to cut ~1 s; show your side in the overlay.

## Order and parallel work
- **Two people can start at once** once step 0 is done: one on the overlay (steps 1–2), one on the engine (steps 3–4).
- **Steps 3 and 4** each need both the engine and the overlay. Build the engine side against the message format, then plug in the overlay.
- **Step 5 can start any time** after the topic labels exist.
- **If time is short,** cut Instagram, then the hear-it button, then the "How do I say" stem.

## To do (after the steps above)
- ✅ tooling built (`tools/quiz.py`, `tools/fit_progress.py --save`); needs real calls + a quiz to fit. **Tune how strongly each signal counts toward knowing a word** (`progress.py`). The priors, learning chances, evidence weights, the 7-day half-life and the 70% threshold are sensible guesses, not measured.
  - Record every signal with a timestamp during test calls.
  - Afterwards, quiz the grandkid on the words (knows / doesn't).
  - Fit the weights to those answers, e.g. with a small grid search that maximises log-likelihood.
  - Report how well the model predicts the quiz (accuracy, calibration) next to the old "heard it once" rule.
- ✅ **Live draft captions,** so the subtitles feel instant like Google's (`draft` messages; `--no-drafts` turns them off). Measured: drafts show 2–3 s before she finishes a sentence; the final English is no slower.
  - Translate her in-progress sentence every ~0.5 s and show it faded; replace it with the final English when she finishes.
  - The voice still waits for the finished sentence.
  - Telugu puts the verb last, so the draft will change as she talks. That's expected; the final line is what counts.

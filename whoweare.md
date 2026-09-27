# Weave: who we are, what we built, and how we demo it

Written from the code as it is today (latest commit `09a3c48`), not from older docs, some of which describe scrapped
ideas. It covers only the **Chrome extension** (on the WhatsApp Web call) and the **iPhone app**, not the web app.
Where a number was measured, it says who measured it and where.

---

## 1. One-liner
> **Weave helps kids of immigrant families actually talk to their grandparents: understand her live, get her
> telling stories, keep those stories in her voice, and need less translation every call.**

Closing line: *"Most translators get better at translating. Weave gets better at knowing when not to."*

---

## 2. The two-paragraph pitch
Millions of kids of immigrants call their grandparents every week, and the calls stay shallow: "Did you eat? How's
school? Okay, bye." Not because they don't care, but because the grandkid lost the language. Translation apps keep
you dependent forever, miss what her sayings and foods mean, and keep nothing from the call. Weave runs on the
WhatsApp call you already make. Grandma changes nothing and installs nothing. On the grandkid's laptop, Weave turns
her Telugu into English captions and speaks them **in her own voice**. It pops up pictures of the dishes, festivals
and people she mentions. And when she pauses, it suggests a question to ask her *in Telugu*, like "Pulihora ela
chestaru? Naaku nerpistara?" ("How do you make pulihora? Will you teach me?"), so she tells the story instead of the
grandkid just listening.

When they hang up, the call becomes a story page for the family: the stories she told, with **clips of her real
voice**, a family dictionary of her words in her voice, questions for next time, and a Telugu message to send her.
Meanwhile Weave tracks how likely the grandkid is to know each of her words, using Bayesian Knowledge Tracing with
forgetting between calls. Once they know a word, it stays in Telugu in the captions and the voice, so every call
needs a little less translation. Meta's Muse hears her live and writes the questions and the story. Laya, a small
model running on the laptop, makes the split-second decisions for every line. The iPhone app shows your language
growing as a plant, holds the family dictionary with her voice, and records your own voice, so the translations
sound like you.

---

## 3. What we actually use (from the code)

| Job | What we use | Where it runs | File |
|---|---|---|---|
| **Hear her speech (speech to text)** | **Meta Muse Voice Transcribe** (`muse-voice-transcribe-1.0`), live over a WebSocket, with Telugu set as the expected language and live partial transcripts | Meta's cloud | `muse.py` |
| ↳ backup if it fails | **None.** It reconnects automatically (0.2 s → 3 s between tries) and warns if the Wi-Fi is down. The old local Whisper version is only in git history (`d111471`) | — | `subtitles.py` |
| **Telugu → English** | **IndicTrans2 1B** (AI4Bharat), deterministic, on the Mac's GPU, after a **308-entry Telugu glossary** swaps in fixed English (pulihora, gangireddulu…) and a **pronoun fix** turns Telugu's gender-neutral తను into "she" or "he" from the verb or context | laptop | `translate_server.py`, `lexicon.py`, `pronouns.py` |
| ↳ backup | **Meta Muse Spark** (`muse-spark-1.1`): raced against the local translator if it hasn't answered in **1.2 s**, used if the local server is down, and always used for **Telugu written in English letters** (IndicTrans2 only reads Telugu script) | Meta's cloud | `subtitles.py`, `muse.py` |
| **English in her voice** | 1. **ElevenLabs Flash v2.5** in her personalized voice, if she recorded one (about 1 min, in the iPhone app). 2. Otherwise **Pocket TTS**, cloning her voice locally from about 10 s of call audio. 3. **Kokoro** (a stock voice) until that clone is ready | cloud / laptop | `eleven.py`, `dub.py` |
| **Laya's per-line decisions** | **Laya** (`convaiinnovations/laya`): request vs statement, topic (when rules can't tell), which picture, whether an unknown word is an Indian food/place/thing, which "Curious?" question matters most, what kind of question she asked (to offer a Telugu reply), and whether the grandkid understood a word from their reply (**a decision head we trained ourselves**) | laptop | `decide.py`, `pictures.py`, `curious.py`, `reply.py` |
| **"Ask her" questions** | Hand-written Telugu templates for things she names (food, festival, place, person, proverb…), ready instantly. Otherwise **Muse Spark 1.1** writes one from her last lines | laptop / cloud | `topics.py`, `prompts.py` |
| **"Curious?" answers** | Word-list words: instant, from our notes. Anything else: **Muse Spark 1.1**, using the call so far as context, cached | laptop / cloud | `curious.py`, `subtitles.py` |
| **Story page after the call** | **Muse Spark 1.3**: title, summary (English and Telugu), the stories she told, highlights, 3 questions for next time, a Telugu WhatsApp message | Meta's cloud | `calls.py` |
| **Pictures** | Our library of **213 pictures** (176 Indian, 37 American). Wikipedia lookups for anything else, fetched in the background and cached, never while a line waits | laptop / web | `pictures.py` |
| **Two-way: English → Telugu** | **IndicTrans2 English→Indic 1B**, spoken in **Meta MMS-TTS Telugu** (stock voice), or in the grandkid's own ElevenLabs voice (**v3 Conversational**, which speaks Telugu) | laptop / cloud | `translate_server.py`, `eleven.py` |
| **Sharing between laptops** | **Firebase (Firestore)**: word progress, the plant, the family dictionary, call story pages and the family list. **Recordings never leave the laptop** | cloud | `sync.py`, `people.py` |

---

## 4. Every feature we have

### A. On the call: the Chrome extension over WhatsApp Web
Turn it on with the toolbar button or Option+Shift+W. It shows **English and romanized Telugu only**; Telugu script
is filtered out on purpose, because the grandkid can't read it.

1. **Live captions:** her line in English at the bottom center, shown about as soon as the translator answers.
2. **Draft captions:** while she's still mid-sentence, a faded draft of the English updates every ~0.6 s, then the
   final line replaces it. Telugu puts the verb last, so drafts can change.
3. **English spoken in her own voice,** mixed over the call. Her real voice drops to 20% between lines and 5% while
   the English plays (both adjustable).
4. **The voice stays close to real time:**
   - a line is skipped (caption only) rather than spoken more than **3 s** late (**5 s** for questions to you);
   - the voice speeds up slightly to catch up;
   - it isn't spoken at all if she said it in English, or if the grandkid already knows every word in it.
5. **Words you know stay in Telugu:** "Today I made *pulihora*," underlined with the English in small text. Clicking
   the word means "I don't know this," and it's translated again from then on.
6. **"Ask her" questions:** a pill at the top center. It waits for a 2 s pause, stays at least 5 s, lasts 45 s, and
   comes at most every 25 s. Never right after she asked something, and each topic only once per call. It shows the
   question romanized plus its English meaning.
7. **The first question of a call** comes from the last call's "ask next time" list.
8. **Pictures:** pop up top right for about 2.5 s and fade. Never the same picture within 5 minutes, and never for
   words the kid already knows.
9. **Meaning cards:** proverbs, idioms, customs and English slang, explained. For example, *"Noru manchidaite ooru
   manchidi"* ("if your words are kind, the whole village is kind").
10. **"Asked you" and "Request" tags** on her questions and requests.
11. **How to answer her:** when she asks something, it offers a reply in respectful Telugu, like *"Avunu, tinnanu.
    Meeru tinnara?"* ("Yes, I ate. Did you eat?").
12. **Left panel, "Curious?":** up to 2 questions per line ("What is gavvalu?", "Who is NTR?", "Why do people say
    ___?"). Click one for the answer.
13. **Left panel, words:** words for the current topic (11 topics). The topic only changes when 2 of the last 3
    lines agree, so it doesn't flicker. Words she's used that you're still learning come first. A button plays each
    word, using the browser's built-in voice.
14. **Controls:** a line at the bottom that moves with what Weave is doing (listening, translating, speaking), and
    buttons to hide the words or pictures.
15. **Transcribe switch:** off means no audio goes to the cloud, nothing is recorded, and the call plays at full
    volume.
16. **English / Telugu switch** (for two-way calls): says which language you speak, and is remembered.
17. **Warnings on screen:** no sound from the call for 15 s, or the Mac volume below 100%.

### B. Two-way (`--two-way`): grandma hears the grandkid in Telugu
18. **Works out who speaks Telugu** from what each person says, or you set it with the switch or
    `--telugu-speaker`.
19. **Your English → Telugu speech** into WhatsApp Web's microphone (BlackHole 16ch).
20. **Turn-taking:**
    - a translation waits while its listener is talking;
    - it fades out if they interrupt;
    - it's dropped if it can't start within 10 s.
21. **Echo removal:** a line from your mic that matches what just played is dropped. On laptop speakers, a
    walkie-talkie mode ignores your mic while anything is playing.
22. **Lines are redone** if the roles turn out to have been guessed wrong (the last 12 s).
23. **Learns from your replies** (two-way only, since it needs your mic):
    - **saying one of her words yourself** is strong evidence you know it;
    - **your reply to a word kept in Telugu** is judged understood, not understood, or no signal. Rules handle the
      clear cases, then **our trained Laya head**, then Muse Spark as a rare tie-breaker (at most 12 times a call).

### C. Learning: which words stay in Telugu (`progress.py`)
24. **A probability that you know each word:** Bayesian Knowledge Tracing with forgetting.
    - **Starting guess by kind of word:** everyday family words 95%, other family 35%, festivals and phrases 25%,
      food, places and clothing 20%, everyday words 15%, customs 10%, proverbs 2%.
    - **Learning events** (`p += (1−p) × chance`): heard with its meaning 20%, its picture 15%, asked and read the
      answer 30%, played it 10%, said it yourself 20%.
    - **Evidence (Bayes' rule):**
      - asked "what does it mean": pushes it down hard;
      - clicked a kept word: pushes it down hard;
      - left a kept word unclicked for 20 s: nudges it up;
      - said it yourself: pushes it up hard;
      - reply shows you understood: up;
      - reply shows you didn't: down.
    - **Forgetting between calls:** a 7-day half-life. It doubles when you show you remember (up to 60 days) and
      halves when you don't (down to 1 day).
    - **Cramming doesn't count:** hearings within 45 s count once. Not clicking counts once per word per call.
    - **When a word stays in Telugu:** at 70% (`--keep-at`; use 0.4 for a demo, so it happens on the second mention).
    - **Everything is logged,** so the settings can be fitted to real quiz results (`tools/quiz.py`,
      `tools/fit_progress.py`). The current numbers are our own estimates.

### D. After the call: the story keeper (`calls.py`)
25. **Records her side only.** Your mic is never recorded, and the recording can be turned off with `--no-record`.
26. **The story page opens when you hang up.** It has:
    - a title, and a summary in English and in Telugu;
    - **the stories she told,** each with her voice clips;
    - highlights;
    - the pictures that came up;
    - the words from this call (new, learning or known);
    - the questions suggested during the call, and **3 to ask next time**;
    - a **Telugu message to send her,** with a copy button;
    - the whole call, line by line, with her voice on each line.
27. **Family dictionary:** every Telugu word ever heard on calls, with **her voice saying it**, from the first call
    it came up in.

### E. The iPhone app
28. **First launch asks your name,** which adds you to the family list (synced to the team's laptops through
    Firebase). "Not you?" in Settings switches person.
29. **Progress tab:** a glowing plant that grows from a bud into a tree as you meet and learn words. Also: hearings,
    a daily streak, a week chart, how many words you know, and recent changes ("X is now known").
30. **Words tab:** the family dictionary, searchable in Telugu or English. Each word has its picture, meaning,
    pronunciation, **her voice clip**, and "Didn't know it."
31. **Voice tab:** read a script for about a minute and tick the consent box. The Mac creates your ElevenLabs voice,
    and your translations are spoken in it, in English and in Telugu. "Record again" and "Remove" (which deletes it
    at ElevenLabs too).
32. **Settings:**
    - record a family member's voice, with their consent;
    - the Mac's address;
    - **demo mode** (sample words and a scripted call, no Mac needed).
33. **Home-screen widget:** "Next call: ask…", using the last call's questions, rotating every 3 hours.

### F. Privacy
34. **The engine only accepts our own pages** (the extension and pages on this Mac). Other websites, even WhatsApp's,
    are refused.
35. **Recordings, clips and voice samples stay on the laptop.** Firebase gets text only.
36. **The keys stay on the Mac;** the phone never sees them.

---

## 5. Where we are right now (be honest about this)

**Checked on our Macs**
- Both translation directions and the Telugu voice work. On the 8 GB Mac: "నువ్వు అన్నం తిన్నావా?" → "Do you have
  you eat?", and "Yes, I had pizza for dinner." → Telugu.
- Firebase and the ElevenLabs key connect.
- `tools/check_decisions.py` runs the demo lines through the real engine: captions, pictures, questions and kept
  words all come out.
- `tools/check_two_way.py`: **13/13** on the team's 24 GB Mac (per the team), and **11/13** on the 8 GB Mac. The two
  failures were a translation timing out and a line dropped for being late, both from lack of memory.

**Laya, re-measured today** (`tools/eval_laya.py`, on lines the team wrote and labelled, plus a held-out call)

| Decision | Laya alone | Rules, then Laya |
|---|---|---|
| Topic (11 options) | 42/66 = 64% | 60/66 = **91%**; held-out call 9/10 |
| What she's asking you (to offer a reply) | 21/27 = 78% | 26/27 = **96%** (no reply offered when unsure) |
| Question / request / statement | — | 64/66 = **97%** |

- **Speed depends on the Mac.** Today's run on the 8 GB Mac: median ~0.7 s per line. On the 24 GB M4, the team
  measured median 52 ms. Run the demo on the 24 GB Mac.
- **The reply check** (trained head): when it's at least 98% sure, 88% of its conclusions were right on held-out
  words (92 of 226 replies), per the code's notes. It was retrained today. We couldn't re-run `tools/check_reply.py`
  on the 8 GB Mac (out of memory).

**Speed, as the team measured on the 24 GB M4 (`overview.md`); re-measure on the demo Mac**
- Her sentence → English on screen: **~0.4–0.6 s**
- Her sentence → her voice: **median ~0.55–0.7 s**
- The speech service's own fixed delay: **~0.7 s**
- On the 8 GB Mac the log shows much worse numbers (voice ~5 s), because it's swapping memory.

**Not done or not checked yet**
- **The extension on a real WhatsApp Web call:** the team's notes say only a preview page was tested. **Test this
  first.**
- **Two-way on a real call** (only scripted tests so far).
- **Grandma's consent:** her side is recorded for the story page and her voice is cloned from the call, with no
  consent step. Voices recorded in the iPhone app do have one.
- **The iPhone app's live-call and past-calls screens** exist in the code but **can't be reached** from the current
  tabs (Progress, Words, Voice). Don't promise them.
- **Two different progress measures:**
  - the plant and the Progress tab count **hearings** (a word is "in bloom" after 8);
  - the captions and the Words tab use the **knowledge model** above.

  They can disagree. If asked, "known" in the Words tab is the real model.
- **Only Telugu has a word list and pictures.** The code accepts Hindi, Tamil, Kannada, Malayalam, Bengali and
  Marathi, but they'd need their own.

---

## 6. What to demo, and what to leave out
A judge told us to show a few things well, not everything. Pick **four moments**:

| # | Moment | Features it shows | Why this one |
|---|---|---|---|
| 1 | **She speaks, you understand her in her own voice** | captions, drafts, her voice | The core problem, solved in 5 seconds |
| 2 | **A picture, then "Ask her" → she tells a story** | picture, "Ask her" in Telugu | The human-connection moment: the AI gets *her* talking |
| 3 | **A word stays in Telugu** | the knowledge model, the fade-out | What makes us different: less translation over time |
| 4 | **Hang up: her story, in her voice** | story page, family dictionary, iPhone Words tab | Something the family keeps |

**Leave out of the live demo** (mention in one line, or save for questions):
- two-way (the riskiest audio setup, never tested on a live call);
- the "Curious?" panel and topic words;
- the reply-in-Telugu helper;
- the Transcribe switch;
- the widget, demo mode, the plant animation;
- Firebase sync, the reply check.

---

## 7. Demo setup (on the 24 GB Mac)
1. **Sound:** System Settings → Sound → Output → **BlackHole 2ch**, volume **100%**. Headphones on.
2. **Terminal 1, the engine:**
   ```
   .venv/bin/python subtitles.py --caller Ammamma --me <your name> --out "<headphones>" --original-volume 0.6 --duck-volume 0.15 --speak telugu --keep-at 0.4
   ```
   Wait for "Overlay: http://localhost:8765" and "listening".
3. **Terminal 2, for the iPhone app:** `python3 -m garden`. Open the app in the Simulator, on the **Words** tab.
4. **The call:** in Chrome, open the **WhatsApp Web** call (not the Mac app) and turn Weave on with **Option+Shift+W**.
5. **Grandma** reads one line at a time and pauses about 2 s after each.
6. **Backup:** a screen recording of a good full run, in case the audio fails at the table.

---

## 8. The demo script (about 3 minutes)

**[0:00, hook, before the call]**
> "My grandmother only really speaks Telugu. I don't. For years our calls were 'Did you eat?', 'Yes', 'Okay, bye.'
> That's millions of families. So we built Weave."

**[0:15, Moment 1, understanding her]**
Grandma: **నాన్నా, బాగున్నావా? అన్నం తిన్నావా?** (*Nanna, bagunnava? Annam tinnava?*)
> "Grandma's on her normal WhatsApp. She installed nothing. On my laptop, Meta's Muse hears her live, and I get the
> English, spoken in *her* voice, not a robot's."

**[0:40, Moment 2, a picture, then "Ask her"]**
Grandma: **ఈ రోజు నీ కోసం పులిహోర చేశాను.** (*Ee roju nee kosam pulihora chesanu.*, "Today I made pulihora for you.")
*(Keep this line a statement. "Ask her" never appears right after she asks a question. Run it through
`tools/check_decisions.py` once to confirm the picture and the prompt come up.)*
> "Pulihora: I'd never know what that is. Weave shows me."

Wait for the pause. **"Ask her"** comes down: *"Pulihora ela chestaru? Naaku nerpistara?"*
> "And here's the part we care about most. Weave doesn't explain her life to me. It gives me a question to ask her,
> in Telugu."

Grandkid asks it out loud. **Grandma answers with a short story** (how she learned to make it).
> "The AI didn't tell that story. It got her to tell it."

**[1:40, Moment 3, a word stays in Telugu]**
Grandma: **పులిహోర చాలా బాగా వచ్చింది.** (*Pulihora chala baaga vachindi.*)
> "Look at the caption: *pulihora* stayed in Telugu. Weave tracks how likely I am to know each of her words, with a
> learning model and forgetting between calls. Once I know a word, it stops translating it. If I don't, I click it
> and it comes back."

**[2:10, Moment 4, hang up]**
Grandkid: *"Tvaralo vastanu, Ammamma"* ("I'll come soon"). Then press Ctrl+C.
> "When we hang up, the call becomes a page for our family: the story she told, in her real voice, and a message in
> Telugu I can send her."

Show the story page, then the iPhone **Words** tab: tap *pulihora* and play her voice.
> "And every word she's taught me is in our family dictionary, in her voice."

**[2:40, how it works, in one breath]**
> "Meta's Muse hears her and writes the questions and her story. Laya, a small model on the laptop, makes the quick
> call on every line (is she asking me something, which picture, what to ask), and gets topics right 91% of the
> time with our rules."

**[2:55, close]**
> "Most translators get better at translating. Weave gets better at knowing when not to."

---

## 9. Likely judge questions
- **"Does grandma understand the grandkid?"** Yes, with `--two-way`: the grandkid's English reaches her as spoken
  Telugu (a local translator plus Meta's MMS voice, or the grandkid's own voice), with turn-taking and echo removal.
  It's been tested with scripted calls, not a live call yet.
- **"What if Meta's speech service goes down?"** It reconnects automatically. There's no offline speech backup
  today; our first version used local Whisper, and we replaced it with Muse. Translation does have a backup: the
  local model, with Muse Spark if it's slow or down.
- **"Why Laya and not just an LLM?"** The decisions are needed on every line, instantly and on the laptop. Rules plus
  Laya: topics 91%, questions/requests/statements 97%. We also trained our own Laya head to judge whether the kid
  understood a word from their reply.
- **"How do you know they learned a word?"** Bayesian Knowledge Tracing with forgetting and spaced repetition (§4C).
  The settings are our estimates until we fit them to real quizzes (the tools are built).
- **"Privacy?"**
  - Recordings stay on the laptop.
  - Only our own pages can connect to the engine.
  - There's a Transcribe switch.
  - Personalized voices are opt-in, with consent, and removable.
  - Next on our list: a consent step for grandma's own recording.
- **"Other languages?"** The pipeline supports six more Indian languages. Telugu is the only one with a word list
  and pictures.

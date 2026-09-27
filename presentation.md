# Weave: presentation and demo guide

Everything we need for the video demo, the live demo and judges' questions: what Weave is, every feature, how it
teaches, how the AI builds connection, what's original, the numbers, and the scripts. The details come from the code
and from [writeup.md](writeup.md), [idea.md](idea.md), [overview.md](overview.md) and [demo.md](demo.md).

---

## 1. The one-liner
> **Weave lets kids of immigrant families actually talk to their grandparents: understand her live, learn her
> language from her, get her telling stories, and keep those stories forever.**

- Grandma changes nothing. She stays on WhatsApp (or Instagram) on her phone.
- The grandkid takes the call in Chrome on their laptop, with Weave on top.

**Closing line:** *"Most translators get better at translating. Weave gets better at knowing when not to."*

---

## 2. The problem
- **The calls shrink.** Millions of kids of immigrants call their grandparents, and the calls shrink to
  *"Annam tinnava?"* ("Did you eat?"), "How's school?" and "bye." It's not that they don't care. The grandkid lost
  the language.
- **Translation apps don't fix it.** You depend on them forever, they get cultural meaning wrong (a proverb comes out
  as nonsense), and nothing from the call is kept.
- **Language apps don't fix it either.** They teach generic words, not the words *your* grandmother uses.
- **It's urgent.** Grandparents are aging. Their stories, recipes, sayings and family history disappear if nobody can
  understand them.

**Who it's for:** kids of immigrant families, starting with Telugu-speaking grandparents.

---

## 3. Every feature

### During the call: the Chrome overlay on WhatsApp Web
| Feature | What it does | Example |
|---|---|---|
| **Live English captions** | Her Telugu becomes English about 0.5 s after each sentence | *"నాన్నా, బాగున్నావా?"* → "Nanna, are you doing well?" |
| **Draft captions** | A faded draft of the English appears 2–3 s *before* she finishes. Telugu puts the verb last, so the final line replaces the draft | |
| **English in her own voice** | Her cloned voice speaks the English (ElevenLabs, or Pocket TTS on the laptop), so it still sounds like *her* | |
| **Words you know stay in Telugu** | Once the grandkid knows a word, the captions and voice keep it in Telugu | "Today I made *pulihora*." |
| **Pictures** | Pop up for things she mentions that an American kid might not know. 213 built in, ~2,000 downloadable ahead of time, Wikipedia as a fallback, never the same one within 5 min | gavvalu, Bhogi bonfire, NTR |
| **Meaning cards** | Proverbs, idioms, customs and slang explained | *"Noru manchidaite ooru manchidi"*: literal "if the mouth is good, the town is good" → *if your words are kind, the whole village is kind* |
| **"Ask her" prompts** | At her pauses, one question for the grandkid to ask *her*, in Telugu with pronunciation. At most one every 25 s, never right after she asked something | *"Meeru, Thatayya ela kalisaru?"* ("How did you and Thatayya meet?") |
| **How to answer her** | When she asks you something, it shows how to reply in Telugu | *"Avunu, tinnanu. Meeru tinnara?"* ("Yes, I ate. Did you eat?") |
| **"Curious?" questions** | Questions the kid might want to ask the app, filled from what she said. Click for a kid-friendly answer using the call's context | "What is gavvalu?", "Who is NTR?", "Why do people say ___?" |
| **Topic words panel** | Words for what you're talking about (11 topics), each with pronunciation and a button to hear it | Food: *annam* (rice), *kura* (curry) |
| **"Asked you" / "Request" tags** | So the kid never misses that she asked them something | |
| **Transcription on/off switch** | Stops all audio going to the cloud and all recording, and brings the call back to full volume | |

### Both directions (`--two-way`)
- **It works out who speaks Telugu** on its own.
- **The grandkid's English reaches her as spoken Telugu:** IndicTrans2 English → Telugu on the laptop, then Meta's MMS
  Telugu voice, or the grandkid's own ElevenLabs voice if they recorded one.
- **Turn-taking is handled:**
  - a translation **waits while the listener is talking**;
  - it **fades out if they interrupt**;
  - it's **dropped as echo** if it matches what just played on the speakers.
- **Pictures for her:** it can show American things the kid mentions (Thanksgiving, s'mores, prom).

### After the call
- **Story page** (made by Meta Muse Spark in about 30 s). It has:
  - the stories she told;
  - **clips of her real voice for every line**;
  - the pictures;
  - the words from the call;
  - questions to ask next time;
  - **a Telugu message to send her**.
- **Family dictionary:** every word the grandkid has heard, *in her voice*.

### Between calls: the web app and the iPhone app
- **Bloom:** a plant that grows from a bud into a tree as the grandkid learns her words.
- **Past calls:** each with its story and her voice on every line.
- **Progress** on each word.
- **"Ask next time" questions,** also on an **iPhone home-screen widget** ("Next call: ask how she makes pulihora").
- **"Float over call":** a small caption window that stays on top of the WhatsApp window.
- **Personalized voices:** someone records for about a minute and agrees to a consent line. Their ElevenLabs voice is
  created and shared with the family's laptops through Firebase.
- **The family list:** synced between laptops through Firebase.

---

## 4. How Weave teaches (our specific methods)

### 4.1 A real learning model, not a counter
Every word has a **probability that the grandkid knows it** (`progress.py`). It's based on **Bayesian Knowledge
Tracing**, the model tutoring software uses, with forgetting added.

**Starting guess, by kind of word**
| Kind of word | Starting guess |
|---|---|
| Family words everyone knows (Amma, Ammamma) | 95% |
| Other family words | 35% |
| Festivals | 25% |
| Foods and places | 20% |
| Everyday words | 15% |
| Proverbs | 2% |

**Learning events.** Each gives a chance they learned it: `p = p + (1 − p) × chance`.
| Event | Chance they learned it |
|---|---|
| Heard it on the call with its meaning shown | 20% |
| Its picture popped up | 15% |
| Asked about it and read the answer | 30% |
| Tapped "hear it" in the words panel | 10% |
| Said it themselves | 20% |

**Evidence from what they do.** Bayes' rule, comparing how likely each action is if they know the word vs if they don't.
| Action | If they know it | If they don't | Effect |
|---|---|---|---|
| Asked "What does ___ mean?" | 10% | 70% | pushes it down hard |
| Tapped a kept word ("I don't know this") | 3% | 80% | pushes it down hard |
| Saw it in Telugu and didn't tap it for 20 s | 90% | 50% | nudges it up |
| Said it themselves on the call | 90% | 5% | pushes it up hard |

### 4.2 Spaced repetition and forgetting
- **Knowledge fades between calls,** back toward the starting guess, with a **7-day half-life** (most families call
  about weekly).
- **The half-life doubles** each time they show they still know the word (up to 60 days), and **halves** when they
  don't (down to 1 day).
- **Cramming doesn't count:** hearing a word again within 45 s counts as one hearing, because massed repetition teaches
  little and spacing does. Before this rule, everyday words reached "known" within one call.

### 4.3 The fade-out
- **When a word counts as known:** once it reaches **70%** (`--keep-at 0.7`), it stays in Telugu in the captions, the
  voice and the story page.
- **Example, *pulihora*:**
  1. 20% to start.
  2. First mention, with its picture: 46%.
  3. Then 56%, 65%, and on the 4th mention 72%, so it's kept in Telugu.
  4. Seen in Telugu and not tapped: 86%, and it's now remembered longer.
  5. If the kid taps it instead, it drops to 19% and is translated again.
- **Understood lines aren't voiced:** a line made only of words the kid knows ("Sare, sare") is captioned but not
  spoken, because they already understood her.

### 4.4 Learning from how the kid answers (a trained Laya head)
When grandma uses a Telugu word Weave kept, Weave judges the grandkid's reply (`reply.py`):
| Reply | Judgment |
|---|---|
| "Save me some mangoes" (after *mamidi*) | **understood** |
| "The coconut tree?", "her what?", "what does that mean?" | **didn't understand** |
| "Okay", "wow", "hold on, Mom's calling" | **no signal** |

- **How it decides:** rules handle the clear cases instantly (98–99% right where they apply). Laya handles the rest,
  with its own small decision head, trained for this question on top of Laya's shared encoder (`tools/train_reply.py`).
- **Accuracy:** when it's at least 80% confident, it's right 90% of the time on held-out words and 88% on a hand-written
  test (`tools/check_reply.py`).
- **Why it matters:** it measures actual comprehension, not just exposure.

### 4.5 Learning inside the relationship
- **Her words, not a textbook's:** the words come from *her*, on *your* calls, and the dictionary has *her voice*
  saying them.
- **Speaking, not just listening:** the reply and "Ask her" coaching get the grandkid *saying* Telugu.
- **Always respectful:** anything the grandkid might say to her is in the respectful form (*meeru*, *mimmalni*).

---

## 5. How generative AI drives the social connection
**The principle: the AI creates openings for grandma to talk. It doesn't talk for her.**

| AI feature | How it builds connection |
|---|---|
| **"Ask her" prompts** (Meta Muse Spark) | Turns "I made pulihora" into "How do you make it? Can you teach me?" She tells the story; the AI doesn't |
| **Replies in Telugu** | The grandkid answers *her*, in *her* language, in their own voice |
| **"Curious?" answers** (Muse Spark) | Explains things without interrupting her mid-story |
| **Story page** (Muse Spark) | Finds the stories she told and saves them in her voice, so the family keeps them |
| **Questions for next time, plus the widget** | The next call starts where the last one left off, not at "did you eat?" |
| **Her cloned voice** | Even translated, the kid hears *grandma*, not a robot |
| **A Telugu message to send her** | Carries the connection past the call itself |

---

## 6. Which AI does what (lead with Meta for the Meta track)
| Job | Model | Where |
|---|---|---|
| Hear her Telugu (and the grandkid's English) live | **Meta Muse Voice Transcribe** | cloud, streaming |
| Telugu → English | IndicTrans2 1B, **raced against Meta Muse Spark** after 1.2 s | laptop / cloud |
| English → Telugu (`--two-way`) | IndicTrans2 English → Telugu 1B | laptop |
| English in her voice | ElevenLabs Flash v2.5, or Pocket TTS voice clone | cloud / laptop |
| Telugu voice for her | **Meta MMS** (`facebook/mms-tts-tel`), or ElevenLabs v3 in the grandkid's voice | laptop / cloud |
| Split-second decisions: question?, topic, which picture, which questions, which reply, did the kid understand | **Laya** | laptop, median 52 ms per line |
| "Ask her" prompts, "Curious?" answers, story pages, the message to her | **Meta Muse Spark** | cloud |

**The line to say:** *"Generative models create; Laya decides."* Laya makes 4–5 decisions per sentence on the laptop,
so the call stays fast and private. The cloud only runs where creativity matters: her voice, her stories and the
answers.

**Laya's measured accuracy** (`tools/eval_laya.py`)
| Decision | Laya alone | Our rules, then Laya | Muse Spark alone |
|---|---|---|---|
| What is the line about? (11 topics) | 64%, 0.13 s | **91%** (9/10 on a held-out call) | 95%, 1.0 s |
| What is she asking you? | 78%, 0.10 s | **96%** | 100%, 0.9 s |
| Question, request or statement? | — | **97%** | — |

- **The takeaway:** rules plus Laya get close to the cloud model's accuracy in about a tenth of the time, on the
  laptop, for free, without sending every line to the cloud.
- **Tests that shaped the design:**
  - Laya's English checkpoint beat the multilingual one.
  - Yes/no questions failed (9/14), so they became rules.
  - Picture choice by Laya alone was 14/25, so rules decide the obvious cases and Laya picks between candidates.

---

## 7. What's original
1. **A translator designed to be used less every call.** Success is how much of grandma the kid understands *without*
   help.
2. **An AI that asks questions instead of answering them.** It gets the grandparent telling stories.
3. **Measured learning:** Bayesian Knowledge Tracing, spaced forgetting, and a trained model that judges comprehension
   from what the kid says back.
4. **A family archive in her own voice,** produced automatically from normal calls.
5. **Cultural meaning, not literal words:** proverbs, customs and foods get meaning cards and pictures.
6. **Nothing changes for grandma:** no app and no setup, on the call she already makes.

---

## 8. Execution (the proof)

### Latency, measured on the 24 GB M4 MacBook Air
| Step | Time |
|---|---|
| Her sentence → English on screen | **~0.4–0.6 s** |
| Her sentence → her voice speaking English | **median 0.54–0.69 s**, max ~1 s |
| Draft captions | **2–3 s before she finishes** |
| Topic words, "Curious?", picture, "ask her" | **2–4 ms** after her line (decided from her Telugu, before the English is back) |
| Laya per line | median 52 ms, slowest 171 ms |
| "Curious?" answer | instant for word-list words; ~1.5 s from Muse Spark, then cached |
| Story page after the call | ~30 s |
| The speech service's own fixed delay | ~0.7 s (not adjustable) |

### Optimizations, each measured before and after
- **Voice first:** speaking before Laya and the picture lookup started the voice ~0.5 s sooner.
- **Streaming the cloned voice** phrase by phrase: another ~0.2–0.8 s.
- **Capping the voice model's GPU cache** at 256 MB: it had grown to ~2 GB and pushed translations to ~10 s.
- **A 1.2 s race against Muse Spark** for slow local translations.
- **Gentle catch-up speed** (up to 1.12×) when lines queue.

### Quality and testing
- **A 308-word Telugu glossary** for the translator.
  - Without it, *gangireddulu* (decorated bulls) became "the Ganges," and *gavvalu, sunnundalu* became "gavas, limes."
  - With it, they come out right.
- **Real WhatsApp Web calls** with a family member speaking Telugu, saved as story pages.
- **The whole pipeline, line by line, without audio** (`tools/check_decisions.py`): every demo line was checked, and
  the demo script corrected to what actually happens.
- **Two-way:** passes **13/13** scripted checks (`tools/check_two_way.py`) on the 24 GB Mac.
- **The Telugu voice** was checked by transcribing it back with Meta's Telugu transcription: nearly word for word.
- **Word content:** 308 Telugu words and proverbs, 46 English words, phrases by topic, and 213 pictures.

### Privacy and safety
- **The engine only talks to our own pages.** Other websites, even WhatsApp's, can't read the call.
- **Personal data stays on the laptop:** recordings, story pages, progress and voice samples are never committed.
- **Voice cloning for family members is opt-in,** with a consent line.
- **Transcription can be switched off** at any time.
- **The voice never falls far behind:** a line is skipped rather than spoken more than 3 s late (5 s for questions).
- **Warnings** if no sound reaches the app, or the Mac volume is below 100%.

---

## 9. How it deepens the connection, step by step
```
Understand her        →  Take part             →  Hear her stories   →  Keep them                →  Come back with more    →  Need less help
(captions, her voice,     (reply in Telugu,        (prompts at her       (story page, dictionary     (next-call questions,     (known words stay
 pictures, meanings)       "Ask her")               pauses)               in her voice)               widget, Bloom)            in Telugu)
```
Each call makes the next one deeper. The goal is a grandkid who, in a few months, can talk with their grandmother
without Weave.

---

## 10. The pitch (about 60 seconds)
> *"Millions of kids of immigrants call their grandparents every week, and the calls stay shallow. 'Did you eat?
> How's school? Okay, bye.' Not because they don't care, but because they lost the language.*
>
> *Translation apps can tell you what a sentence means. They can't tell you that pulihora is the dish your grandmother
> made every festival, or that this is the moment to ask her about it.*
>
> *Weave runs on the WhatsApp call you already make. You hear her in English, in her own voice. It shows you what
> she's talking about, explains her sayings, tells you how to answer her in Telugu, and at every pause suggests a
> question that gets her telling a story. When you hang up, the call becomes a page for the family, with her stories
> in her voice.*
>
> *And every call, it translates a little less. It tracks which words you know, and those stay in Telugu. You're
> learning your grandmother's language from your grandmother.*
>
> *Most translators get better at translating. Weave gets better at knowing when not to."*

---

## 11. Video demo script (2–3 minutes)
| Time | On screen | Voiceover |
|---|---|---|
| 0:00 | Personal photo or old call | "My grandmother only really talks in Telugu. I don't. Our calls used to be 'did you eat?' and 'bye.'" |
| 0:15 | Line 1: captions, her voice, "Asked you" tag, the Telugu reply | "Weave runs on the WhatsApp call I already make. I hear her in English, in her own voice, and it tells me how to answer in Telugu." |
| 0:40 | Lines 2–4: gavvalu picture, *pulihora* kept in Telugu | "It shows me what she's talking about, and once I've learned a word, it stops translating it." |
| 1:10 | Line 6: the proverb card | "Word-for-word translation misses this. Weave gets the meaning." |
| 1:30 | Line 7: "Ask her: how did you and Thatayya meet?", then she tells the story | "At every pause it gives me a question to ask her, so she tells me the story instead of me just listening." |
| 2:00 | Hang up: story page, her voice clips, dictionary, Bloom | "When we hang up, the call becomes a page for the family, with her voice." |
| 2:20 | Model diagram | "Meta's Muse hears and writes; a small local model, Laya, makes five decisions per sentence in a fraction of a second, so the call stays fast." |
| 2:40 | Logo | "Most translators get better at translating. Weave gets better at knowing when not to." |

---

## 12. Live demo

### Setup (5 minutes before, on the 24 GB Mac)
1. **Sound:** Mac output = **BlackHole 2ch**, volume **100%**, and **headphones** on so the English voice doesn't echo
   back to the phone.
2. **Chrome extension:** loaded from `extension/` (see [extension/README.md](extension/README.md)).
3. **Start the engine:**
   ```
   .venv/bin/python subtitles.py --out "<headphones>" --caller "Ammamma" --me "<your name>" --original-volume 0.6 --duck-volume 0.15 --speak telugu --keep-at 0.4
   ```
   `--keep-at 0.4` keeps a word in Telugu from its second mention, so the learning shows within one call.
4. **Wait** for `Overlay: http://localhost:8765` and "listening."
5. **Start the app server:** `python3 -m garden`. Open **http://localhost:8770/app**, and the iPhone app or Simulator
   if we're showing it.
6. **Start the call:** open the WhatsApp Web call in Chrome and turn Weave on (toolbar button, or **Option+Shift+W**).
7. **Grandma:** speaks clearly, one line at a time, and pauses about 2 s after each line.
8. **Backup:** have a screen recording of a good run ready. If live audio fails at the table, play it.

### The call script
| # | Grandma says (Telugu) | How to say it | What shows up | Grandkid does | Presenter says |
|---|---|---|---|---|---|
| 1 | నాన్నా, బాగున్నావా? అన్నం తిన్నావా? | *Nanna, bagunnava? Annam tinnava?* | English in her cloned voice; **Asked you** tag; left: *How do I say "Yes, I ate. Did you eat?"* and *What does "annam tinnava" mean?*; words: **Saying hello** | Clicks the reply and says it: *"Avunu, tinnanu. Meeru tinnara?"* | "It tells me she asked me something, and how to answer her in Telugu." |
| 2 | నిన్న సంక్రాంతికి గవ్వలు, అరిసెలు చేశాను. | *Ninna Sankranti ki gavvalu, ariselu chesanu.* | **gavvalu** picture; *What is gavvalu?*, *What is ariselu?*; words switch to **Food and cooking**; at the pause: **Ask Ammamma about Gavvalu**: *"Gavvalu ela chestaru? Naaku nerpistara?"* | Clicks *What is gavvalu?* (the answer shows at once) | "Pictures for what I wouldn't know, and the words change with the topic." |
| 3 | ఈ రోజు పులిహోర చేశాను, నీకు చాలా ఇష్టం కదా? | *Ee roju pulihora chesanu, neeku chala ishtam kada?* | **pulihora** picture; *How do I say "Yes, I like it a lot"* → *"Avunu, naaku chala ishtam"* | Says it | |
| 4 | పులిహోర చాలా బాగా వచ్చింది. | *Pulihora chala baaga vachindi.* | The caption now keeps **pulihora** in Telugu; at the pause: **Ask Ammamma about Pulihora**: *"Pulihora ela chestaru?"* | Asks her, in Telugu | "I just learned *pulihora*, so it stopped translating it." |
| 5 | మా చిన్నప్పుడు భోగి మంటలు వేసేవాళ్ళం, గంగిరెద్దులు ఇంటికి వచ్చేవి. | *Maa chinnappudu Bhogi mantalu vesevallam, gangireddulu intiki vachevi.* | **Bhogi** picture; **gangireddu** custom card; words switch to **Festivals and temple**; *What is gangireddu?*, *What does "chinnappudu" mean?* | Clicks *What is gangireddu?* | |
| 6 | నోరు మంచిదైతే ఊరు మంచిది అని మా అమ్మ చెప్పేది. | *Noru manchidaite ooru manchidi ani maa amma cheppedi.* | Literal caption ("if the mouth is good, the town is good"); the card gives the meaning: *if your words are kind, the whole village is kind* | Points at the card | "Word-for-word translation misses this. Weave gets the meaning." |
| 7 | మీ తాతయ్య ఎన్టీఆర్ సినిమాలు చాలా ఇష్టపడేవారు. | *Mee thatayya NTR cinemalu chala ishtapadevaru.* | **NTR** picture; *Who is NTR?*; at the pause: **Ask Ammamma: "Meeru, Thatayya ela kalisaru?"** (How did you and Thatayya meet?) | Asks it | **"This is the moment Weave is about: the AI doesn't tell the story, it gets her to."** |
| 8 | ఎప్పుడు వస్తావు నాన్నా? జాగ్రత్తగా ఉండు, బాగా చదువుకో. | *Eppudu vastavu nanna? Jagrattaga undu, baaga chaduvuko.* | **Request** tag; *How do I say "I'll come soon"* → *"Tvaralo vastanu"* | Says *"Tvaralo vastanu, Ammamma"*, then hangs up | |
| 9 | (the call ends) | | Stop `subtitles.py` (Ctrl+C): the **story page** opens with her stories, her voice clips, pictures, words and questions for next time | Shows the story page, the family dictionary and Bloom | "Every call becomes something the family keeps, in her voice." |

"Ask Ammamma" questions come at most every 25 s (`--prompt-every`), at her pauses, so with about 10–15 s per line they
appear after lines 2, 4 and 7.

### If something goes wrong
| Problem | Fix |
|---|---|
| No captions | Mac volume must be 100%, output BlackHole 2ch, and the call in **WhatsApp Web** (the WhatsApp Mac app bypasses BlackHole) |
| Overlay missing | Reload the WhatsApp tab and turn Weave on again (it's off after every reload) |
| Voice lagging | Keep going. Captions stay live, and late lines are skipped on purpose |
| Anything else | Switch to the backup screen recording |

---

## 13. What to cover (checklist)
- [ ] The personal problem (the "did you eat? bye" call)
- [ ] Grandma changes nothing
- [ ] Live captions and her own voice, with the speed numbers
- [ ] Pictures and meaning cards (the proverb)
- [ ] Reply in Telugu, and "Ask her" → she tells a story
- [ ] Words staying in Telugu, and the learning model behind it (BKT, forgetting, reply check)
- [ ] The story page, the dictionary in her voice, the message to send her
- [ ] Bloom, the widget, next-call questions
- [ ] Two-way (her side hears the grandkid in Telugu)
- [ ] Which AI does what: Meta Muse Voice Transcribe, Muse Spark, MMS, and Laya with its accuracy table
- [ ] Privacy: local-first, opt-in voices, the transcription switch
- [ ] The closing line

---

## 14. Judges' questions: prepared answers
- **"How is this different from Google Translate?"**
  - It's built to be used *less*: known words stay in Telugu.
  - It explains cultural meaning.
  - It gets grandma telling stories.
  - It keeps them in her voice.
- **"How does grandma understand the grandkid?"**
  - With `--two-way`, the grandkid's English reaches her as spoken Telugu, and turn-taking is handled.
  - Weave also coaches the grandkid to answer in Telugu themselves, which is what she'll care about most.
- **"Why Laya instead of just an LLM?"**
  - Rules plus Laya reach 91–97% accuracy in ~50 ms on the laptop.
  - The cloud LLM is ~95–100% but ~1 s per line and an API call each.
  - Per-sentence decisions have to be instant, so generative models run only where creativity matters.
- **"What do the Meta models do?"**
  - Muse Voice Transcribe hears her live.
  - Muse Spark writes the prompts, answers, stories and backup translations.
  - MMS gives her the Telugu voice.
- **"How do you know they learned a word?"**
  - Bayesian Knowledge Tracing with forgetting and spaced repetition.
  - Evidence from taps, questions and saying it.
  - A trained Laya head that judges understanding from the kid's reply (88–90% when confident).
- **"Privacy?"**
  - Local-first: recordings, stories and progress stay on the laptop.
  - The engine only answers our own pages.
  - Voice cloning is opt-in, and transcription can be switched off.
- **"Consent for grandma's voice?"**
  - Family voice cloning has a consent step.
  - An explicit consent step for her story-page recordings is next on our list.
- **"Other languages?"**
  - The pipeline supports Hindi, Tamil, Kannada, Malayalam, Bengali and Marathi.
  - Telugu is the only one with a word list and pictures so far.
- **"Does it work on a real call?"**
  - Yes: real WhatsApp Web calls, saved as story pages.
  - Two-way passes 13/13 scripted checks.

---

## 15. Before we present: open items to check
- [ ] **Test the extension on a real WhatsApp Web call** on the demo Mac. `overview.md` lists this as not yet tested
      (only the preview page was).
- [ ] **Test `--two-way` on a real call** with BlackHole 16ch. The scripted check passes; a live call hasn't been run.
- [ ] **Record a backup** screen recording of a good full run.
- [ ] **Update `writeup.md`'s "What's next":** it still says the grandkid's Telugu voice is a stock voice, but ElevenLabs
      personalized voices now cover that.
- [ ] **Decide how to answer consent** for grandma's recordings and cloned voice (see above).
- [ ] **Run the demo on the 24 GB Mac.** 8 GB Macs swap and get several seconds slower.

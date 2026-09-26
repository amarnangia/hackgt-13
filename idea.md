# Weave: the idea (v2)

## One line
Weave is an overlay on the WhatsApp or Instagram video call page in Chrome. It lets a grandkid understand their
grandparent's Telugu live, learn her words as they talk, and ask about anything they didn't get without interrupting
the call.

## Who it's for
Kids of immigrant families who can't really talk to their grandparents in their language. Grandma stays on her phone
with WhatsApp or Instagram as usual; she installs nothing. The grandkid takes the call on their laptop in Chrome, with
Weave on top.

## What's on the screen
The call stays in the middle, untouched. Weave adds two side panels and captions:

```
┌──────────────────────────── WhatsApp / Instagram call in Chrome ────────────────────────────┐
│ LEFT: learn                │                                   │ RIGHT: see and understand     │
│                            │                                   │                               │
│ ❓ Curious?  (Laya)         │                                   │ 🖼  Gavvalu                    │
│  • What does "gavvalu"     │          her video                │    [picture]                  │
│    mean?                   │                                   │    Little shell-shaped fried  │
│  • What is Bhogi?          │                                   │    sweets for festivals       │
│  • How do I say "I miss    │                                   │                               │
│    you" in Telugu?         │                                   │ 💬 "Noru manchidaite ooru      │
│   (click → answer)         │                                   │    manchidi"                  │
│                            │                                   │    If your words are kind,    │
│ 📚 Words for: Food  (Laya)  │   ┌───────────────────────────┐   │    the whole village is kind  │
│  annam · rice              │   │ నిన్న గవ్వలు చేశాను         │   │                               │
│  kura · curry              │   │ Yesterday I made gavvalu  │   │                               │
│  tinnava? · did you eat?   │   └───────────────────────────┘   │                               │
└────────────────────────────┴───────────────────────────────────┴───────────────────────────────┘
```

### Middle: captions (what we have now)
- Her Telugu becomes English about 0.5 s after each sentence, shown under the video.
- Optionally spoken in English, in her cloned voice.
- Words you already know stay in Telugu ("Today Ammamma made *pulihora*").

### Left, top: "Curious?" questions (Laya + an LLM)
Questions the grandkid might want to ask *the app* about what was just said. Each is a sentence stem with a blank,
filled from the conversation:

| Stem | Filled from | Example |
|---|---|---|
| What does "___" mean? | Telugu words and phrases she used | What does "gavvalu" mean? |
| What is ___? | foods, things, places, festivals she mentioned | What is Bhogi? |
| Who is ___? | people she mentioned (NTR, Ghantasala) | Who is Ghantasala? |
| Why do people say "___"? | proverbs, blessings, customs | Why do people say "annam tinnava"? |
| How do I say "___" in Telugu? | what the grandkid might want to reply | How do I say "I miss you" in Telugu? |

- **What Laya does here:**
  - Candidates come from each line: word-list matches, proverbs, picture candidates and nouns.
  - For each candidate, Laya picks which stem fits.
  - Laya then ranks the candidates to choose the 3 most worth asking.
  - This is multiple choice with no text generation, on the laptop, in about 0.1 s.
- **On click, an LLM (Meta Muse Spark) answers.**
  - It gets the last few lines of the call as context.
  - The answer is 2–3 kid-friendly sentences, plus the Telugu word and how to say it.
  - For words already in our word list, the answer appears instantly from the list's note, and the LLM only adds more on request.
- The list stays short (3–4 questions), with the newest first, and old questions fade.

### Left, bottom: vocab for the current topic (Laya)
Words that change with what the conversation is about.

- **Laya picks the topic** for each line:
  - greetings
  - food and cooking
  - family
  - festivals and temple
  - health
  - school and work
  - travel and places
  - home and village
  - weather
  - feelings
  - plans and visits
- **The panel doesn't flicker.** It only switches when the same topic wins 2 of the last 3 lines.
- **Each word shows** its Telugu script, how to say it, the English, and a button to hear it.
- **Words she actually said in this call** are pinned at the top of the panel.
- **The call starts on greetings:** namaskaram, bagunnava? (are you well?), annam tinnava? (did you eat?), avunu (yes), sare (okay).
- **The words come from** our word list (308 Telugu entries), each tagged with a topic.

### Right: pictures and meanings (what we have now)
- **Pictures** of things she mentions: 213 built in, plus Wikipedia lookups.
- **Cards for idioms, proverbs, slang and customs,** with what they mean.
- The newest card goes on top, with at most 3–4 showing, and they fade after a while.

## How AI is used
| Job | Model | Where |
|---|---|---|
| Hear her Telugu | Meta Muse Voice Transcribe | cloud, streaming |
| Translate Telugu → English | IndicTrans2 1B, raced against Meta Muse Spark when slow | laptop / cloud |
| Speak the English in her voice (optional) | Pocket TTS voice clone | laptop |
| Pick the stems, rank questions, pick the topic, choose pictures, spot questions to you | **Laya** | laptop, about 0.1 s each |
| Answer a "Curious?" question | Meta Muse Spark | cloud, on click |
| After the call: story page, summary, questions for next time | Meta Muse Spark | cloud |

**The pitch line for AI:** *"Generative models create; Laya decides."* Every sentence gets 4–5 fast decisions on the
laptop (which questions, which topic, which picture, is she asking you something). The cloud LLM only runs when the
grandkid actually clicks.

## One standard for everything
- **One engine.** `subtitles.py` hears the call, translates it, and makes every decision.
- **One screen.** The Chrome extension draws the overlay on `web.whatsapp.com` and `instagram.com`. The subtitles page and the Weave app are only for debugging and backup.
- **One message format** over the engine's WebSocket (`ws://localhost:8765`):
  - **Existing:** `speaking`, `partial`, `original`, `english`, `details` (cards), `picture`, `prompt`, `warning`, `voice`.
  - **New:**
    - `curious` `{questions: [{id, stem, blank, text}]}`
    - `topic` `{topic, words: [{id, telugu, roman, english, heard}]}`
    - `answer` `{id, text, telugu?, roman?}`
  - **From the overlay back to the engine:** `ask` `{id}` (a click on a question) and the existing `forget` `{id}`.
- **Same audio setup** for both apps. The call plays in Chrome, the Mac's output is BlackHole 2ch at 100%, and the engine listens to BlackHole. So Instagram web calls work the same way as WhatsApp Web.

## What we keep, drop or move
- **Keep:** live translation, known words kept in Telugu, the cloned voice, pictures and cards, "Asked you" tags.
- **Keep, after the call:** the story page with her voice clips, and the family dictionary.
- **Decide:** the "Ask her about it" questions, which we ask *grandma*, overlap with "Curious?", which the grandkid asks *the app*. We could keep one "Ask her" item at the top of the left panel, or drop it.
- **Secondary:** the Weave app, the garden and the iPhone app. They're not part of the demo unless there's time.

## Open questions for the team
1. Right side = pictures and meanings, left side = questions and vocab. Is that right?
2. Is the answer to a "Curious?" question shown only in the left panel, or also spoken?
3. Do we keep "Ask her about it", and if so where does it go?
4. How big should the panels be, and should they collapse when the call is full screen?
5. Is Instagram a must for the demo, or only mentioned as supported?

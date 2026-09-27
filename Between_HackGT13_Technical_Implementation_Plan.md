# Between — HackGT 13 Meta Track
## Product + Technical Implementation Plan
### Built directly on the team's existing BlackHole + WhatsApp Desktop prototype

> **One-liner:** Between runs alongside a family call and helps two people who do not fully share a language understand each other now, while gradually helping them need less translation over time.

---

# 1. Product goal

Between is not meant to be “Google Translate with extra cards.”

The product goal is:

> **Make family conversations possible immediately, then use those same conversations to rebuild a shared language over time.**

The core problem is that many children of immigrants can technically call grandparents, parents, cousins, and relatives abroad, but the calls stay shallow because they do not share enough language. Translation apps can tell you what a sentence means, but they do not understand the relationship, the slang, the family-specific cultural context, or the fact that the long-term goal should be less dependence on translation.

Between should do four things extremely well:

1. **Understand now** — give the listener live enough translation to follow the conversation.
2. **Preserve meaning, not literal words** — recognize slang, idioms, family terms, and cultural references.
3. **Teach inside the relationship** — gradually reduce support for phrases the listener has learned.
4. **Create more human conversation** — use AI to surface context and generate prompts that encourage the family member to tell the story rather than letting the AI answer everything.

The success metric should be:

> **How much more of the conversation can these two people understand directly over time?**

---

# 2. Current project state

This plan intentionally builds on the project that already exists.

The teammate has already proven:

```text
WhatsApp Desktop
      ↓
BlackHole 2ch
      ↓
Python audio capture
      ↓
live audio meter responds to call audio
```

That is valuable. Audio routing on macOS is one of the riskiest parts of this project, so **do not rewrite it**.

The team also already has local Laya work:

- English checkpoint
- Apple MPS
- roughly 120–150 ms for the current typed questions
- English checkpoint performed better than the multilingual checkpoint for the current use case

Keep that too.

The immediate next milestone is:

```text
WhatsApp → BlackHole → existing Python stream
                    ↓
             Meta Muse STT
                    ↓
          live Telugu transcript
```

Do not add translation, images, TTS, or Muse Spark until that works reliably.

---

# 3. Is the idea technically feasible?

## Yes, if “real time” is implemented correctly

A system cannot reliably translate every syllable before enough meaning exists. Telugu and English do not always place information in the same order, and slang or idioms can change the meaning entirely.

Example:

> “My party was fire.”

A literal translation could communicate actual flames.

The intended meaning is:

> “My party was amazing.”

So translation is **not a deterministic word replacement problem**. A translation engine can use deterministic decoding, but the linguistic task itself is context dependent.

What is feasible is a layered experience:

```text
speaker talks
   ↓
source transcript appears live
   ↓
provisional English subtitle updates
   ↓
speaker finishes a short thought
   ↓
final English translation locks
   ↓
English TTS begins
```

The user should never stare at a frozen screen waiting for the entire AI pipeline.

---

# 4. Latency targets

Do not only measure:

```text
sentence start → English output
```

That metric is misleading because the sentence is still being spoken.

Measure:

```text
1. audio arrival → first STT partial
2. speech end → finalized transcript
3. finalized transcript → final English
4. final English → first TTS chunk
5. speech end → first translated audio
```

The desired demo experience is:

- source captions while speech is happening
- provisional English during or shortly after speech
- final English within hundreds of milliseconds after a short thought ends
- translated voice ideally starting in under about 1 second after the thought ends

That last number is a target. Benchmark it on the actual Mac and network.

If voice is slower, subtitles should still make the system feel live.

If dubbed audio starts falling several seconds behind, **drop dubbing for that turn and keep captions**. A good caption is better than stale speech.

---

# 5. Recommended architecture

```text
┌──────────────────── WhatsApp Desktop ────────────────────┐
│ live call audio                                          │
└────────────────────────┬─────────────────────────────────┘
                         ▼
                   BlackHole 2ch
                         ▼
              existing Python audio code
                         │
                         ▼
               Meta Muse Voice Transcribe
                  realtime WebSocket
                         │
        ┌────────────────┴────────────────┐
        │                                 │
   partial transcript               finalized turn
        │                                 │
        ▼                                 ├──────────────┐
   source subtitle                        │              │
        │                                 ▼              ▼
        │                          fast translator    Laya
        │                                 │         decision layer
        │                                 │              │
        │                                 └──────┬───────┘
        │                                        ▼
        │                                   PolicyEngine
        │                                        │
        │                ┌───────────────────────┼────────────────────┐
        │                │                       │                    │
        │                ▼                       ▼                    ▼
        │          Language Fade          Context Lens        Muse Spark
        │          learner state          image cards         when needed
        │                │                       │                    │
        └────────────────┴───────────────────────┴───────────┬────────┘
                                                             ▼
                                                  final subtitle / TTS
                                                             │
                                              ┌──────────────┴────────────┐
                                              ▼                           ▼
                                         overlay UI                  headphones
```

The architecture rule is:

> **Only the things necessary for comprehension belong in the critical latency path.**

Image cards, after-call recap, relationship prompts, and social context should run asynchronously.

---

# 6. Audio capture — keep the current implementation

## Use

- BlackHole 2ch
- `sounddevice`
- existing teammate audio code

The current audio meter proves that Python is receiving the call audio.

The next code change should expose reusable PCM chunks without breaking that meter.

Conceptually:

```python
AudioFrame(
    pcm: bytes,
    sample_rate: int,
    channels: int,
    timestamp: float,
)
```

The sounddevice callback should stay lightweight.

Do not:

- write temporary WAV files
- call external APIs inside the callback
- block the callback
- rebuild device routing unless necessary

Use a queue from the callback into async processing.

---

# 7. Realtime speech-to-text — Meta Muse Voice Transcribe

For the Meta track, this is where Meta technology should become foundational.

Use Meta Muse Voice Transcribe's realtime WebSocket.

Target configuration:

```text
model: muse-voice-transcribe-1.0
mode: ENDPOINTING
partial mode: CUMULATIVE
audio: mono signed int16 PCM
preferred sample rate: 24 kHz
language bias: Telugu + English
```

Why this is attractive:

- live partial transcripts
- built-in endpointing
- English/Telugu code-switching support
- sponsor alignment
- family/cultural keyword biasing

That lets us simplify the original plan:

```text
OLD:
BlackHole → VAD → STT

PREFERRED FIRST TEST:
BlackHole → Muse Voice Transcribe
```

Only reintroduce Silero VAD if Muse endpointing does not work well enough.

### Family vocabulary bias

Provide likely family/cultural terms at startup:

```text
Ammamma
Nanna
pappu
Hyderabad
Sankranti
family names
neighborhood names
```

This is likely more useful than adding another generic model.

---

# 8. Live partial captions

Muse partial transcripts should update the Telugu/Hinglish subtitle immediately.

If partials are cumulative:

```text
నేను
నేను నిన్న
నేను నిన్న మార్కెట్
```

replace the displayed line instead of appending each update.

Use `turnId` to track finalized turns.

This matters because multiple turns may overlap in the cleanup/finalization stages.

---

# 9. Translation layer

## Do not put Muse Spark in every sentence

The translation architecture should have two paths.

### Fast path

Ordinary speech:

```text
final / stable transcript
        ↓
dedicated Telugu ↔ English translator
        ↓
translation
```

### Context path

Slang, idiom, cultural meaning, ambiguity:

```text
source transcript
+ fast translation
+ recent context
        ↓
Muse Spark
        ↓
meaning-preserving repair / explanation
```

This keeps ordinary translation fast while making generative AI essential for the cases where literal translation fails.

## Recommended initial translator

Use a dedicated Indic-language translation provider behind an abstraction.

A practical first candidate is Sarvam for Telugu ↔ English.

Implement:

```python
class Translator:
    async def translate(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> TranslationResult:
        ...
```

Then:

```text
SarvamTranslator
```

can later be swapped if another service benchmarks better.

Do not couple the rest of the app to one provider.

---

# 10. Provisional English while the person is still talking

To make the system feel live, do not wait only for final turns.

Use a `TranslationScheduler`.

Example:

```text
Muse partial 1: నిన్న
Muse partial 2: నిన్న నేను
Muse partial 3: నిన్న నేను మార్కెట్
Muse partial 4: నిన్న నేను మార్కెట్ కి వెళ్లాను
```

Rules:

- show every source partial immediately
- debounce translation requests around 300–400 ms
- only translate when the partial changed meaningfully
- assign each request a version number
- stale responses must never overwrite newer ones
- provisional English is visually distinct
- final English replaces it when `speechComplete` arrives

Example UI:

```text
నిన్న నేను మార్కెట్ కి...
I went to the market...      [provisional]
```

then:

```text
నేను నిన్న మార్కెట్ కి వెళ్లాను.
I went to the market yesterday. [final]
```

Do **not** speak provisional translations yet.

---

# 11. Spoken translation

For the MVP, use **interpreter-style voiceover**, not perfect simultaneous dubbing.

Flow:

```text
final translation
      ↓
streaming TTS
      ↓
headphones
```

A reasonable first choice is ElevenLabs Flash through a streaming WebSocket.

Do not wait for a complete MP3.

Begin playback from the first PCM/audio chunks.

### Queue safeguard

Track:

```text
pending_dub_seconds
```

If the queue becomes too long:

```text
captions_only = True
```

for that utterance.

Otherwise translated speech can become three sentences behind the real call.

For MVP:

- headphones required
- no voice cloning
- no translated audio sent back into WhatsApp
- original call stays audible locally
- when dub plays, optionally lower original volume

---

# 12. Laya — where it should be essential

The teammate already has Laya running locally, so use that work rather than restarting.

Laya should not write translation.

Laya should be the **fast per-turn policy engine**.

For every finalized utterance, give it:

```json
{
  "source_text": "...",
  "english_translation": "...",
  "recent_context": "...",
  "learner_state": "...",
  "relationship": "grandparent_to_grandchild"
}
```

Return a typed result:

```json
{
  "semantic_route": "FAST | CONTEXT",
  "importance": "NORMAL | HIGH_STAKES",
  "visual_type": "FOOD | PLACE | FESTIVAL | VEHICLE | CLOTHING | OBJECT | NONE",
  "needs_explainer": true,
  "learning_opportunity": true,
  "needs_connection_prompt": false
}
```

## Laya job 1 — decide whether Muse is needed

Question:

> Is the fast translation probably sufficient, or is this slang, idiom, ambiguity, cultural meaning, or nonliteral language?

Output:

```text
FAST
CONTEXT
```

If FAST:

```text
use base translation
```

If CONTEXT:

```text
call Muse Spark
```

This makes Muse selective and keeps latency lower.

## Laya job 2 — visual category

Keep the teammate's existing image-category idea.

Output:

```text
FOOD
PLACE
FESTIVAL
VEHICLE
CLOTHING
OBJECT
NONE
```

Then a local lexicon identifies the actual image.

## Laya job 3 — explainer decision

Examples:

```text
"that party was fire" → true
"no cap" → true
Telugu idiom → true
"I bought milk" → false
```

If true, Muse generates a short explanation.

## Laya job 4 — learning opportunity

Laya helps decide whether this is a good moment to fade translation.

A familiar phrase in a casual sentence can be left alone.

The same phrase in medical instructions should not be.

## Laya job 5 — human-connection opportunity

This is important.

Example:

> “We used to make this every Sankranti when I was a child.”

Laya can flag:

```text
meaningful family/cultural moment
```

Then Muse generates:

> **Ask Ammamma:** “What was Sankranti like when you were my age?”

The AI does not tell the story.

It gives the relative an opening to tell it.

That connects the generative AI directly to the Meta challenge.

---

# 13. Deterministic safeguards

Do not use AI where code can guarantee correctness.

Hard-detect:

- times
- dates
- phone numbers
- money amounts
- some addresses
- obvious medical/safety keywords

If detected:

```text
FULL_CLARITY
```

That means:

- full translation
- no intentional omission for learning
- key facts surfaced in UI
- no risky Language Fade

Laya can also flag high-stakes content, but deterministic rules override it.

---

# 14. Muse Spark — where generative AI should matter

Use Muse Spark for open-ended meaning and relationship intelligence.

## A. Semantic repair

Input:

```json
{
  "source": "That party was fire",
  "fast_translation": "...",
  "recent_turns": ["...", "..."],
  "speaker": "grandchild",
  "listener": "grandmother"
}
```

Output:

```json
{
  "natural_meaning": "The party was amazing / really fun.",
  "is_nonliteral": true,
  "short_explanation": ""Fire" is slang for extremely good or exciting.",
  "use_repaired_translation": true
}
```

The grandmother should never receive a literal-flames interpretation.

## B. Cultural explainer

Example:

```text
pappu
```

Card:

```text
Pappu
A lentil dish common in Telugu households.
```

Short only.

## C. Human connection prompt

Example:

```text
🍲 Pappu

Ask Ammamma:
"Who taught you how to make it?"
```

This is one of the strongest Meta-aligned uses of generative AI.

## D. After-call recap

Example:

```text
TODAY WITH AMMAMMA

Understood directly:
• pappu
• bagundi

New:
• ...

Story:
• Ammamma learned this recipe from...

Next time:
• phrase due for review
```

The learner model supplies facts. Muse writes the human-readable recap.

---

# 15. Context Lens image cards

The image feature is worth doing, but it should be restrained.

Some concepts are genuinely easier to understand visually:

- pappu
- gajar ka halwa
- auto-rickshaw
- mandir
- rangoli
- saree / lehenga
- Diwali / Sankranti
- American prom / tailgate

The system should work culturally **in both directions**.

## MVP architecture

Use:

```text
context_lens/images/
context_lens/lexicon.json
```

Example:

```json
{
  "pappu": {
    "category": "FOOD",
    "aliases": ["pappu", "పప్పు", "dal"],
    "label": "Pappu",
    "image": "pappu.jpg"
  }
}
```

Flow:

```text
Laya says FOOD
      ↓
filter lexicon to FOOD
      ↓
alias / fuzzy match
      ↓
high confidence?
   yes      no
    ↓        ↓
 show       nothing
 image
```

Do not image-search live.

Do not generate an image for every sentence.

One useful visual every few minutes is better than constant distraction.

Stretch:

- Muse Image generates missing illustrations asynchronously
- cache them
- never block translation

---

# 16. Language Fade

The teammate's current heuristic is good enough for MVP:

```text
heard < 3
→ dub + full subtitle

3 <= heard < 8
→ original audio + English subtitle

heard >= 8
→ original audio + faded hint / none
```

Store:

```text
PhraseState
- phrase
- heard_count
- asked_count
- successful_context_count
- last_seen
- support_level
```

Add a `?` button.

When clicked:

```text
show full meaning
asked_count += 1
increase future support
```

Important:

> `heard >= 8` does not scientifically prove mastery.

It is a demo heuristic.

After the core system works, use FSRS for spaced-repetition scheduling.

Laya can contribute comprehension evidence; FSRS owns review timing.

---

# 17. Full live workflow

## App startup

Do all expensive initialization before the call:

```text
1. detect BlackHole
2. detect headphone output
3. start existing audio capture
4. connect Muse Voice realtime WebSocket
5. load Laya on MPS
6. initialize translation client
7. initialize Muse Spark client
8. open/reuse TTS connection
9. load SQLite learner state
10. load image lexicon
11. launch overlay
12. show health indicators
```

Do not load Laya after the first sentence.

Do not create a new TTS client for every sentence.

---

## During speech

```text
WhatsApp
  ↓
BlackHole
  ↓
existing PCM stream
  ↓
Muse Voice Transcribe
  ↓
partial Telugu/Hinglish
  ├────► source subtitle
  │
  └────► debounced TranslationScheduler
              ↓
        provisional English
              ↓
             UI
```

---

## When the turn is final

Run in parallel:

```text
A. final base translation
B. Laya typed decision
C. learner-state lookup
```

Then:

```text
if Laya semantic_route == FAST:
    keep base translation

if Laya semantic_route == CONTEXT:
    call Muse Spark with recent context
```

Then PolicyEngine combines:

```text
deterministic safety
+ Laya importance
+ learner state
```

and returns:

```text
FULL_CLARITY
DUB
SUBTITLE
HINT
PASSTHROUGH
```

If TTS is required:

```text
final English
→ streaming TTS
→ headphones
```

At the same time, asynchronously:

```text
visual card
slang/idiom explanation
Ask-them prompt
learner-state update
```

---

# 18. Instagram / Meta social context

This is potentially strong later, but **do not make it an MVP dependency**.

The valuable idea is relationship context.

For the demo, use a local schema:

```json
{
  "grandchild": {
    "recent_topics": ["college", "concert", "Atlanta"],
    "important_people": ["Mom", "Ravi"]
  },
  "grandparent": {
    "home": "Hyderabad",
    "family_topics": ["cooking", "Sankranti"]
  }
}
```

Muse can use this when understanding ambiguous language or generating connection prompts.

Later, where permission/API access exists, the same structure could be populated from opt-in:

- Instagram captions/posts
- selected photos
- WhatsApp history
- user-provided memories

Do not say “Muse reads Instagram” unless you actually have that integration and permission.

The product idea is:

> **Bring relevant shared context into the conversation, with explicit user choice.**

Example:

The grandchild recently posted concert photos and says:

> “The show last night was insane.”

Muse can understand that “show” refers to the concert and “insane” is positive slang.

Even better, the app can suggest:

> “Show Ammamma the photo?”

That creates shared context between generations.

---

# 19. WhatsApp strategy

For HackGT:

> **Between is a companion Mac app running alongside WhatsApp Desktop.**

That is enough.

Do not depend on private consumer WhatsApp call APIs.

Current architecture:

```text
WhatsApp output
→ BlackHole
→ Between
```

Overlay sits beside/on top of WhatsApp.

Stretch:

- virtual microphone for English → Telugu
- translated output back into WhatsApp
- screen share for visual cards
- deeper WhatsApp/Meta integration if a mentor confirms accessible APIs

---

# 20. Demo sequence

Do not demo ten disconnected features.

Show four proof moments.

## Moment 1 — live call

Relative speaks Telugu.

Judges see:

```text
live Telugu/Hinglish caption
→ live/provisional English
→ final English
→ English audio
```

This proves the hard engineering.

## Moment 2 — nonliteral meaning

Use a verified sentence whose literal translation would fail.

For example, on the English → Telugu stretch path:

> “The party was fire.”

Between:

```text
Meaning:
The party was amazing / really fun.

"fire"
slang: extremely good / exciting
```

For the one-direction Telugu MVP, use a Telugu idiom verified by a fluent speaker.

This proves the system understands **meaning**, not token replacement.

## Moment 3 — Context Lens + connection

Relative says something about pappu / Sankranti / another culturally meaningful topic.

Between shows:

```text
[image]

Pappu
lentil dish

Ask Ammamma:
"Who taught you how to make it?"
```

Grandchild asks.

Relative tells story.

That is the Meta moment.

## Moment 4 — Language Fade

Switch to a seeded returning-learner profile.

The same familiar phrase is no longer dubbed.

The learner follows it naturally.

Close with:

> **Most translators get better at translating. Between gets better at knowing when not to.**

---

# 21. Judging criteria mapping

## 30% — strengthens human connection

The app enables deeper family calls and intentionally routes cultural questions back to the family member.

Its end goal is less mediation.

## 25% — essential AI

- Muse Voice hears Telugu/Hinglish live.
- dedicated translator provides fast baseline meaning.
- Laya makes rapid policy decisions.
- Muse Spark understands nonliteral/cultural language.
- learner state decides when support can fade.
- Muse generates prompts that create more human conversation.

The AI components have distinct jobs.

## 20% — originality

The novelty is the combination:

```text
live family translation
+
meaning-aware cultural interpretation
+
translation that fades with learning
+
visual context
+
AI that prompts humans to tell each other stories
```

## 20% — technical execution

The live demo can prove:

- macOS audio routing
- realtime WebSocket STT
- Telugu/Hinglish code-switching
- provisional translation
- local decision model
- conditional generative reasoning
- streaming TTS
- persistent learner state
- asynchronous visual UI

---

# 22. Build order from the exact current state

## Step 0 — freeze what works

```bash
git add .
git commit -m "working BlackHole WhatsApp audio baseline"
git checkout -b realtime-pipeline
```

## Step 1 — expose PCM frames

Keep the meter working.

Add a second consumer.

No AI.

## Step 2 — Muse realtime STT

Goal:

```text
WhatsApp Telugu
→ BlackHole
→ Muse
→ terminal partials/finals
```

This is the first go/no-go checkpoint.

## Step 3 — latency tracer

Timestamp:

```text
speechStart
first partial
speechEnd
speechComplete
```

## Step 4 — final English translation

```text
speechComplete
→ translator
→ terminal English
```

## Step 5 — provisional English

Use Muse partials and debounce.

## Step 6 — overlay

Only source + English.

## Step 7 — TTS

Only final English.

Benchmark:

```text
speech end → first English audio
```

## Step 8 — Laya

Reuse teammate work.

Add the typed decision schema.

## Step 9 — Muse semantic repair

Build slang/idiom proof moment.

## Step 10 — Context Lens

Local images only.

## Step 11 — Language Fade

SQLite state + seeded profiles.

## Step 12 — Ask-them prompt

Muse connection prompt.

Do not change this order unless a dependency forces it.

---

# 23. Claude Code prompts — run one at a time

## Prompt 1 — inspect the existing project

```text
We are continuing an existing HackGT project called Between.

IMPORTANT: do not redesign or refactor the project yet.

The current repository already has a working macOS prototype:
- WhatsApp Desktop output is routed into BlackHole 2ch
- Python reads that live audio
- there is an audio meter/bar that moves with WhatsApp call audio
- there may already be Laya benchmark/integration code

First inspect the entire repository.

Tell me:
1. which files implement BlackHole/audio-device selection;
2. which files use sounddevice or otherwise read PCM;
3. the exact sample rate, dtype, channel count, block size, and callback/threading model;
4. where the existing UI/audio meter gets its values;
5. whether PCM frames are already reusable elsewhere;
6. where the existing Laya code is and how it is initialized;
7. the smallest safe changes needed to expose PCM frames to a streaming STT consumer while preserving all existing behavior.

Do NOT change code yet.

Give me a file-by-file plan based on the code that actually exists. Do not invent filenames.
```

## Prompt 2 — expose PCM without breaking existing work

```text
Implement only the minimal audio-stream abstraction we just planned.

Requirements:
- preserve the existing BlackHole → audio meter behavior exactly
- preserve existing device selection
- expose captured PCM frames to additional async consumers
- do not write audio to disk
- avoid blocking work inside the sounddevice callback
- use a thread-safe or async-safe queue appropriate to the existing architecture
- add a temporary debug consumer that prints frame/byte counts once per second

Do not add STT, translation, Laya, or TTS yet.

Run the existing app/tests after the change.
```

Acceptance:

```text
meter still works
+
debug PCM consumer receives data
```

## Prompt 3 — Meta Muse realtime STT

```text
Add realtime Meta Muse Voice Transcribe on top of the existing PCM stream.

Use the current official Meta Model API realtime speech-to-text protocol.

Requirements:
- model: muse-voice-transcribe-1.0
- endpoint: wss://api.meta.ai/v1/asr/realtime
- ENDPOINTING mode
- CUMULATIVE partials
- signed int16 mono PCM
- prefer 24 kHz
- Telugu + English language bias
- environment variable MODEL_API_KEY
- send live PCM without writing files
- handle speechStart, transcript, speechEnd, speechComplete, and error events
- use turnId
- expose TranscriptPartial and TranscriptFinal events
- cumulative partials replace previous UI text
- reconnect safely
- configure a small keyword/family-vocabulary bias list

Do not add translation.
Do not add external VAD unless Muse endpointing proves inadequate.

Integrate into the existing code rather than replacing its audio architecture.
```

## Prompt 4 — latency instrumentation

```text
Add a reusable per-turn latency tracer.

Record:
- speechStart
- first partial transcript
- speechEnd
- speechComplete

Print per-turn values and rolling p50/p95.

Design it so later stages can add:
- translation start/end
- Laya start/end
- Muse context start/end
- TTS request
- first TTS audio

Do not optimize anything yet.
```

## Prompt 5 — translator abstraction

```text
Add a pluggable async Translator interface.

Implement SarvamTranslator for Telugu -> English using the current Sarvam text translation API.

Requirements:
- async
- source Telugu, target English
- TranslationResult with text, elapsed_ms, provider
- timeout
- one retry for transient failures
- API key from environment
- cache identical finalized strings within a session
- consume TranscriptFinal only for now
- emit TranslationFinal

Print:
SOURCE:
ENGLISH:
TRANSLATION_MS:

Do not add Muse Spark or TTS.
```

## Prompt 6 — provisional English

```text
Build TranslationScheduler on top of Muse cumulative partials.

Requirements:
- source caption updates immediately
- debounce translation requests ~300–400 ms initially
- only translate when the partial changed meaningfully
- version every request
- stale responses can never overwrite newer ones
- emit TranslationPartial
- on TranscriptFinal, invalidate stale partial work and issue one final translation
- emit TranslationFinal
- log request count and latency

Never generate TTS from provisional translation.
```

## Prompt 7 — overlay

```text
Inspect and extend the current frontend instead of changing frameworks.

Build a minimal polished always-on-top overlay.

For now show:
1. Telugu/Hinglish source transcript
2. English translation

Requirements:
- visually distinguish provisional and final English
- live updates without reload
- connect to backend using the existing transport or a local WebSocket
- readable beside a WhatsApp Desktop call
- one control to hide/show

No images, slang cards, settings, or animations yet.
```

## Prompt 8 — streaming TTS

```text
Add English streaming TTS using ElevenLabs Flash v2.5.

Requirements:
- use WebSocket streaming
- only consume TranslationFinal
- start playback from first returned chunks
- output to real headphones, NOT BlackHole
- no voice cloning
- keep a small playback queue
- track queued audio duration
- if backlog exceeds a configurable threshold, skip dubbing for that utterance and keep captions
- log tts_request and first_audio_played
- never block STT while audio plays

Preserve existing WhatsApp/BlackHole routing.
```

## Prompt 9 — wrap the existing Laya implementation

```text
Find and reuse the Laya implementation/benchmark already in this repository.

Do not replace it.

Create a DecisionEngine wrapper. Load the English Laya checkpoint once at startup on MPS.

For each finalized English translation, return:

semantic_route:
- FAST
- CONTEXT

importance:
- NORMAL
- HIGH_STAKES

visual_type:
- FOOD
- PLACE
- FESTIVAL
- VEHICLE
- CLOTHING
- OBJECT
- NONE

needs_explainer: bool
learning_opportunity: bool
needs_connection_prompt: bool

Use the English translation as the primary state because our benchmark showed that checkpoint performed better.

Keep question/options narrow.

Run Laya concurrently with noncritical work.

Instrument Laya latency.
```

## Prompt 10 — evaluate Laya

```text
Create a labeled Laya evaluation set with at least 40 sentences.

Include:
- ordinary sentences
- slang
- idioms
- food
- places
- festivals
- vehicles
- clothing
- times/dates
- money
- health information
- serious/emotional content
- sentences where no card should appear

Store expected outputs.

Build a script that prints:
- accuracy per decision field
- false positives
- false negatives
- average latency
- p95 latency

Do not fine-tune yet.

First show where zero-shot Laya fails.
```

## Prompt 11 — policy/safety engine

```text
Build PolicyEngine.

Inputs:
- final translation
- Laya DecisionResult
- learner PhraseState

Outputs:
- FULL_CLARITY
- DUB
- SUBTITLE
- HINT
- PASSTHROUGH

Add deterministic detection for:
- times
- dates
- currency/amounts
- phone numbers
- obvious medical/safety terms

Rules:
- deterministic high-stakes detection forces FULL_CLARITY
- Laya HIGH_STAKES also forces FULL_CLARITY
- no model may override deterministic safety rules
- ordinary sentences may reduce support using learner state

Add unit tests.
```

## Prompt 12 — Muse Spark semantic context

```text
Add Meta Muse Spark 1.3 through Meta Model API as a ContextEngine.

Use:
- base URL https://api.meta.ai/v1
- model muse-spark-1.3
- MODEL_API_KEY

Call it ONLY when Laya semantic_route == CONTEXT or needs_explainer == true.

Input:
- source transcript
- fast English translation
- previous two finalized turns
- speaker/listener relationship
- source/target languages
- optional relationship_context

Require JSON output:
{
  "natural_translation": string,
  "is_nonliteral": boolean,
  "short_explanation": string | null,
  "cultural_note": string | null,
  "human_followup_prompt": string | null
}

Rules:
- short explanation only
- follow-up prompt should invite the user to ask the FAMILY MEMBER, not the AI
- strict timeout
- if Muse fails, fall back to base translation
- FAST sentences must never wait for Muse
- instrument latency
```

## Prompt 13 — slang regression tests

```text
Create semantic-risk regression tests.

Include:
- "that party was fire"
- "no cap"
- "I'm dead" meaning amused
- "break a leg"
- Telugu idioms supplied and verified by our team

For each:
- inspect base translation
- inspect Laya route
- inspect Muse repair
- inspect final displayed explanation

Flag dangerous literal interpretations.

Do not invent Telugu idioms; use only native-speaker-verified examples.
```

## Prompt 14 — Context Lens local images

```text
Implement Context Lens using a curated local image lexicon.

Create/extend:
- context_lens/lexicon.json
- context_lens/images/

Each entry:
- canonical id
- category
- English aliases
- Telugu-script aliases
- romanized Telugu aliases
- display label
- image path
- optional one-line description

Flow:
Laya visual_type != NONE
→ filter lexicon by category
→ exact/fuzzy alias match
→ show image only above confidence threshold
→ otherwise show nothing

Never delay translation or TTS for image logic.

Seed only 30–50 high-value concepts.
```

## Prompt 15 — Language Fade learner state

```text
Implement Language Fade state in SQLite.

Per user + phrase store:
- heard_count
- asked_count
- successful_context_count
- last_seen
- support_level

Initial behavior:
- new phrase = maximum support
- repeated phrase without confusion = gradually less support
- '?' action = show full meaning immediately and increase future support
- HIGH_STAKES = always full clarity

Create seeded profiles:
- first_call
- returning_learner

The same test utterance should behave differently between profiles.
```

## Prompt 16 — "Ask them..." human connection prompts

```text
Add the human-connection prompt.

When:
- Laya needs_connection_prompt == true
- importance == NORMAL
- no recent connection prompt was shown

call Muse Spark and generate ONE optional short question for the listener to ask the family member.

Desired examples:
food -> "Who taught you how to make it?"
festival -> "What was it like when you were my age?"
place -> "What's your favorite memory there?"
family phrase -> "Who in the family used to say that?"

The AI must not answer the question.

Rate-limit to roughly one every few minutes.
```

## Prompt 17 — complete latency benchmark

```text
Benchmark at least 30 representative turns through the full pipeline.

Collect:
- first STT partial
- speechEnd -> speechComplete
- final translation latency
- Laya latency
- Muse latency when invoked
- TTS request -> first audio
- speechEnd -> first translated audio
- whether voice was skipped due to backlog

Print p50, p95, max.

Split results into:
- FAST route
- CONTEXT route

Save raw results to JSON or CSV.

Identify the top two contributors to user-perceived latency.
```

## Prompt 18 — optimization pass

```text
Optimize based only on measured results.

Prioritize:
1. persistent connections
2. avoiding repeated model/client initialization
3. parallelizing independent calls
4. reducing unnecessary partial-translation API requests
5. reducing audio buffers
6. keeping blocking work out of callbacks/event loop
7. caching
8. skipping Muse on FAST sentences

For every optimization:
- explain expected effect
- implement it
- rerun benchmark
- report before/after p50/p95
```

## Prompt 19 — demo reliability mode

```text
Add a Demo Mode while keeping the real pipeline intact.

Requirements:
- default remains real BlackHole/Muse/translator/Laya pipeline
- selectable seeded learner profile: first_call vs returning_learner
- prewarm Laya, Muse client, translator, TTS connection, and Muse Voice connection
- visible health indicators
- one-click state reset
- backup ability to replay prerecorded call audio into the SAME real processing pipeline

Do not fake AI outputs.
The backup replays real audio through the real models.
```

---

# 24. First two hours from now

Do this in order:

1. commit the working BlackHole baseline;
2. run Claude Prompt 1;
3. expose PCM frames without breaking the meter;
4. connect Muse Voice Transcribe;
5. get live Telugu partials from an actual WhatsApp call;
6. add latency timestamps;
7. test 10–20 real Telugu/Hinglish utterances;
8. only then add translation.

If live Telugu STT is not reliable, that is the team's top issue.

Do **not** build the image card first.

---

# 25. Go / no-go checkpoints

## A. STT

Can Muse accurately understand actual Telugu/Hinglish call audio?

```text
NO → fix/fallback before continuing
YES → continue
```

## B. Translation

Can final English arrive quickly enough to feel conversational?

```text
NO → benchmark another translator / partial strategy
YES → continue
```

## C. TTS

Can voice begin without accumulating backlog?

```text
NO → make captions primary and voice secondary
YES → continue
```

## D. Laya

Does Laya actually outperform simple heuristics on your labeled set?

```text
NO → narrow its questions / reduce its responsibilities
YES → keep it central
```

## E. Muse

Does Muse reliably repair semantic-risk examples?

```text
NO → tune structured prompt / examples
YES → expose the routing in the demo
```

---

# 26. What not to build before the core works

Do not prioritize:

- Instagram API integration
- multiple language pairs
- voice cloning
- full bidirectional WhatsApp audio injection
- hundreds of cultural images
- mobile apps
- authentication/accounts
- elaborate spaced-repetition dashboards
- generated images on every turn

The product must first prove:

```text
REAL CALL
→ REAL TRANSCRIPT
→ FAST MEANING
→ NATURAL OUTPUT
```

Then prove:

```text
AI UNDERSTANDS THE CULTURAL GAP
```

Then prove:

```text
AI CREATES A HUMAN CONVERSATION
```

---

# 27. Expansion after the English ↔ Telugu MVP

Once the one-direction Telugu → English path is stable:

## Bidirectional mode

```text
child microphone
→ Muse Voice
→ English transcript
→ Telugu translation
→ Telugu TTS
→ virtual microphone
→ WhatsApp
```

The biggest new technical risk is **virtual microphone routing and echo**, not the translation itself.

## More languages

Add one at a time:

- Hindi
- Punjabi
- Gujarati
- Tamil

Do not claim broad multilingual support until tested with fluent speakers.

## Better learning

Replace basic heard-count thresholds with FSRS and comprehension signals.

## Better social context

Opt-in relationship context can eventually come from:

- selected Instagram posts
- family photos
- chosen WhatsApp messages
- manual onboarding

Use it to improve meaning and create conversation openings, not to surveil people.

---

# 28. Team split

## Audio / realtime systems

Own:

- existing BlackHole code
- PCM abstraction
- Muse Voice
- TTS playback
- audio queue/backlog
- latency tracer

## Translation / Muse

Own:

- translator abstraction
- Telugu-English provider
- Muse Spark
- semantic repair
- slang/idiom regression tests

## Laya / learning

Own:

- existing Laya implementation
- decision schema
- evaluation set
- PolicyEngine
- SQLite phrase state
- Language Fade

## Frontend / Context Lens

Own:

- overlay
- provisional/final captions
- image cards
- explainer cards
- `?` action
- human connection prompt

---

# 29. Final product thesis

Between is not trying to become the best general-purpose translator.

It is a **relationship layer for families separated by language**.

The speech stack handles the immediate barrier.

Laya decides what kind of help is needed.

Muse understands the things literal translation cannot.

Context Lens makes unfamiliar cultural objects visible.

Language Fade helps each person depend on translation less.

And the most important generative-AI feature should often end with:

> **Ask them.**

The model notices the opening.

The family member tells the story.

That is how the AI strengthens the relationship rather than replacing it.

---

# 30. Final engineering rule

For every feature ask:

> **Does this have to finish before the listener understands the sentence?**

If yes:

> optimize it ruthlessly.

If no:

> make it asynchronous.

The build path is:

```text
BLACKHOLE WORKS
      ↓
MUSE LIVE TRANSCRIPTION
      ↓
FAST TRANSLATION
      ↓
LIVE CAPTIONS
      ↓
LOW-LATENCY TTS
      ↓
LAYA POLICY
      ↓
MUSE SEMANTIC REPAIR
      ↓
LANGUAGE FADE
      ↓
CONTEXT LENS
      ↓
AI CREATES MORE HUMAN CONVERSATION
```

Build in that order.

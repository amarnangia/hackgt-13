## Inspiration

We're second-generation immigrants, and one of the hardest parts of growing up has been watching our relationships with our grandparents shrink because we don't share a language. Calls with a Telugu-speaking grandma turn into the same three questions: *Did you eat? How's school? Okay, bye.*

A translator could help, but most translators keep you dependent on them forever. We wanted something that helps you understand her today and teaches you her language, so you need it a little less on every call.

## What it does

Roots runs on top of the WhatsApp calls families already make. Grandma installs nothing and changes nothing.

- **Live translation in her own voice.** English captions appear about half a second after she finishes a sentence, and the English is spoken in her cloned voice. Her real voice stays underneath, turned down.
- **Idioms and cultural references explained.** When she uses a saying, or mentions a food, place, festival or person, Roots shows what it really means, with a picture.
- **Translates less over time.** Roots tracks how likely you are to know each of her words and leaves the ones you know in Telugu, so the translation fades as your fluency grows. Tap a word you don't know and it comes back.
- **Keeps the conversation going.** When the call pauses, Roots suggests a question to ask her *in Telugu*, like *"Pulihora ela chestaru? Naaku nerpistara?"* ("How do you make pulihora? Will you teach me?"), so she tells the story instead of you just listening. When she asks you something, it shows how to answer her in Telugu.
- **A story page after every call.** When you hang up, the call becomes a page for the family: the stories she told with clips of her real voice, questions to ask next time, and a Telugu message to send her.
- **A mobile app.** An iPhone app and widget remind you what to ask on your next call, show the words you've learned in her voice, and let family members record their own voices.

## How we built it

### The pipeline

```
her phone ─WhatsApp─▶ Chrome (WhatsApp Web) ─audio─▶ BlackHole ─▶ Python engine
                                                                    │
   Muse Voice Transcribe ─▶ live Telugu text                        │
   IndicTrans2 (local) ⟷ Muse Spark (backup) ─▶ English             │
   Rules + Laya (local) ─▶ decisions for every line                 │
   Knowledge tracing ─▶ which words stay in Telugu                  │
   Pocket TTS / ElevenLabs ─▶ English in her voice                  │
                                                                    ▼
             Chrome overlay ◀── localhost WebSocket ── captions, pictures, questions, words
             Story page     ◀── Muse Spark, after the call
```

**Audio.** WhatsApp Web's audio is routed through a virtual audio device (BlackHole) into our Python engine, which plays it on to your headphones. Her voice drops to 20% between lines and 5% while the English plays.

**Speech to text.** Meta's **Muse Voice Transcribe** streams her Telugu as live partial transcripts over a WebSocket. We cut the stream into sentences, or at commas once a clause is long enough, and send each piece off as soon as it ends.

**Translation.** **IndicTrans2** (AI4Bharat's 1B model) translates on the laptop's GPU. Before it runs, a 308-entry glossary pins words like *pulihora* to fixed English, and a pronoun fixer turns Telugu's gender-neutral తను into "she" or "he" from the verb. If the local model hasn't answered within **1.2 s**, the same line goes to **Muse Spark** and the first answer wins. If the local translator crashes, Muse Spark takes over for the rest of the call. Captions appear in about **0.4–0.6 s** after she finishes a sentence.

**Voice.** Relatives who record about a minute in the app get an **ElevenLabs** voice. Until then, **Pocket TTS** clones the caller's voice locally from about 10 seconds of call audio, with **Kokoro** as a stock voice for the first few lines. A line that would be spoken more than 3 s late is shown as a caption only, and lines she said in English, or made only of words you know, aren't spoken at all.

### The AI, model by model

| Job | Model | Where it runs |
|---|---|---|
| Hear her Telugu | **Muse Voice Transcribe** | Meta's cloud |
| Telugu → English | **IndicTrans2 indic-en 1B** (AI4Bharat) | Laptop GPU |
| Backup translation, and Telugu written in English letters | **Muse Spark 1.1** | Meta's cloud |
| Quick decisions on every line | **Laya**, plus a decision head we trained | Laptop |
| "Ask her" questions when no template fits, and "Curious?" answers | **Muse Spark 1.1** | Meta's cloud |
| Story page after the call | **Muse Spark 1.3** | Meta's cloud |
| Her cloned voice | **Pocket TTS**, then **Kokoro** as a stock fallback | Laptop GPU |
| Personalized voices | **ElevenLabs** Flash v2.5 (English), v3 Conversational (Telugu) | Cloud |
| Two-way: English → Telugu, spoken | **IndicTrans2 en-indic 1B** + Meta **MMS-TTS Telugu** | Laptop |
| Our training data | **Muse Spark** wrote ~3,300 labelled example replies | Meta's cloud |

### Laya: the split-second decisions

**What Laya is.** Laya is not an LLM, and it doesn't write anything. You give it a sentence and a set of choices, and it returns a probability for each one. That makes it fast enough to run on every line of a live call: a median of **52 ms per line** on our 24 GB M4 MacBook, where an LLM round trip takes about a second.

**What it decides.**
- Is she asking you a question, making a request, or just telling you something?
- What is the conversation about (11 topics)? That drives the topic words in the side panel.
- Which thing in the line gets a picture, and is an unfamiliar word a food, place, festival or clothing?
- Which "Curious?" questions are most worth showing?
- What kind of question did she ask you, so we can suggest a reply in Telugu?

**Rules first, Laya second.** Laya on its own was weak on yes/no questions and on choices with many options, so every decision runs through our rules first and Laya only handles what the rules can't settle.

| Decision | Laya alone | Rules, then Laya | Muse Spark alone |
|---|---|---|---|
| Topic (11 options) | 64% | **91%** (9/10 on a held-out call) | 95%, ~1 s |
| What she's asking you | 78% | **96%** | 100%, ~0.9 s |
| Question, request or statement | — | **97%** | — |

Rules plus Laya get close to Muse Spark's accuracy at a fraction of its latency.

**Our own layer on top of Laya.** Roots needs to know whether you understood a Telugu word it left untranslated. Laya had never been asked that, so we taught it:
1. **Data.** Muse Spark generated about **3,300** realistic replies to Grandma's lines, each labelled *understood*, *not understood* or *no signal* (for replies like "okay" or "hold on").
2. **Training.** We froze Laya's encoder and trained a new copy of its decision layers on this one question, so its other decisions stay untouched.
3. **Using it carefully.** Clear cases are handled by rules first (asking what a word means, backchannels like "okay"). The trained head is only trusted when it's at least 98% confident; otherwise it gives no evidence. When both are unsure, Muse Spark breaks the tie, at most 12 times a call.

**Results.** On words it had never seen before, the trained head was right **88%** of the time when it was confident. On a hand-written test of replies about unseen words, the evidence the app actually used was **93%** right, with no false "understood", and **95%** with Muse Spark as the tie-breaker. This check runs on two-way calls, where Roots can hear your replies.

**Where Laya didn't work.** We also tried to have Laya confirm idioms: is she really using a saying, or just sharing some words with it? It never got past chance. Its encoder doesn't represent Telugu spelling (a linear probe on it reached 57%), and on English the trained head didn't learn either. So we dropped it, and idioms are found by fuzzy matching instead.

### Idioms and sayings

Roots knows about **1,370** sayings, idioms, slang terms and cultural references (794 Telugu, 578 English). Speech recognition often spells a saying a little differently, so exact matching caught only 48% of spoken Telugu idioms. We romanize Telugu into a sound-alike form and match loosely, so small misspellings and merged or split words still match. Short forms must match as whole words, so "slaying" doesn't match "saying". That raised spoken Telugu idioms caught to **89%**. Pictures come from our own library of 213, plus Wikipedia lookups that are fetched in the background and never make a line wait.

### The learning model

Roots tracks a probability $p$ that you know each word, using Bayesian Knowledge Tracing. Each word starts from a guess by its kind: 95% for everyday family words like *amma*, 2% for proverbs. Every exposure is a learning event:

$$p \leftarrow p + (1 - p)\,L$$

where $L$ is 0.20 for hearing it with its meaning, 0.15 for seeing its picture, and 0.30 for asking about it and reading the answer.

Everything you do is evidence, weighed with Bayes' rule:

$$p \leftarrow \frac{P(e \mid \text{know})\,p}{P(e \mid \text{know})\,p + P(e \mid \neg\text{know})\,(1-p)}$$

Saying a word yourself is strong evidence that you know it. Tapping a word to ask what it means is strong evidence that you don't. Leaving a kept word untapped is weak evidence that you understood it, and on two-way calls the trained Laya head adds evidence from your replies.

Between calls, each word fades back toward its starting guess:

$$p(t) = p_0 + (p - p_0)\cdot 0.5^{\,\Delta t / h}$$

The half-life $h$ starts at 7 days. It doubles each time you show you remember the word (up to 60 days) and halves when you don't (down to 1 day). That gives you spaced repetition without any quizzes. Hearing a word several times within 45 seconds counts once, so cramming doesn't count. Once $p \geq 0.7$, the word stays in Telugu.

### Two-way mode

Grandma can hear you too. Roots works out who speaks Telugu from what each person says. Your English is translated locally and spoken into WhatsApp Web's microphone, either in Meta's MMS Telugu voice or in your own ElevenLabs voice. A translation waits while its listener is talking and fades out if they interrupt. Anything your mic picks up that closely matches what was just played is dropped as echo.

### Front ends

A Chrome extension draws the overlay on WhatsApp Web. Each panel runs in its own frame so WhatsApp's security rules can't block its connection to the engine, and the engine only accepts our own pages. A SwiftUI iPhone app and home-screen widget handle everything outside the call. They talk to the Mac, which syncs word progress, the family dictionary and story pages to Firebase. Recordings never leave the laptop.

### Claude Code

We used Claude Code as our coding agent, and leaned on it most for verification. A live call is hard to test, so it helped us build a harness:
- a fake-call replayer for building the overlay without audio;
- scripts that run the demo lines through the real engine and check each decision;
- separate tests for idioms, pronouns, the reply check and two-way translation (13/13 passing on our 24 GB Mac);
- an evaluation that compares Laya with Muse Spark on accuracy and speed.

## Challenges we ran into

- **Speed.** Telugu puts the verb at the end of the sentence, so we can't translate until the sentence is nearly done. We show faded draft captions every 0.6 s, run three translation workers in parallel, and race the local model against the cloud.
- **Laya alone wasn't accurate enough.** It needed rules underneath it and a trained layer on top. It was also weak on yes/no questions, so those became rules.
- **Knowing when a model hasn't learned.** Our first reply-check training reached only 72% on its own training data, because every batch held the same few words. Reshuffling each epoch and doubling the data raised held-out accuracy from 65% to 83%. A model can also score well by always guessing the most common answer, so we added class-weighted training and per-class accuracy. Measured that way, the idiom check never got past chance, so we dropped it.
- **Memory.** The voice library's GPU cache grew to about 2 GB and pushed the Mac into swap, which made translation take about 10 s. Capping it at 256 MB fixed it.
- **Echo in two-way mode.** Translations played through the speakers were picked up again by the mic, so we filter out anything that closely matches audio we just played.

## What we learned

- Small, fast models combined with good rules beat a big LLM for real-time decisions, and an LLM is still great for writing training data and for tie-breaking.
- A model's accuracy only means something next to the baseline. Measuring per class is what told us when to drop a model.
- Learning science (knowledge tracing, the testing effect, spaced repetition) translates naturally into product design.
- Building the testing harness first is what let four people ship this much in one weekend.

## What's next

- Test two-way mode on live calls.
- Add a consent step before cloning Grandma's voice from the call.
- Build word lists and sayings for the six other Indian languages the pipeline already accepts.
- Fit the learning model's parameters to real quiz data instead of our hand estimates (the quiz and fitting tools are built).

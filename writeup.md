# Weave: submission write-up

## Who it's for
Kids of immigrant families who can't really talk to their grandparents in their language, starting with Telugu. Their
calls shrink to *"Annam tinnava?"* ("Did you eat?") and "bye". Grandma doesn't need to change anything: she stays on
WhatsApp or Instagram on her phone. The grandkid takes the call on their laptop in Chrome, with Weave on top.

## How it strengthens connection
- **They can actually talk.** Her Telugu becomes English about half a second after each sentence, spoken **in her own cloned voice**, so it still sounds like her.
- **The grandkid takes part, not just listens.**
  - When she asks something, Weave shows how to answer *in Telugu*: "How do I say 'Yes, I ate. Did you eat?'" → *"Avunu, tinnanu. Meeru tinnara?"*
  - At her pauses, it suggests a question that turns what she said into a story: *"Meeru, Thatayya ela kalisaru?"* (How did you and Thatayya meet?)
- **Her world makes sense.** Pictures of what she mentions (gavvalu, Bhogi bonfires, NTR), what her proverbs mean, and a "Curious?" panel for anything the grandkid didn't get, answered from the call's context.
- **It teaches instead of replacing.**
  - Weave estimates how likely the grandkid is to know each word, from hearings, pictures, questions they asked and words they tapped, with forgetting between calls.
  - Once a word is known, it stays in Telugu in the captions.
  - The side panel shows words for whatever they're talking about.
  - Over time the call needs less translation.
- **The family keeps the stories.** Every call becomes a story page with her stories, her voice clips, pictures and questions for next time, plus a family dictionary. The next call opens with one of those questions.

## Why AI is essential
Without it these two people can't have a conversation at all. Every step is AI:
- **Meta Muse Voice Transcribe:** hears her Telugu, live.
- **IndicTrans2** on the laptop translates it, raced against **Meta Muse Spark** when it's slow.
- **A voice-cloning model** speaks the English in her voice.
- **Meta Muse Spark:**
  - writes the questions to ask her;
  - answers the grandkid's questions using what she just said;
  - turns the call into a story page.
- **Laya,** a small model on the laptop, makes the split-second decisions for every sentence, in about a quarter of a second:
  - is she asking you something?
  - what are you talking about?
  - which picture?
  - what's worth explaining?
  - which reply to offer?

We measured it (`tools/eval_laya.py`):

| Decision | Laya alone | Our rules, then Laya | Muse Spark alone |
|---|---|---|---|
| What is the line about? (11 topics) | 64%, 0.13 s | 91% (9/10 on a held-out call) | 95%, 1.0 s |
| What is she asking you? | 78%, 0.10 s | 96% | 100%, 0.9 s |
| Question, request or statement? | — | 97% | — |

Rules plus Laya get close to the cloud LLM in a tenth of the time, on the laptop, without sending every line to the
cloud. So the call stays fast, and the generative models run where they matter: her voice, her stories and the
answers.

## How we built it
- **Engine:** Python.
  - Audio through BlackHole.
  - Streaming speech recognition, with sentences cut as she speaks.
  - Local translation with a glossary of 308 Telugu words, so names like pulihora come out right.
  - A cloned-voice queue that speeds up slightly to keep up.
- **Overlay:** a Chrome extension of three panels over the call, fed by a local WebSocket that only accepts our own pages.
- **After-call story keeper** and the Weave app (web and iPhone).
- **Latency is logged for every sentence.**

## What's next
- **The reverse direction:** the grandkid's English spoken to her in Telugu.
- **Live draft captions** while she's still mid-sentence. Telugu puts the verb last, so a sentence can't be final until she finishes it.
- **Fitting the word-knowledge model** to quizzes, instead of our hand-set weights.
- **More languages:** Hindi and Tamil use the same pipeline.

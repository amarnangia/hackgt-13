# Overview

## The problem
Many kids of immigrants can't comfortably talk with their grandparents and other relatives back home. The grandparents speak Hindi (or another Indian language) and the kids think in English. Calls turn into short "how are you, eat well" exchanges because both sides run out of shared words.

## The idea
A Mac app that runs **alongside a live WhatsApp call on the laptop (WhatsApp Web in Chrome)** and fills in the language gap in real time:

- **Partial live translation:** when a relative speaks, some phrases are dubbed into English (their voice is lowered and an English voice plays over it). Other phrases play in the original language, with the translation shown as a subtitle on screen.
- **It learns what you know:** the app keeps track of words and phrases you've heard. The more often you've heard one, the less it gets translated. It goes from dubbed, to subtitled only, to left alone. Over time the call becomes more Hindi and less English, so you learn the language just by talking to family.
- **Slang and idiom explainer:** when someone says something that isn't literal ("that was fire", "no cap", or a Hindi *muhavara*), a small card explains what it means.
- **Cultural image cards:** when a relative mentions something concrete, like a food (gajar ka halwa), a vehicle (rickshaw), a place (mandir) or a festival (Diwali), a picture of it appears on screen. The image set covers Indian and American things, so it helps both sides.
- **Ask her about it:** when she mentions something with a picture or card (gavvalu, Bhogi, Thatayya, a proverb, NTR), a question in simple Telugu appears at her next pause that turns it into a story: *"Gavvalu ela chestaru? Naaku nerpistara?"* (How do you make gavvalu? Will you teach me?). The next call opens with a question the last call's story page suggested.

## Where Laya fits
[Laya](https://laya.convaiinnovations.com/) is an open-source model from Convai Innovations that makes fast decisions without writing any text. You give it a sentence and typed questions, and it returns choices and probabilities. We run it locally on the Mac, so it costs nothing per call, and it makes the split-second calls for each sentence:

- What kind of thing, if any, was mentioned? (food / vehicle / place / clothing / festival / none) This decides whether an image appears.
- Is this slang or a figure of speech? This decides whether an explanation card appears.

We tested it on an M4 MacBook Air with the English checkpoint on the Apple GPU, feeding it the English translation of each sentence:
- It took **~120–150 ms** per sentence for 3 questions.
- It picked the right category on **6/6** sample call sentences and flagged slang correctly on 5/6.

The multilingual checkpoint was faster (~45 ms) but much less accurate, so we use the English one. Laya can't write text, so an LLM writes the explanations and a word list picks the actual image.

## Scope for HackGT
- **In scope:** relative → you direction (Telugu → English first; Hindi and others via `--lang`), running on a Mac with WhatsApp Web and headphones.
- **Stretch:** you → relative direction (a translated Hindi voice sent through a virtual mic), more languages (Punjabi, Gujarati, Tamil), and sharing the image cards over WhatsApp screen share.

See [plan.md](plan.md) for the architecture and build order.

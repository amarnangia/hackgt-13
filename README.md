# Weave

**Talk to your grandparents in their language, and keep what they tell you.**

Weave is an overlay on the WhatsApp (or Instagram) video call you already make in Chrome. Your grandmother speaks
Telugu on her phone as usual. On your laptop you hear her in English, in her own cloned voice, and see:
- the pictures of what she mentions;
- what her sayings mean;
- questions you can ask about anything you didn't understand;
- the Telugu words for what you're talking about.

Once you've learned a word, Weave stops translating it, and every call becomes a family story page with her voice.
It also works both ways (`--two-way`): she hears your English in Telugu.

Built at HackGT 13 for Meta's "Bringing People Closer Together with AI" challenge. [idea.md](idea.md) has the full idea;
[demo.md](demo.md) has the demo call; [writeup.md](writeup.md) has the submission write-up.

## How it works
```
her phone ──WhatsApp──▶ Chrome on your laptop ──sound──▶ BlackHole ──▶ subtitles.py (the engine)
                                                                          │  Meta Muse Voice Transcribe: her Telugu, live
                                                                          │  IndicTrans2 1B on the laptop (raced against Meta Muse Spark): English
                                                                          │  Laya on the laptop: question or not, topic, which picture, what to ask
                                                                          │  Pocket TTS on the laptop: the English in her cloned voice
                                                                          ▼
                                     extension/ (the overlay) ◀── ws://localhost:8765 ── captions, questions, words, pictures
                                     calls/<call>/index.html  ◀── after the call: Meta Muse Spark writes the story page
```

| Piece | What it does |
|---|---|
| `subtitles.py` | The engine: listens, translates, decides, speaks, and sends everything to the overlay |
| `extension/` | The Chrome overlay: questions and words on the left, pictures and meanings on the right, captions in the middle |
| `lexicon.json`, `vocab.json`, `images/` | 308 Telugu words and proverbs, 46 English ones, phrases by topic, and 213 pictures |
| `progress.py` | How likely you are to know each word (Bayesian knowledge tracing with forgetting); known words stay in Telugu |
| `decide.py`, `curious.py`, `topics.py` | Laya's decisions: intent, topic, which questions to show, and replies in Telugu |
| `calls.py`, `prompts.py` | The story keeper (story pages, family dictionary) and the live "ask her" questions |
| `garden/` | Weave's app and iPhone app: past calls, words learned |
| `tools/eval_laya.py` | Laya's accuracy and speed, next to Muse Spark |
| `tools/fake_call.py` | A pretend call for building the overlay without audio or models |
| `subtitles.py --two-way`, `roles.py` | Both directions in one app: works out who speaks Telugu; your English → Telugu (IndicTrans2 en→indic + Meta's MMS voice) into WhatsApp Web's mic; waits while the listener talks; drops echo |

## Run it
Setup (audio, keys, models) is in [plan.md](plan.md). Then:
```
python subtitles.py --out "MacBook Air Speakers" --caller "Ammamma" --speak telugu
```
In Chrome, load `extension/` (see [extension/README.md](extension/README.md)), open the call, and press Alt+Shift+W.
No call handy? Run `python tools/fake_call.py` instead of `subtitles.py`.

## Privacy
- **The engine only talks to our own pages.** Its connection answers only the Weave extension and pages served from your laptop (`origins.py`), so other websites can't read the call.
- **Nothing personal is committed.** Her voice, the call recordings, the story pages and your progress stay on your laptop and are kept out of git.
- **Cloud models only get what they need:** Meta's models receive the call audio (for transcription) and text (for translation backup, stories and answers).

# Plan

## Setup (working)
**Audio**
1. `brew install --cask blackhole-2ch`. If it doesn't appear as a sound device, run `sudo killall coreaudiod` or reboot.
2. System Settings → Sound → Output → **BlackHole 2ch**, with the Mac volume at **100%**.
3. Make the call from **WhatsApp Web in Chrome** (web.whatsapp.com), not the WhatsApp Mac app.

**Main app**
4. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
5. `brew install espeak-ng` (the local voice uses it for words like *pulihora*).
6. Put `MODEL_API_KEY=<Meta Model API key>` in `.env` (gitignored; a pre-commit hook also blocks keys).

**Local translator (IndicTrans2, same English every time, ~0.3–0.5 s)**

7. Make a free account at huggingface.co, open https://huggingface.co/ai4bharat/indictrans2-indic-en-1B and click **Agree and access** (the model is gated).
8. `hf auth login` and paste a read token from https://huggingface.co/settings/tokens (saved on your Mac, not in the repo).
9. It needs its own virtualenv (IndicTrans2's model code needs transformers 4.51; the voice library needs 5.x):
   `python3 -m venv .venv-translate && .venv-translate/bin/pip install -r requirements-translate.txt`
10. In its own terminal, leave this running: `.venv-translate/bin/python translate_server.py` (first start downloads ~4 GB).

**Run**

11. `python subtitles.py --out "MacBook Air Speakers"` (or your headphones' name), then open http://localhost:8765.
    - No call handy? `python subtitles.py --file samples/telugu_grandma.wav`
    - If the translator isn't running it falls back to Muse Spark automatically; force it with `--translator muse`.

What we learned the hard way:
- **The WhatsApp Mac app plays straight to the speakers** and ignores the Mac's output setting. BlackHole stays silent and there's no BlackHole option in its menu. Chrome follows the Mac's output setting, so WhatsApp Web works.
- **When BlackHole is the output, the Mac volume slider controls what goes into BlackHole.** At 29% the call arrived at about 1% strength. Keep it at 100% and control loudness on the speaker side. `audio_loop.py` warns you if it's lower.
- The terminal app running the script needs microphone permission. The VS Code terminal worked for us.
- **Raw translation models mangle cultural words** ("My mother was a widow" for *grandma made pulihora*, "car" for *auto*). `lexicon.json` swaps known words for fixed plain English *before* translating, which fixed every case we tried. Add words there; the translator reloads it on save. Use plain English in `translate_as` ("tamarind rice", not "pulihora"): an English name right before a Telugu verb gets read as a person's name.

## Architecture

```
WhatsApp Web in Chrome (Mac output = BlackHole 2ch)
        │
        ▼
 ┌────────────────────── our app (Python) ──────────────────────┐
 │ audio in (BlackHole) ─► Muse Voice Transcribe (live words)    │
 │        │                                   │                  │
   │        │                                   │                  │
 │        │   lexicon.json ─► IndicTrans2 (local) ─► English      │
 │        │                         │                 │          │
 │        │          Laya (local, ~130ms)     dub-or-subtitle    │
 │        │          • category choice         decision (uses    │
 │        │          • slang flag              known-words list) │
 │        │            │          │              │        │      │
 │        │      word list     LLM writes      dub    subtitle   │
 │        │      → image       explanation     (TTS)    only      │
 │        │            │          │              │        │      │
 │        ▼            └────► overlay window ◄──┘────────┘      │
 │ mixer: original audio (lowered while dubbing) + TTS           │
 └───────────────────────────────┬──────────────────────────────┘
                                 ▼
                     real output device (headphones)
```

### Components
| Part | Choice | Notes |
|---|---|---|
| Capturing call audio | [BlackHole 2ch](https://github.com/ExistentialAudio/BlackHole) (`brew install --cask blackhole-2ch`) | Set the Mac's output to BlackHole and call from WhatsApp Web in Chrome. The WhatsApp Mac app skips BlackHole. |
| Audio input/output | `sounddevice` (Python) | Reads BlackHole and writes to the headphones. |
| Speech-to-text | **Muse Voice Transcribe** (Meta Model API, streaming, `languageBias: telugu`) | Words appear ~1–2 s after she starts talking; ends of utterances are detected by Muse. Much more accurate on Telugu than local Whisper. |
| Translation | **IndicTrans2 1B, local** (`translate_server.py`) + `lexicon.json` glossary | ~0.3–0.5 s per sentence, greedy decoding so the same input always gives the same English. Fallback: Muse Spark `muse-spark-1.1` (~0.8–1.5 s, online). NLLB 600M/1.3B were as fast but got food, vehicle and place words wrong. |
| Decisions | **Laya** `convaiinnovations/laya` (English checkpoint, `device="mps"`) | Load at startup; the first load takes ~35 s. |
| Words & phrases | **`lexicon.json`** (hard-coded) | 40 Telugu entries (food, vehicles, places, clothing, festivals, family, idioms) + English slang. Fixes translations, and will drive the image and explanation cards. |
| Images | a local `images/` folder, one file per `lexicon.json` id | Still to do. |
| Text-to-speech | **Kokoro-82M, local** (`mlx-audio`, voice `af_heart`) | 7 s of speech in ~0.6 s on the M4 after a ~4 s warm-up. Needs `brew install espeak-ng`. |
| On-screen overlay | an always-on-top window (Electron or a web page) fed over WebSocket | Shows subtitles, image cards and slang cards. |

### Laya questions (checked on this Mac)
```python
agent = laya.load("convaiinnovations/laya", device="mps")
Q = {
  "category": {"type": "choice", "instructions": "What kind of thing is mentioned?",
               "criteria": {"food": "a dish, snack, sweet or drink",
                            "vehicle": "rickshaw, scooter, bus, train",
                            "place": "temple, market, city, village",
                            "clothing": "saree, kurta, dupatta",
                            "festival": "Diwali, Holi, puja, wedding",
                            "none": "nothing concrete"}},
  "idiom": {"type": "noul",
            "instructions": "Does the English sentence use slang or a figure of speech whose meaning is not literal?"},
}
agent.predict({"original": hindi_text, "english": english_text}, Q)
```
What we learned from testing (script: `tools/laya_bench.py`):
- Show an image when `category != none` **and** the word list finds a match. Don't use a yes/no "is this visual?" question, because it was unreliable.
- Give Laya the English translation, and use the English checkpoint. The multilingual one was faster but much worse.
- Too many options hurts accuracy. For fuzzy image matching, narrow the options first with `laya.predict_shortlist`.

### Known-words list (translating less over time)
- Store `{phrase: {heard: n, asked: m}}` in SQLite.
- `heard < 3` → dub it in English.
- `3 ≤ heard < 8` → play the original audio and show a subtitle.
- `heard ≥ 8` → play the original, with a small faded subtitle or none.
- The "?" button on a subtitle adds to `asked` and moves the phrase back down a level.

## Risks
1. ~~**Audio routing**~~ solved with WhatsApp Web, BlackHole and `audio_loop.py` (see Audio setup).
2. **Echo:** use headphones. If our output plays through the laptop speakers, it leaks back into the call.
3. **Delay:** expect ~1–2 s after each sentence ends. Stream every stage and show subtitles before the dubbed voice is ready.
4. **Laya out of the box** is only okay at general questions. Keep the questions narrow. With time left over, fine-tune on ~200 labeled call sentences.

## Build order
1. ✅ **Audio loop:** WhatsApp → BlackHole → Python → headphones, with no processing, during a real call (`audio_loop.py`).
2. ✅ **Live subtitles:** Muse streams Telugu text into the overlay (`subtitles.py`, `muse.py`, `overlay.html`).
3. ✅ **Translation:** Muse Spark, sentence by sentence while she is still talking.
4. **Laya:** image cards (word list plus images) and slang cards (LLM explanation).
5. **Dubbing:** text-to-speech, with the original lowered underneath.
6. **Known-words list:** show the translation fading out over a demo call.
7. **Stretch:** the other direction (virtual mic), more languages, screen share.

## Team split (suggested)
- **Audio:** steps 1 and 5 (BlackHole, mixer, lowering the original, TTS)
- **Speech pipeline:** steps 2 and 3 (VAD, speech-to-text, translation)
- **Laya and content:** step 4 (questions, word list, image set, slang cards)
- **Frontend:** the overlay window and the known-words list

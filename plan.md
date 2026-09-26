# Plan

## Audio setup (working)
1. `brew install --cask blackhole-2ch`. If it doesn't appear as a sound device, run `sudo killall coreaudiod` or reboot.
2. System Settings → Sound → Output → **BlackHole 2ch**, with the Mac volume at **100%**.
3. Make the call from **WhatsApp Web in Chrome** (web.whatsapp.com), not the WhatsApp Mac app.
4. `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
5. `python audio_loop.py --out "MacBook Air Speakers"` (or your headphones' name).

What we learned the hard way:
- **The WhatsApp Mac app plays straight to the speakers** and ignores the Mac's output setting. BlackHole stays silent and there's no BlackHole option in its menu. Chrome follows the Mac's output setting, so WhatsApp Web works.
- **When BlackHole is the output, the Mac volume slider controls what goes into BlackHole.** At 29% the call arrived at about 1% strength. Keep it at 100% and control loudness on the speaker side. `audio_loop.py` warns you if it's lower.
- The terminal app running the script needs microphone permission. The VS Code terminal worked for us.

## Architecture

```
WhatsApp Web in Chrome (Mac output = BlackHole 2ch)
        │
        ▼
 ┌────────────────────── our app (Python) ──────────────────────┐
 │ audio in (BlackHole) ─► voice activity detection ─► segments  │
 │        │                                   │                  │
 │        │                    streaming speech-to-text          │
 │        │                    (Hindi / Hinglish)                │
 │        │                                   │                  │
 │        │                    translate ─► English text         │
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
| Voice activity detection | `silero-vad` or `webrtcvad` | Cuts audio into chunks at pauses in speech. |
| Speech-to-text | Deepgram Nova-3 (multi) or Sarvam | Has to handle Hindi mixed with English. Compare both on real audio. |
| Translation | Claude Haiku 4.5, streaming | The same call also writes the slang explanations. |
| Decisions | **Laya** `convaiinnovations/laya` (English checkpoint, `device="mps"`) | Load at startup; the first load takes ~35 s. |
| Images | a local `images/` folder plus `lexicon.json` | Maps Hindi, romanized and English words to image files. ~100 items to start. |
| Text-to-speech | ElevenLabs Flash (or similar low-latency voice) | Only for dubbed phrases. |
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
2. **Live subtitles:** voice activity detection plus speech-to-text, with Hindi text showing in the overlay.
3. **Translation:** English subtitles.
4. **Laya:** image cards (word list plus images) and slang cards (LLM explanation).
5. **Dubbing:** text-to-speech, with the original lowered underneath.
6. **Known-words list:** show the translation fading out over a demo call.
7. **Stretch:** the other direction (virtual mic), more languages, screen share.

## Team split (suggested)
- **Audio:** steps 1 and 5 (BlackHole, mixer, lowering the original, TTS)
- **Speech pipeline:** steps 2 and 3 (VAD, speech-to-text, translation)
- **Laya and content:** step 4 (questions, word list, image set, slang cards)
- **Frontend:** the overlay window and the known-words list

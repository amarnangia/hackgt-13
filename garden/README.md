# Weave: the call UI, progress and iPhone app

Everything in this folder is a layer on top of the translator. It reads the team's files (`lexicon.json`,
`images/`, `samples/call_script.json`, `progress.json`, `calls/`) and never changes them.

## During a call (the laptop)

### Captions right on top of the call (Chrome extension, set up once)

1. Chrome → `chrome://extensions` → turn on **Developer mode** (top right) → **Load unpacked** → pick `garden/extension`.
2. That's it. Whenever web.whatsapp.com is open, a small "Weave · Waiting for subtitles.py" pill sits over it.
   Start `python subtitles.py` and it opens into a caption bar over the call by itself: her Telugu as she speaks,
   the English, pictures and "Ask" prompts (and your side too with `--outgoing`). Drag it by its top edge, resize it
   from the corner, "–" tucks it away until her next line. It only needs `subtitles.py`, not the garden server.
3. After pulling new code, press the ↻ on the extension's card in `chrome://extensions`.

### The full app (optional, next to the call)

1. Start the translator as usual: `python subtitles.py --out "MacBook Air Speakers"`
   (no call handy? `python subtitles.py --file samples/telugu_two_turns.wav --out none`)
2. In a second terminal: `python3 -m garden` (standard library only, nothing to install)
3. Open **http://localhost:8770/app** and put it next to the WhatsApp Web window.

4. Click **Float over call** (bottom of the page). A small caption window pops out and stays on top of
   the WhatsApp window: her Telugu as she speaks, the English under it, pictures, and "Ask Ammamma" prompts.
   Drag it anywhere and resize it; the text scales. Tap an underlined word for its picture and meaning.
   Needs Chrome (it uses Document Picture-in-Picture); in other browsers use the full page.

**The garden (http://localhost:8770) grows from real calls.** While `subtitles.py` runs, every Telugu word she says plants or waters its plant, and the header says *On a call · growing live* (click it for the live captions). Calls already saved in `calls/` are planted when the server starts, once each. *Call stories* at the bottom lists each call's story page and the family dictionary.

**Weave opens the live call by itself** when `subtitles.py` starts (from the home screen; if you go back home during a call it stays there). When you stop `subtitles.py`, Weave shows the call's story (title, summary, stories, pictures, words) with a link to the full story page, and the home screen lists every saved call from `calls/`, newest first.

The badge at the top says **LIVE** when it's reading `subtitles.py` (port 8765). If you open the page first,
it plays a demo call and switches to the live call by itself once `subtitles.py` starts.

What it shows, from the pipeline's WebSocket messages:
- her Telugu as she speaks (`partial`), then the line (`original`), "translating", and the English (`english`)
- words kept in Telugu are underlined; tap one for the picture, meaning and pronunciation, or
  "Didn't know it" (sends `forget`, same as clicking it in overlay.html)
- "Asked you" on questions (`details`), photos inline (`picture`), a speaker icon once voiced (`voice`)
- "Ask Ammamma" cards with Telugu, pronunciation and meaning (`prompt`)
- your progress from `progress.json`, and a link to `calls/dictionary.html` once a call has been saved

overlay.html at http://localhost:8765 still works; both can be open at once.

Try it without the translator: `python3 -m garden --demo`, then http://localhost:8770/app
(`?demo=1` forces the demo call, `?reset=1` shows onboarding again, `?floatpreview=1` draws the
floating window inside the page, for browsers without Picture-in-Picture).

## Between calls (the phone)

- `ios/`: SwiftUI app + home-screen widget ("Next call: ask how she makes పులిహోర").
  `cd garden/ios && xcodegen && open Weave.xcodeproj`, then run on a simulator or your phone.
- `widget.js`: Scriptable version of the widget for phones without the app.
- `dashboard.html`: the older web progress dashboard at http://localhost:8770.

The phone reads live calls only if `subtitles.py` listens on the network (`serve(..., "0.0.0.0", ...)`);
by default it listens on the laptop only, which is all the call UI needs.

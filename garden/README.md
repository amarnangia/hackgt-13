# Weave: the call UI, progress and iPhone app

Everything in this folder is a layer on top of the translator. It reads the team's files (`lexicon.json`,
`images/`, `samples/call_script.json`, `progress.json`, `calls/`) and never changes them.

## During a call (the laptop)

### On top of the call (Chrome extension)

The overlay moved to [`extension/`](../extension/README.md) at the top of the repo: captions, "Curious?" questions,
topic words, pictures and meanings on top of the call, turned on with its toolbar button or Alt+Shift+W. (The old
caption bar that lived here was replaced by it.)

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

Try it without the translator: `python3 -m garden --demo`, then http://localhost:8770/app?demo=1
(without `?demo=1` the app waits for a real call instead of playing the scripted one)
(`?demo=1` forces the demo call, `?reset=1` shows onboarding again, `?floatpreview=1` draws the
floating window inside the page, for browsers without Picture-in-Picture).

## On the phone (iPhone app)

Everything comes from the Mac running `python3 -m garden`: the people you've called, each saved call with its story
and **her voice on every line**, the family dictionary (her voice saying each word), your progress, and the
"ask next time" questions (also on the home-screen widget). During a call the app shows it live: the Weave server
relays `subtitles.py` to the phone (`/api/live`), so `subtitles.py` doesn't need to change.

- Simulator: works as is (`http://localhost:8770`).
- Your iPhone: in the app, avatar → Settings → type the "phone widget URL" `python3 -m garden` prints; same Wi-Fi.
- With no Mac it shows the last calls and words it saw. **Demo mode** in Settings shows sample words and the
  scripted call instead, for presenting without the Mac.

## Between calls (the phone)

- `ios/`: SwiftUI app + home-screen widget ("Next call: ask how she makes పులిహోర").
  `cd garden/ios && xcodegen && open Weave.xcodeproj`, then run on a simulator or your phone.

The phone reads live calls only if `subtitles.py` listens on the network (`serve(..., "0.0.0.0", ...)`);
by default it listens on the laptop only, which is all the call UI needs.

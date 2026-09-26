# Weave: the call UI, progress and iPhone app

Everything in this folder is a layer on top of the translator. It reads the team's files (`lexicon.json`,
`images/`, `samples/call_script.json`, `progress.json`, `calls/`) and never changes them.

## During a call (the laptop)

1. Start the translator as usual: `python subtitles.py --out "MacBook Air Speakers"`
   (no call handy? `python subtitles.py --file samples/telugu_two_turns.wav --out none`)
2. In a second terminal: `python3 -m garden` (standard library only, nothing to install)
3. Open **http://localhost:8770/app** and put it next to the WhatsApp Web window.

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
(`?demo=1` forces the demo call, `?reset=1` shows onboarding again).

## Between calls (the phone)

- `ios/`: SwiftUI app + home-screen widget ("Next call: ask how she makes పులిహోర").
  `cd garden/ios && xcodegen && open Weave.xcodeproj`, then run on a simulator or your phone.
- `widget.js`: Scriptable version of the widget for phones without the app.
- `dashboard.html`: the older web progress dashboard at http://localhost:8770.

The phone reads live calls only if `subtitles.py` listens on the network (`serve(..., "0.0.0.0", ...)`);
by default it listens on the laptop only, which is all the call UI needs.

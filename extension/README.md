# Weave overlay (Chrome extension)

Puts Weave on top of the call in your Chrome tab (WhatsApp Web, Instagram, or any page) when you turn it on. The layout and message format are in
[../idea.md](../idea.md).

Everything sits at the edges, so the faces in the middle of the call stay clear (design notes: [DESIGN.md](DESIGN.md)):

- **Dock (top left):** the orb shows what Weave is doing (idle, listening, translating, speaking). Click it to hide or
  show everything. Next to it: **Questions and words**, **Pictures and meanings**, and **⋯** (the two-way
  "I speak English / తెలుగు" switch, and Hide). Hover the dock to see its status.
- **Questions and words (under the dock):** "Ask her" (opens by itself when there's a new one), "Curious?" questions
  (click one for the answer) and words for what you're talking about.
- **Pictures and meanings (top right):** pictures of what she mentions and what her sayings mean. Only there while
  there are some; click one to keep it.
- **Captions (bottom middle):** her words and the English, above the call's buttons. They fade away when nobody is
  talking. Click a word shown in Telugu if you don't know it.
- **Two-way calls** (`subtitles.py --two-way`): the language switch in the ⋯ menu tells the engine which language you
  speak, so it doesn't have to guess. It's remembered and sent again whenever the engine restarts.

It connects to the Weave engine on this Mac at `ws://localhost:8765`: either `subtitles.py`, or `tools/fake_call.py`
for a pretend call.

## Install
1. Open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked** and pick this `extension` folder.
2. Pin it: click the puzzle-piece icon in Chrome's toolbar and pin **Weave overlay**.
3. On your call's tab, click the Weave button (or press **Alt+Shift+W**) to turn it on. Press it again to hide or show
   it; clicking the orb does the same. It turns off when the page reloads.

After changing files here, click the reload icon on the extension in `chrome://extensions`, then reload the call page.

## Try it without a call
```
python tools/fake_call.py                               # a pretend call on ws://localhost:8765
python3 -m http.server 8799 --directory extension       # in another terminal
```
Open http://localhost:8799/dev.html. It's a stand-in call page that loads the overlay without installing the extension.

## Use a different engine address
In the extension's service worker console (`chrome://extensions` → Weave overlay → *service worker*), run:
`chrome.storage.local.set({ wsUrl: "ws://localhost:8765" })`, then reload the call page.

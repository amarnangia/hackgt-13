# Weave overlay (Chrome extension)

Puts Weave on top of the call in your Chrome tab (WhatsApp Web, Instagram, or any page) when you turn it on. The layout and message format are in
[../idea.md](../idea.md).

Weave keeps the faces in the middle of the call clear, and shows English only (design notes: [DESIGN.md](DESIGN.md)):

- **The line (bottom center, above the call's buttons):** vibrates with the call's sound. Turning Weave on also starts
  listening to the tab (Chrome tab capture; the sound is played straight back, so you still hear the call). Click the
  line to hide or show everything. Beside it: the words and pictures buttons, and in two-way calls **English / Telugu** (which
  language you speak).
- **Captions (right above the line):** the English, in a glass bubble while someone talks. Click an underlined word if
  you don't know it.
- **Ask her (top center):** what to say and what it means, when the talk pauses.
- **Words (top left):** a few words for what you're talking about, and questions; click one for the answer.
- **Pictures and meanings (top right):** each with what it is. Click one to keep it.

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

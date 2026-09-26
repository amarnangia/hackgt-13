# Weave overlay (Chrome extension)

Puts Weave on top of a WhatsApp Web or Instagram call in Chrome. The layout and message format are in
[../idea.md](../idea.md).

- **Left:** "Curious?" questions (click one for the answer) and words for what you're talking about.
- **Right:** pictures of what she mentions, and what her sayings mean.
- **Bottom:** her words and the English. Click a word shown in Telugu if you don't know it.

It connects to the Weave engine on this Mac at `ws://localhost:8765`: either `subtitles.py`, or `tools/fake_call.py`
for a pretend call.

## Install
1. Open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked** and pick this `extension` folder.
2. Open a call on https://web.whatsapp.com or https://www.instagram.com. The overlay appears by itself.
3. Anywhere else, click the Weave toolbar button (or press **Alt+Shift+W**) to show it. Press it again to hide it.
   The pill at the top middle also hides and shows it.

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

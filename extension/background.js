// Weave only appears when you turn it on: the toolbar button or Alt+Shift+W adds it to the current tab, and
// pressing again hides or shows it. It's gone after the page reloads.
// Turning it on also starts listening to the tab's sound (tab capture, in offscreen.html) so the overlay's line can
// move with the call's actual frequencies. Capturing a tab silences it, so offscreen.js plays the sound straight back.
const capturing = new Set();

async function toggle(tab) {
  if (!tab?.id || !/^https?:/.test(tab.url || "")) return;
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
  listen(tab.id).catch(() => {});   // no sound, no problem: the line then follows what Weave is doing
}

async function listen(tabId) {
  if (capturing.has(tabId)) return;
  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
  if (!(await chrome.offscreen.hasDocument?.())) {
    await chrome.offscreen.createDocument({ url: "offscreen.html", reasons: ["USER_MEDIA"], justification: "Show the call's sound as a moving line" });
  }
  capturing.add(tabId);
  chrome.runtime.sendMessage({ target: "offscreen", type: "start", tabId, streamId });
}

chrome.action.onClicked.addListener(toggle);
chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "toggle-overlay") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  toggle(tab);
});

// The sound's frequency bands, from offscreen.js to the overlay in that tab
chrome.runtime.onMessage.addListener((m) => {
  if (m?.target !== "background") return;
  if (m.type === "bands") chrome.tabs.sendMessage(m.tabId, { weave: "bands", bands: m.bands }).catch(() => {});
  if (m.type === "stopped") capturing.delete(m.tabId);
});
chrome.tabs.onRemoved.addListener((tabId) => capturing.delete(tabId));

// The toolbar button and Alt+Shift+W show or hide Weave on the current tab. On WhatsApp Web and Instagram the
// overlay is already there (manifest content_scripts); anywhere else this adds it.
async function toggle(tab) {
  if (!tab?.id || !/^https?:/.test(tab.url || "")) return;
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
}
chrome.action.onClicked.addListener(toggle);
chrome.commands.onCommand.addListener(async (command) => {
  if (command !== "toggle-overlay") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  toggle(tab);
});

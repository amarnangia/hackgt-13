// Weave only appears when you turn it on: the toolbar button or Alt+Shift+W adds it to the current tab, and
// pressing again hides or shows it. It's gone after the page reloads.
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

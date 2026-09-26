// Weave overlay: puts three panels on top of the call page, leaving the video in the middle free.
//   left      "Curious?" questions and words for the current topic
//   right     pictures and what sayings mean
//   captions  her words and the English, above the call controls
// Each panel is panel.html (an extension page) in its own frame, so the call site's security rules can't block its
// connection to the Weave engine on this Mac (ws://localhost:8765 by default; set "wsUrl" in chrome.storage.local
// to change it). background.js runs this when you turn Weave on; running it again shows or hides the overlay.
(() => {
  if (window.__weaveOverlay) {
    window.__weaveOverlay.toggle();
    return;
  }

  const Z = 2147483000;
  const host = document.createElement("div");
  host.id = "weave-overlay";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      iframe { position: fixed; z-index: ${Z}; border: 0; background: transparent; color-scheme: normal;
               transition: opacity .25s ease, transform .3s cubic-bezier(.2,.8,.2,1); }
      .hidden iframe { opacity: 0; pointer-events: none; }
      .hidden .side.left { transform: translateX(-24px); }
      .hidden .side.right { transform: translateX(24px); }
      .toggle { position: fixed; z-index: ${Z + 1}; top: 10px; left: 50%; transform: translateX(-50%); display: flex; gap: 6px;
                align-items: center; padding: 5px 12px 5px 9px; border-radius: 999px; border: 1px solid rgba(255,255,255,.14);
                background: rgba(12, 14, 18, .78); color: #eef0f3; font: 600 12px/1 system-ui, sans-serif; cursor: pointer;
                backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); box-shadow: 0 6px 20px rgba(0,0,0,.35); }
      .toggle:hover { background: rgba(24, 27, 33, .9); }
      .dot { width: 8px; height: 8px; border-radius: 50%; background: #6b7280; }
      .dot.on { background: #34d399; box-shadow: 0 0 0 3px rgba(52, 211, 153, .2); }
    </style>
    <div class="wrap">
      <iframe class="side left" title="Weave: questions and words" allowtransparency="true"></iframe>
      <iframe class="side right" title="Weave: pictures and meanings" allowtransparency="true"></iframe>
      <iframe class="captions" title="Weave: captions" allowtransparency="true"></iframe>
      <button class="toggle" title="Show or hide Weave (Alt+Shift+W)"><span class="dot"></span><span class="label">Weave</span></button>
    </div>`;
  document.documentElement.append(host);

  const wrap = root.querySelector(".wrap");
  const frames = { left: root.querySelector(".left"), right: root.querySelector(".right"), captions: root.querySelector(".captions") };
  const toggleButton = root.querySelector(".toggle");
  let captionsHeight = 150;

  // Side panels hug the edges; captions sit between them, above the call's own buttons at the bottom. In a narrow
  // window there's no room between the panels, so the captions span the bottom and the panels end above them.
  function layout() {
    const w = innerWidth, h = innerHeight;
    const gap = 12, top = 52, bottomBar = 96, minCaptions = 360;
    const side = Math.max(200, Math.min(320, Math.round(w * 0.22)));
    const between = w - 2 * (side + 2 * gap);
    const narrow = between < minCaptions;
    const capWidth = narrow ? w - 2 * gap : Math.min(780, between);
    const capTop = h - bottomBar - captionsHeight;
    const sideHeight = (narrow ? capTop - gap : h - gap) - top;
    Object.assign(frames.left.style, { left: `${gap}px`, top: `${top}px`, width: `${side}px`, height: `${Math.max(120, sideHeight)}px` });
    Object.assign(frames.right.style, { left: `${w - gap - side}px`, top: `${top}px`, width: `${side}px`, height: `${Math.max(120, sideHeight)}px` });
    Object.assign(frames.captions.style, {
      left: `${Math.round((w - capWidth) / 2)}px`, width: `${capWidth}px`, height: `${captionsHeight}px`, top: `${capTop}px`,
    });
  }

  function load(wsUrl) {
    const q = wsUrl ? `&ws=${encodeURIComponent(wsUrl)}` : "";
    for (const [part, frame] of Object.entries(frames)) frame.src = chrome.runtime.getURL(`panel.html?part=${part}${q}`);
  }

  // The captions panel reports its height (it grows with longer lines) and whether the engine is connected.
  addEventListener("message", (e) => {
    const m = e.data;
    if (!m || m.source !== "weave-panel") return;
    if (m.kind === "height" && m.part === "captions") {
      captionsHeight = Math.max(60, Math.min(260, Math.ceil(m.height)));
      layout();
    } else if (m.kind === "status") {
      root.querySelector(".dot").classList.toggle("on", !!m.connected);
      root.querySelector(".label").textContent = m.connected ? `Weave · ${m.name || "listening"}` : "Weave · waiting for the engine";
    }
  });

  let shown = true;
  function toggle(show = !shown) {
    shown = show;
    wrap.classList.toggle("hidden", !shown);
  }
  toggleButton.addEventListener("click", () => toggle());
  addEventListener("resize", layout);
  window.__weaveOverlay = { toggle };

  layout();
  try {
    chrome.storage.local.get("wsUrl", (s) => load(s?.wsUrl));
  } catch {
    load();
  }
})();

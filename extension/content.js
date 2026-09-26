// Weave overlay: floats over the call page and keeps the middle of the call (the faces) clear.
//   dock      top left: the orb (Weave's state; click to hide or show everything), the two panels, and a menu
//   left      under the dock, opened from it: "Ask her", "Curious?" questions and words for the current topic
//   right     top right: pictures and what sayings mean, only while there are some
//   captions  bottom middle, above the call's own buttons: subtitles that fade away when nobody is talking
// Each panel is panel.html (an extension page) in its own frame, so the call site's security rules can't block its
// connection to the Weave engine on this Mac (ws://localhost:8765 by default; set "wsUrl" in chrome.storage.local
// to change it). background.js runs this when you turn Weave on; running it again shows or hides the overlay.
(() => {
  if (window.__weaveOverlay) {
    window.__weaveOverlay.toggle();
    return;
  }

  const Z = 2147483000;
  const url = (p) => chrome.runtime.getURL(p);
  const icon = {
    ask: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a8.5 8.5 0 0 1-12.6 7.4L3 21l1.6-5.1A8.5 8.5 0 1 1 21 12z"/><path d="M9.8 9.6a2.3 2.3 0 0 1 4.4.8c0 1.5-2.2 2-2.2 3.1"/><path d="M12 16.4h.01"/></svg>`,
    pics: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3.5"/><circle cx="9" cy="10" r="1.8"/><path d="m21 16-4.6-4.6a1.5 1.5 0 0 0-2.1 0L6 19.5"/></svg>`,
    more: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5.5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18.5" cy="12" r="1.6"/></svg>`,
  };

  const host = document.createElement("div");
  host.id = "weave-overlay";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host { all: initial;
        --glass: rgba(20, 20, 22, .72); --blur: blur(24px) saturate(1.5);
        --inner: inset 0 1px 0 rgba(255,255,255,.06), inset 0 0 0 1px rgba(255,255,255,.05);
        --shadow: 0 24px 48px -16px rgba(0,0,0,.6), 0 4px 12px -4px rgba(0,0,0,.35);
        --text: #f4f5f7; --text-2: #a1a1aa; --text-3: #6b6b74;
        --grad: linear-gradient(135deg, #22d3ee 0%, #4f8cff 52%, #8b5cf6 100%);
        --ease-out: cubic-bezier(.16,1,.3,1); --ease-spring: cubic-bezier(.32,.72,0,1); --ease-in: cubic-bezier(.7,0,.84,0);
        --font: "Weave Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; }
      * { box-sizing: border-box; }
      button { all: unset; cursor: pointer; }

      /* ---- frames ---- */
      iframe { position: fixed; z-index: ${Z}; border: 0; background: transparent; color-scheme: normal; }
      .left { border-radius: 20px; background: var(--glass); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
              box-shadow: var(--inner), var(--shadow); transform-origin: 24px 0;
              transition: opacity 220ms var(--ease-out), transform 420ms var(--ease-spring), visibility 0s linear 0s; }
      .left:not(.open) { opacity: 0; transform: translateY(-10px) scale(.96); visibility: hidden; pointer-events: none;
              transition: opacity 160ms var(--ease-in), transform 220ms var(--ease-in), visibility 0s linear 220ms; }
      .right { -webkit-mask-image: linear-gradient(#000 calc(100% - 28px), transparent); mask-image: linear-gradient(#000 calc(100% - 28px), transparent);
              transition: opacity 260ms var(--ease-out), transform 420ms var(--ease-spring), height 420ms var(--ease-spring); }
      .right.empty, .right:not(.open) { opacity: 0; transform: translateX(14px); pointer-events: none; }
      .captions.idle { pointer-events: none; }
      .hidden iframe { opacity: 0 !important; transform: scale(.98) !important; pointer-events: none !important; visibility: hidden;
              transition: opacity 180ms var(--ease-in), transform 220ms var(--ease-in), visibility 0s linear 220ms !important; }

      /* ---- dock ---- */
      .dock { position: fixed; z-index: ${Z + 2}; top: 16px; left: 16px; height: 52px; padding: 6px; display: flex; align-items: center; gap: 2px;
              border-radius: 24px; background: var(--glass); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
              box-shadow: var(--inner), var(--shadow); font: 600 13px/1 var(--font); color: var(--text); -webkit-font-smoothing: antialiased;
              transition: padding 420ms var(--ease-spring); }
      .dock::before { content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1px; pointer-events: none;
              background: conic-gradient(from var(--weave-ang), rgba(34,211,238,0) 0deg, rgba(34,211,238,.9) 60deg, rgba(139,92,246,.9) 120deg, rgba(79,140,255,0) 200deg, rgba(79,140,255,0) 360deg);
              -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite: xor; mask-composite: exclude;
              opacity: .35; animation: weave-ang 7s linear infinite; transition: opacity 600ms var(--ease-out); }
      .dock[data-state="listening"]::before, .dock[data-state="speaking"]::before { opacity: 1; animation-duration: 3s; }
      .dock[data-state="thinking"]::before { opacity: .8; animation-duration: 1.6s; }
      .dock[data-state="off"]::before { opacity: 0; }
      @keyframes weave-ang { to { --weave-ang: 360deg; } }
      .status { max-width: 0; opacity: 0; overflow: hidden; white-space: nowrap; color: var(--text-2); font-weight: 600; letter-spacing: -.005em;
              transition: max-width 420ms var(--ease-spring), opacity 200ms var(--ease-out), padding 420ms var(--ease-spring); }
      .dock:hover .status, .dock.peek .status { max-width: 240px; opacity: 1; padding: 0 8px 0 6px; }
      .status b { color: var(--text); font-weight: 700; margin-right: 6px; }
      .items { display: flex; align-items: center; gap: 2px; max-width: 200px; overflow: hidden;
              transition: max-width 420ms var(--ease-spring), opacity 200ms var(--ease-out); }
      .hidden .items { max-width: 0; opacity: 0; }
      .sep { width: 1px; height: 20px; background: rgba(255,255,255,.08); margin: 0 6px; flex: none; }
      .dk { position: relative; width: 36px; height: 36px; border-radius: 18px; display: grid; place-items: center; color: var(--text-2); flex: none;
              transition: color 140ms var(--ease-out), background 140ms var(--ease-out), transform 140ms var(--ease-out), box-shadow 140ms var(--ease-out); }
      .dk svg { width: 18px; height: 18px; }
      .dk:hover { color: var(--text); background: rgba(255,255,255,.07); }
      .dk:active { transform: scale(.92); }
      .dk.on { color: #fff; background: rgba(79,140,255,.18); box-shadow: inset 0 0 0 1px rgba(79,140,255,.38); }
      .dk .badge { position: absolute; top: 7px; right: 7px; width: 7px; height: 7px; border-radius: 50%; background: var(--grad);
              box-shadow: 0 0 0 2px rgba(20,20,22,.95); transform: scale(0); transition: transform 320ms var(--ease-spring); }
      .dk.new .badge { transform: scale(1); }
      .dk[data-tip]:hover::after { content: attr(data-tip); position: absolute; top: calc(100% + 10px); left: 50%; transform: translateX(-50%);
              white-space: nowrap; padding: 6px 9px; border-radius: 8px; background: rgba(20,20,22,.94); box-shadow: var(--inner); color: var(--text);
              font: 600 11.5px/1 var(--font); pointer-events: none; animation: tip 200ms var(--ease-out) 350ms both; }
      @keyframes tip { from { opacity: 0; transform: translate(-50%, -3px); } to { opacity: 1; transform: translate(-50%, 0); } }

      /* ---- the orb ---- */
      .orb-btn { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 18px; flex: none; }
      .orb { position: relative; width: 32px; height: 32px; transition: transform 520ms var(--ease-spring), filter 420ms var(--ease-out), opacity 420ms var(--ease-out); }
      .orb i { position: absolute; inset: 0; border-radius: 50%; pointer-events: none; }
      .core { background: conic-gradient(from 0deg, #22d3ee, #4f8cff, #8b5cf6, #4f8cff, #22d3ee); animation: spin 14s linear infinite; }
      .shine { background: radial-gradient(circle at 34% 28%, rgba(255,255,255,.85), rgba(255,255,255,0) 36%),
                           radial-gradient(circle at 50% 50%, rgba(0,0,0,0) 52%, rgba(6,10,30,.38) 100%); }
      .glow { inset: -6px !important; background: radial-gradient(circle, rgba(79,140,255,.45), rgba(139,92,246,0) 68%); opacity: .5;
              transition: opacity 420ms var(--ease-out), transform 520ms var(--ease-spring); }
      .blob { opacity: 0; filter: blur(2.5px); transition: opacity 320ms var(--ease-out); }
      .b1 { background: linear-gradient(135deg, #22d3ee, #4f8cff); }
      .b2 { background: linear-gradient(135deg, #8b5cf6, #22d3ee); }
      .sweep { inset: -4px !important; opacity: 0; background: conic-gradient(from 0deg, rgba(255,255,255,0) 0 62%, rgba(165,243,252,.95) 100%);
               -webkit-mask: radial-gradient(circle, transparent 60%, #000 62%, #000 70%, transparent 72%); mask: radial-gradient(circle, transparent 60%, #000 62%, #000 70%, transparent 72%);
               transition: opacity 240ms var(--ease-out); }
      .ring { border: 1.5px solid rgba(96,165,250,.85); opacity: 0; }

      /* off: no engine */
      .orb[data-state="off"] { filter: grayscale(1) brightness(.7); opacity: .55; }
      .orb[data-state="off"] .core { animation-play-state: paused; }
      .orb[data-state="off"] .glow { opacity: 0; }
      /* idle: slow, low breathing */
      .orb[data-state="idle"] { animation: breathe 4.2s ease-in-out infinite; }
      @keyframes breathe { 0%, 100% { transform: scale(.9); opacity: .6; } 50% { transform: scale(1); opacity: .88; } }
      /* listening: a little bigger, liquid waves in the cool colors */
      .orb[data-state="listening"] { transform: scale(1.12); }
      .orb[data-state="listening"] .glow { opacity: .9; transform: scale(1.15); }
      .orb[data-state="listening"] .blob { opacity: .75; }
      .orb[data-state="listening"] .b1 { animation: morph 2.6s ease-in-out infinite; }
      .orb[data-state="listening"] .b2 { animation: morph 3.4s ease-in-out infinite reverse; }
      .orb[data-state="listening"] .core { animation-duration: 6s; }
      @keyframes morph {
        0%   { border-radius: 42% 58% 60% 40% / 45% 45% 55% 55%; transform: rotate(0deg) scale(1.22); }
        50%  { border-radius: 58% 42% 38% 62% / 58% 62% 38% 42%; transform: rotate(180deg) scale(1.36); }
        100% { border-radius: 42% 58% 60% 40% / 45% 45% 55% 55%; transform: rotate(360deg) scale(1.22); } }
      /* thinking: a fast sweep around a quickly turning gradient */
      .orb[data-state="thinking"] .core { animation-duration: .9s; }
      .orb[data-state="thinking"] .sweep { opacity: 1; animation: spin .9s linear infinite; }
      .orb[data-state="thinking"] .glow { opacity: .75; }
      /* speaking: waves radiating out, the core moving with the voice */
      .orb[data-state="speaking"] { transform: scale(calc(1.06 + var(--amp, 0) * .1)); transition-duration: 120ms; }
      .orb[data-state="speaking"] .glow { opacity: 1; transform: scale(calc(1.1 + var(--amp, 0) * .35)); transition-duration: 120ms; }
      .orb[data-state="speaking"] .ring { animation: radiate 1.5s var(--ease-out) infinite; }
      .orb[data-state="speaking"] .r2 { animation-delay: .5s; }
      .orb[data-state="speaking"] .r3 { animation-delay: 1s; }
      .orb[data-state="speaking"] .core { animation-duration: 3s; }
      @keyframes radiate { 0% { transform: scale(1); opacity: .85; } 100% { transform: scale(1.75); opacity: 0; } }
      @keyframes spin { to { transform: rotate(360deg); } }
      .hidden .orb { opacity: .7; }
      @media (prefers-reduced-motion: reduce) { .orb, .orb i { animation: none !important; } }

      /* ---- menu ---- */
      .menu { position: fixed; z-index: ${Z + 3}; top: 72px; min-width: 232px; padding: 6px; border-radius: 16px; background: rgba(20,20,22,.8);
              backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); box-shadow: var(--inner), var(--shadow);
              font: 600 13px/1 var(--font); color: var(--text); transform-origin: 0 0;
              opacity: 0; transform: translateY(-6px) scale(.96); pointer-events: none;
              transition: opacity 160ms var(--ease-in), transform 200ms var(--ease-in); }
      .menu.open { opacity: 1; transform: none; pointer-events: auto; transition: opacity 200ms var(--ease-out), transform 360ms var(--ease-spring); }
      .mi { display: flex; align-items: center; justify-content: space-between; gap: 14px; width: 100%; padding: 10px; border-radius: 10px; box-sizing: border-box; }
      button.mi:hover { background: rgba(255,255,255,.06); }
      .mi small { color: var(--text-3); font-weight: 600; font-size: 11px; }
      .mi .hint { color: var(--text-3); font-weight: 600; font-size: 11px; margin-top: 4px; }
      .seg { display: flex; padding: 3px; gap: 2px; border-radius: 999px; background: rgba(255,255,255,.05); }
      .seg button { padding: 5px 10px; border-radius: 999px; color: var(--text-2); font-size: 12px; transition: color 140ms, background 140ms; }
      .seg button:hover { color: var(--text); }
      .seg button.on { background: var(--grad); color: #fff; }
      .menu hr { border: 0; height: 1px; background: rgba(255,255,255,.06); margin: 4px 6px; }
    </style>
    <div class="wrap">
      <iframe class="right open empty" title="Weave: pictures and meanings" allowtransparency="true"></iframe>
      <iframe class="captions idle" title="Weave: captions" allowtransparency="true"></iframe>
      <iframe class="left" title="Weave: questions and words" allowtransparency="true"></iframe>
      <nav class="dock" aria-label="Weave">
        <button class="orb-btn" title="Show or hide Weave (Alt+Shift+W)" aria-label="Show or hide Weave">
          <span class="orb" data-state="off"><i class="glow"></i><i class="ring r1"></i><i class="ring r2"></i><i class="ring r3"></i>
            <i class="blob b1"></i><i class="blob b2"></i><i class="core"></i><i class="sweep"></i><i class="shine"></i></span>
        </button>
        <span class="status"><b>Weave</b><span class="st">Waiting for the Weave engine</span></span>
        <span class="items">
          <span class="sep"></span>
          <button class="dk" data-panel="left" data-tip="Questions and words" aria-label="Questions and words">${icon.ask}<i class="badge"></i></button>
          <button class="dk on" data-panel="right" data-tip="Pictures and meanings" aria-label="Pictures and meanings">${icon.pics}<i class="badge"></i></button>
          <button class="dk" data-panel="menu" data-tip="More" aria-label="More">${icon.more}</button>
        </span>
      </nav>
      <div class="menu" role="menu"></div>
    </div>`;
  document.documentElement.append(host);

  // The dock's turning edge needs an animatable angle; custom properties can only be registered on the page itself.
  try { CSS.registerProperty({ name: "--weave-ang", syntax: "<angle>", inherits: false, initialValue: "0deg" }); } catch {}

  // The geometric face from the extension, for the dock (the panels load it themselves). Falls back to the system font.
  try {
    const face = new FontFace("Weave Manrope", `url(${url("fonts/manrope.woff2")})`, { weight: "200 800" });
    face.load().then((f) => document.fonts.add(f)).catch(() => {});
  } catch {}

  const $ = (s) => root.querySelector(s);
  const wrap = $(".wrap"), dock = $(".dock"), orb = $(".orb"), menu = $(".menu");
  const frames = { left: $(".left"), right: $(".right"), captions: $(".captions") };
  const buttons = { left: $('[data-panel="left"]'), right: $('[data-panel="right"]'), menu: $('[data-panel="menu"]') };
  const size = { right: 0 };
  const CAPTIONS_H = 230;
  const ui = { shown: true, left: false, right: true, roles: null, state: "off", connected: false };

  // ---- layout: edges only; the middle of the call stays clear ----
  function layout() {
    const w = innerWidth, h = innerHeight, m = 16;
    const controls = 104;                                   // the call's own buttons along the bottom
    const capWidth = Math.min(820, w - 2 * m);
    const capTop = h - controls - CAPTIONS_H;               // a fixed box: the words move inside it, the frame never does
    const top = m + 48 + 10;                                // under the dock
    const leftWidth = Math.min(340, w - 2 * m);
    const leftHeight = Math.max(220, Math.min(560, h - controls - 150 - top));   // stops above where the caption words sit
    const rightWidth = Math.max(260, Math.min(340, Math.round(w * 0.26)));
    const rightMax = h - controls - 230;                    // leaves the bottom-right corner for your own camera tile
    Object.assign(frames.left.style, { left: `${m}px`, top: `${top}px`, width: `${leftWidth}px`, height: `${leftHeight}px` });
    Object.assign(frames.right.style, { right: `${m}px`, top: `${m}px`, width: `${rightWidth}px`, height: `${Math.max(1, Math.min(rightMax, size.right))}px` });
    Object.assign(frames.captions.style, { left: `${Math.round((w - capWidth) / 2)}px`, width: `${capWidth}px`,
      top: `${capTop}px`, height: `${CAPTIONS_H}px` });
    const r = buttons.menu.getBoundingClientRect();
    menu.style.left = `${Math.max(m, Math.round(r.right - 232))}px`;
  }

  function load(wsUrl) {
    const q = wsUrl ? `&ws=${encodeURIComponent(wsUrl)}` : "";
    for (const [part, frame] of Object.entries(frames)) frame.src = url(`panel.html?part=${part}${q}`);
  }

  // ---- dock ----
  function setPanel(part, open) {
    ui[part] = open;
    frames[part].classList.toggle("open", open);
    buttons[part].classList.toggle("on", open);
    if (open) buttons[part].classList.remove("new");
  }
  function peek(ms = 2400) {
    dock.classList.add("peek");
    clearTimeout(peek.t); peek.t = setTimeout(() => dock.classList.remove("peek"), ms);
  }
  function renderMenu() {
    const lang = ui.roles ? `<div class="mi"><div>I speak${ui.roles.sure ? "" : `<div class="hint">Weave is guessing</div>`}</div>
        <span class="seg">${[["en", "English"], ["te", "తెలుగు"]].map(([k, v]) => `<button data-lang="${k}" class="${ui.roles.you === k ? "on" : ""}">${v}</button>`).join("")}</span></div><hr>` : "";
    menu.innerHTML = `${lang}<button class="mi" data-act="hide">Hide Weave <small>⌥⇧W</small></button>`;
  }
  function openMenu(open) {
    if (open) { renderMenu(); layout(); }
    menu.classList.toggle("open", open);
    buttons.menu.classList.toggle("on", open);
  }
  $(".orb-btn").addEventListener("click", () => toggle());
  buttons.left.addEventListener("click", () => setPanel("left", !ui.left));
  buttons.right.addEventListener("click", () => setPanel("right", !ui.right));
  buttons.menu.addEventListener("click", (e) => { e.stopPropagation(); openMenu(!menu.classList.contains("open")); });
  menu.addEventListener("click", (e) => {
    e.stopPropagation();
    const lang = e.target.closest("[data-lang]");
    if (lang) {
      frames.captions.contentWindow?.postMessage({ source: "weave-dock", kind: "i_speak", lang: lang.dataset.lang }, "*");
      ui.roles = { ...ui.roles, you: lang.dataset.lang, sure: true }; renderMenu();
    }
    if (e.target.closest('[data-act="hide"]')) { openMenu(false); toggle(false); }
  });
  root.addEventListener("click", () => openMenu(false));
  addEventListener("click", () => openMenu(false));
  addEventListener("keydown", (e) => { if (e.key === "Escape") openMenu(false); });

  // Speaking: the orb moves with a voice-like envelope (the page can't hear the engine's audio itself)
  let amp = 0, ampTimer = 0;
  function setOrb(state) {
    if (state === ui.state) return;
    ui.state = state;
    orb.dataset.state = state;
    dock.dataset.state = state;
    clearInterval(ampTimer);
    if (state === "speaking") ampTimer = setInterval(() => { amp += (Math.random() - amp) * 0.55; orb.style.setProperty("--amp", amp.toFixed(3)); }, 110);
  }

  // ---- messages from the panels ----
  addEventListener("message", (e) => {
    const m = e.data;
    if (!m || m.source !== "weave-panel") return;
    if (m.kind === "height" && m.part === "right") {
      size.right = Math.max(0, Math.min(2000, Math.ceil(m.height)));
      frames.right.classList.toggle("empty", !size.right);
      layout();
    } else if (m.kind === "idle") {
      frames.captions.classList.toggle("idle", !!m.idle);
    } else if (m.kind === "status") {
      if (m.connected !== ui.connected) { ui.connected = m.connected; peek(3200); }
      setOrb(m.state || (m.connected ? "idle" : "off"));
      $(".st").textContent = m.text || "";
    } else if (m.kind === "roles") {
      ui.roles = m.roles;
      if (menu.classList.contains("open")) renderMenu();
    } else if (m.kind === "attention") {
      if (m.part === "right" && m.what === "ask") setPanel("right", true);       // "Ask her" is worth opening for
      else if (m.part === "left" && !ui.left) buttons.left.classList.add("new");
      else if (m.part === "right" && !ui.right) buttons.right.classList.add("new");
    }
  });

  function toggle(show = !ui.shown) {
    ui.shown = show;
    wrap.classList.toggle("hidden", !show);
    if (!show) openMenu(false);
  }
  addEventListener("resize", layout);
  window.__weaveOverlay = { toggle };

  layout();
  peek(3200);
  try {
    chrome.storage.local.get("wsUrl", (s) => load(s?.wsUrl));
  } catch {
    load();
  }
})();

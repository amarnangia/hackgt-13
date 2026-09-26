// Weave overlay: floats over the call page and keeps the faces clear.
//   top       "Ask her": a frosted pill, top center, that comes down when the talk pauses
//   left      the dictionary feed (words, then "Curious?" questions), middle left
//   float     pictures and meanings as small bubbles that spring up above the captions, on the right
//   captions  the translation bubble, bottom center, directly above...
//   the orb   ...Weave's state (idle, listening, translating, speaking). Click it to hide or show everything; hover it
//             for the panel buttons, the menu (the two-way "I speak" switch, Hide) and what Weave is doing.
// Each panel is panel.html (an extension page) in its own frame, so the call site's security rules can't block its
// connection to the Weave engine on this Mac (ws://localhost:8765 by default; set "wsUrl" in chrome.storage.local
// to change it). background.js runs this when you turn Weave on; running it again shows or hides the overlay.
// Every frame is placed once per size change and shown, hidden and moved only with transform and opacity.
(() => {
  if (window.__weaveOverlay) {
    window.__weaveOverlay.toggle();
    return;
  }

  const Z = 2147483000;
  const url = (p) => chrome.runtime.getURL(p);
  const icon = {
    words: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/><path d="M9 8h7M9 12h5"/></svg>`,
    pics: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3.5"/><circle cx="9" cy="10" r="1.8"/><path d="m21 16-4.6-4.6a1.5 1.5 0 0 0-2.1 0L6 19.5"/></svg>`,
    more: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5.5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="18.5" cy="12" r="1.7"/></svg>`,
  };

  const host = document.createElement("div");
  host.id = "weave-overlay";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host { all: initial;
        --glass: rgba(18, 18, 20, .66); --blur: blur(22px) saturate(1.6);
        --inner: inset 0 1px 0 rgba(255,255,255,.07), inset 0 0 0 1px rgba(255,255,255,.05);
        --shadow: 0 24px 48px -16px rgba(0,0,0,.65), 0 4px 12px -4px rgba(0,0,0,.4);
        --text: #f4f5f7; --text-2: #a1a1aa; --text-3: #6b6b74;
        --grad: linear-gradient(135deg, #22d3ee 0%, #4f8cff 50%, #7c3aed 100%);
        --spring: cubic-bezier(.34,1.56,.64,1); --ease-out: cubic-bezier(.16,1,.3,1); --ease-sheet: cubic-bezier(.32,.72,0,1); --ease-in: cubic-bezier(.7,0,.84,0);
        --font: "Weave Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; }
      * { box-sizing: border-box; }
      button { all: unset; cursor: pointer; }

      /* ---- frames: placed once, then only transform + opacity move ---- */
      iframe { position: fixed; left: 0; top: 0; z-index: ${Z}; border: 0; background: transparent; color-scheme: normal;
               transform: var(--at); will-change: transform, opacity; }
      .glass { border-radius: 22px; background: var(--glass); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
               box-shadow: var(--inner), var(--shadow); }
      .top { border-radius: 26px; box-shadow: var(--inner), 0 18px 50px -12px rgba(124,58,237,.45), var(--shadow);
             transition: opacity 420ms var(--ease-out), transform 560ms var(--spring); }
      .top.off { opacity: 0; transform: var(--at) translate3d(0, -18px, 0) scale(.96); pointer-events: none;
             transition: opacity 320ms var(--ease-in), transform 360ms var(--ease-in); }
      .left { transition: opacity 260ms var(--ease-out), transform 460ms var(--ease-sheet); }
      .left.off { opacity: 0; transform: var(--at) translate3d(-16px, 0, 0) scale(.98); pointer-events: none;
             transition: opacity 180ms var(--ease-in), transform 220ms var(--ease-in); }
      .float { transition: opacity 260ms var(--ease-out); }
      .float.off { opacity: 0; pointer-events: none; }
      .captions { border-radius: 24px; transition: opacity 420ms var(--ease-out), transform 520ms var(--ease-sheet); }
      .captions.off { opacity: 0; transform: var(--at) translate3d(0, 10px, 0) scale(.98); pointer-events: none;
             transition: opacity 700ms var(--ease-in), transform 700ms var(--ease-in); }
      .hidden iframe { opacity: 0 !important; pointer-events: none !important; }

      /* ---- the orb and its controls, bottom center ---- */
      .core { position: fixed; z-index: ${Z + 2}; left: 50%; width: 0; height: 56px; font: 700 12.5px/1 var(--font); color: var(--text);
              -webkit-font-smoothing: antialiased; }
      .orb-btn { position: absolute; left: -28px; top: 0; width: 56px; height: 56px; border-radius: 50%; display: grid; place-items: center; }
      .orb-btn::after { content: ""; position: absolute; top: 4px; right: 4px; width: 9px; height: 9px; border-radius: 50%; background: var(--grad);
              box-shadow: 0 0 0 2px #121212; transform: scale(0); transition: transform 320ms var(--spring); }
      .core.new .orb-btn::after { transform: scale(1); }
      .side { position: absolute; top: 6px; height: 44px; display: flex; align-items: center; gap: 6px; opacity: 0; pointer-events: none;
              transition: opacity 180ms var(--ease-in), transform 240ms var(--ease-in); }
      .side.l { right: 28px; padding-right: 10px; transform: translate3d(14px, 0, 0) scale(.9); transform-origin: right center; }
      .side.r { left: 28px; padding-left: 10px; transform: translate3d(-14px, 0, 0) scale(.9); transform-origin: left center; }
      .core:hover .side, .core:focus-within .side, .core.open .side { opacity: 1; transform: none; pointer-events: auto;
              transition: opacity 220ms var(--ease-out), transform 420ms var(--spring); }
      .ctl { position: relative; width: 40px; height: 40px; border-radius: 20px; display: grid; place-items: center; color: var(--text-2);
              background: var(--glass); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); box-shadow: var(--inner), var(--shadow);
              transition: color 140ms var(--ease-out), background 140ms var(--ease-out), transform 140ms var(--ease-out); }
      .ctl svg { width: 18px; height: 18px; }
      .ctl:hover { color: #fff; }
      .ctl:active { transform: scale(.9); }
      .ctl.on { color: #fff; background: rgba(79,140,255,.26); box-shadow: var(--inner), inset 0 0 0 1px rgba(79,140,255,.45), var(--shadow); }
      .ctl .badge { position: absolute; top: 6px; right: 6px; width: 7px; height: 7px; border-radius: 50%; background: var(--grad);
              box-shadow: 0 0 0 2px rgba(18,18,20,.95); transform: scale(0); transition: transform 320ms var(--spring); }
      .ctl.new .badge { transform: scale(1); }
      .status { height: 40px; padding: 0 14px; border-radius: 20px; display: flex; align-items: center; gap: 7px; white-space: nowrap; color: var(--text-2);
              background: var(--glass); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); box-shadow: var(--inner), var(--shadow); }
      .status b { color: var(--text); }

      /* the orb: every state is transform, opacity or a turning gradient (no layout) */
      .orb { position: relative; width: 44px; height: 44px; transition: transform 520ms var(--ease-sheet), opacity 420ms var(--ease-out), filter 420ms var(--ease-out); }
      .orb i { position: absolute; inset: 0; border-radius: 50%; pointer-events: none; }
      .core-i { background: conic-gradient(from 0deg, #22d3ee, #4f8cff, #7c3aed, #4f8cff, #22d3ee); animation: spin 14s linear infinite; }
      .shine { background: radial-gradient(circle at 34% 28%, rgba(255,255,255,.9), rgba(255,255,255,0) 36%),
                           radial-gradient(circle at 50% 50%, rgba(0,0,0,0) 52%, rgba(6,10,30,.4) 100%); }
      .halo { inset: -14px !important; background: radial-gradient(circle, rgba(79,140,255,.55), rgba(124,58,237,.18) 45%, rgba(124,58,237,0) 70%);
              opacity: .45; transition: opacity 420ms var(--ease-out), transform 520ms var(--ease-sheet); }
      .blob { opacity: 0; filter: blur(3px); transition: opacity 320ms var(--ease-out); }
      .b1 { background: linear-gradient(135deg, #22d3ee, #4f8cff); }
      .b2 { background: linear-gradient(135deg, #7c3aed, #22d3ee); }
      .sweep { inset: -5px !important; opacity: 0; background: conic-gradient(from 0deg, rgba(255,255,255,0) 0 62%, rgba(165,243,252,.95) 100%);
               -webkit-mask: radial-gradient(circle, transparent 60%, #000 62%, #000 70%, transparent 72%); mask: radial-gradient(circle, transparent 60%, #000 62%, #000 70%, transparent 72%);
               transition: opacity 240ms var(--ease-out); }
      .ring { border: 1.5px solid rgba(96,165,250,.85); opacity: 0; }
      .orb[data-state="off"] { filter: grayscale(1) brightness(.7); opacity: .55; }
      .orb[data-state="off"] .core-i { animation-play-state: paused; }
      .orb[data-state="off"] .halo { opacity: 0; }
      /* idle: a slow, low pulse */
      .orb[data-state="idle"] { animation: breathe 4.2s ease-in-out infinite; }
      @keyframes breathe { 0%, 100% { transform: scale(.9); opacity: .62; } 50% { transform: scale(1); opacity: .9; } }
      /* listening: a little bigger, liquid waves in cyan and violet */
      .orb[data-state="listening"] { transform: scale(1.1); }
      .orb[data-state="listening"] .halo { opacity: .9; transform: scale(1.12); }
      .orb[data-state="listening"] .blob { opacity: .75; }
      .orb[data-state="listening"] .b1 { animation: morph 2.6s ease-in-out infinite; }
      .orb[data-state="listening"] .b2 { animation: morph 3.4s ease-in-out infinite reverse; }
      .orb[data-state="listening"] .core-i { animation-duration: 6s; }
      @keyframes morph {
        0%   { border-radius: 42% 58% 60% 40% / 45% 45% 55% 55%; transform: rotate(0deg) scale(1.2); }
        50%  { border-radius: 58% 42% 38% 62% / 58% 62% 38% 42%; transform: rotate(180deg) scale(1.34); }
        100% { border-radius: 42% 58% 60% 40% / 45% 45% 55% 55%; transform: rotate(360deg) scale(1.2); } }
      /* thinking: a fast sweep */
      .orb[data-state="thinking"] .core-i { animation-duration: .9s; }
      .orb[data-state="thinking"] .sweep { opacity: 1; animation: spin .9s linear infinite; }
      .orb[data-state="thinking"] .halo { opacity: .75; }
      /* speaking: glowing, with waves going out */
      .orb[data-state="speaking"] { transform: scale(calc(1.06 + var(--amp, 0) * .1)); transition-duration: 120ms; }
      .orb[data-state="speaking"] .halo { opacity: 1; transform: scale(calc(1.15 + var(--amp, 0) * .4)); transition-duration: 120ms; }
      .orb[data-state="speaking"] .ring { animation: radiate 1.5s var(--ease-out) infinite; }
      .orb[data-state="speaking"] .r2 { animation-delay: .5s; }
      .orb[data-state="speaking"] .r3 { animation-delay: 1s; }
      .orb[data-state="speaking"] .core-i { animation-duration: 3s; }
      @keyframes radiate { 0% { transform: scale(1); opacity: .85; } 100% { transform: scale(1.8); opacity: 0; } }
      @keyframes spin { to { transform: rotate(360deg); } }
      .hidden .orb { opacity: .6; }
      @media (prefers-reduced-motion: reduce) { .orb, .orb i { animation: none !important; } }

      /* ---- menu, above the orb ---- */
      .menu { position: fixed; z-index: ${Z + 3}; left: 50%; min-width: 236px; padding: 6px; border-radius: 18px; background: rgba(18,18,20,.94);
              backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); box-shadow: var(--inner), var(--shadow);
              font: 700 13px/1 var(--font); color: var(--text); transform-origin: 50% 100%;
              opacity: 0; transform: translate3d(-50%, 8px, 0) scale(.95); pointer-events: none;
              transition: opacity 160ms var(--ease-in), transform 200ms var(--ease-in); }
      .menu.open { opacity: 1; transform: translate3d(-50%, 0, 0); pointer-events: auto; transition: opacity 200ms var(--ease-out), transform 380ms var(--spring); }
      .mi { display: flex; align-items: center; justify-content: space-between; gap: 14px; width: 100%; padding: 10px; border-radius: 12px; box-sizing: border-box; }
      button.mi:hover { background: rgba(255,255,255,.06); }
      .mi small { color: var(--text-3); font-size: 11px; }
      .mi .hint { color: var(--text-3); font-size: 11px; margin-top: 4px; font-weight: 600; }
      .seg { display: flex; padding: 3px; gap: 2px; border-radius: 999px; background: rgba(255,255,255,.05); }
      .seg button { padding: 5px 10px; border-radius: 999px; color: var(--text-2); font-size: 12px; transition: color 140ms, background 140ms; }
      .seg button:hover { color: var(--text); }
      .seg button.on { background: var(--grad); color: #fff; }
      .menu hr { border: 0; height: 1px; background: rgba(255,255,255,.06); margin: 4px 6px; }
    </style>
    <div class="wrap">
      <iframe class="left glass" title="Weave: words and questions" allowtransparency="true"></iframe>
      <iframe class="float off" title="Weave: pictures and meanings" allowtransparency="true"></iframe>
      <iframe class="captions glass off" title="Weave: captions" allowtransparency="true"></iframe>
      <iframe class="top glass off" title="Weave: ask her" allowtransparency="true"></iframe>
      <div class="core">
        <div class="side l">
          <button class="ctl on" data-panel="left" aria-label="Words and questions" title="Words and questions">${icon.words}<i class="badge"></i></button>
          <button class="ctl on" data-panel="float" aria-label="Pictures and meanings" title="Pictures and meanings">${icon.pics}<i class="badge"></i></button>
        </div>
        <button class="orb-btn" title="Show or hide Weave (Alt+Shift+W)" aria-label="Show or hide Weave">
          <span class="orb" data-state="off"><i class="halo"></i><i class="ring r1"></i><i class="ring r2"></i><i class="ring r3"></i>
            <i class="blob b1"></i><i class="blob b2"></i><i class="core-i"></i><i class="sweep"></i><i class="shine"></i></span>
        </button>
        <div class="side r">
          <button class="ctl" data-panel="menu" aria-label="More" title="More">${icon.more}</button>
          <span class="status"><b>Weave</b><span class="st">Waiting for the Weave engine</span></span>
        </div>
      </div>
      <div class="menu" role="menu"></div>
    </div>`;
  document.documentElement.append(host);

  // The geometric face from the extension, for the controls (the panels load it themselves). Falls back to the system font.
  try {
    const face = new FontFace("Weave Manrope", `url(${url("fonts/manrope.woff2")})`, { weight: "200 800" });
    face.load().then((f) => document.fonts.add(f)).catch(() => {});
  } catch {}

  const $ = (s) => root.querySelector(s);
  const wrap = $(".wrap"), core = $(".core"), orb = $(".orb"), menu = $(".menu");
  const frames = { top: $(".top"), left: $(".left"), float: $(".float"), captions: $(".captions") };
  const buttons = { left: $('[data-panel="left"]'), float: $('[data-panel="float"]'), menu: $('[data-panel="menu"]') };
  const size = { top: [0, 0], left: 0, float: 0 };
  const ui = { shown: true, left: true, float: true, ask: false, idle: true, roles: null, state: "off", connected: false };

  // ---- layout: placed with transforms; sizes change only when content does ----
  const M = 16, ORB_BOTTOM = 92, ORB = 56, CAP_H = 148;   // ORB_BOTTOM clears the call's own buttons
  function place(frame, x, y, w, h) {
    frame.style.width = `${Math.round(w)}px`;
    frame.style.height = `${Math.max(1, Math.round(h))}px`;
    frame.style.setProperty("--at", `translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`);   // the class rules add to this
  }
  function layout() {
    const w = innerWidth, h = innerHeight;
    // bottom center: the orb, and the translation bubble right above it
    core.style.bottom = `${ORB_BOTTOM}px`;
    const leftW = Math.min(300, w - 2 * M);
    const capW = Math.max(Math.min(360, w - 2 * M), Math.min(700, w - 2 * (M + leftW + 12))), capY = h - ORB_BOTTOM - ORB - 12 - CAP_H;
    place(frames.captions, (w - capW) / 2, capY, capW, CAP_H);
    menu.style.bottom = `${ORB_BOTTOM + ORB + 12}px`;
    // top center: the "Ask her" pill
    const [tw, th] = size.top;
    place(frames.top, (w - (tw || 620)) / 2, M, tw || 620, th || 1);
    // left: the dictionary feed, from the top-left corner down the whole left edge
    place(frames.left, M, M, leftW, h - 2 * M);
    // float: word bubbles rising from just above the bubble's right end
    const fw = 310, fh = Math.min(size.float || 1, capY - M - 96);
    place(frames.float, Math.min(w - M - fw, (w + capW) / 2 - fw + 60), capY - 10 - fh, fw, fh);
  }
  function load(wsUrl) {
    const q = wsUrl ? `&ws=${encodeURIComponent(wsUrl)}` : "";
    for (const [part, frame] of Object.entries(frames)) frame.src = url(`panel.html?part=${part}${q}`);
  }
  function refresh() {
    frames.top.classList.toggle("off", !ui.ask);
    frames.left.classList.toggle("off", !ui.left || !size.left);
    frames.float.classList.toggle("off", !ui.float || !size.float);
    frames.captions.classList.toggle("off", ui.idle);
    core.classList.toggle("new", [buttons.left, buttons.float].some((b) => b.classList.contains("new")));
  }

  // ---- controls ----
  function setPanel(part, open) {
    ui[part] = open;
    buttons[part].classList.toggle("on", open);
    if (open) buttons[part].classList.remove("new");
    refresh();
  }
  function renderMenu() {
    const lang = ui.roles ? `<div class="mi"><div>I speak${ui.roles.sure ? "" : `<div class="hint">Weave is guessing</div>`}</div>
        <span class="seg">${[["en", "English"], ["te", "తెలుగు"]].map(([k, v]) => `<button data-lang="${k}" class="${ui.roles.you === k ? "on" : ""}">${v}</button>`).join("")}</span></div><hr>` : "";
    menu.innerHTML = `${lang}<button class="mi" data-act="hide">Hide Weave <small>⌥⇧W</small></button>`;
  }
  function openMenu(open) {
    if (open) renderMenu();
    menu.classList.toggle("open", open);
    buttons.menu.classList.toggle("on", open);
    core.classList.toggle("open", open);   // keep the controls out while the menu is up
  }
  $(".orb-btn").addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
  buttons.left.addEventListener("click", (e) => { e.stopPropagation(); setPanel("left", !ui.left); });
  buttons.float.addEventListener("click", (e) => { e.stopPropagation(); setPanel("float", !ui.float); });
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
  addEventListener("click", () => openMenu(false));
  addEventListener("keydown", (e) => { if (e.key === "Escape") openMenu(false); });

  // Speaking: the orb moves with a voice-like envelope (the page can't hear the engine's audio itself)
  let amp = 0, ampTimer = 0;
  function setOrb(state) {
    if (state === ui.state) return;
    ui.state = state;
    orb.dataset.state = state;
    clearInterval(ampTimer);
    if (state === "speaking") ampTimer = setInterval(() => { amp += (Math.random() - amp) * 0.55; orb.style.setProperty("--amp", amp.toFixed(3)); }, 110);
  }

  // ---- messages from the panels ----
  addEventListener("message", (e) => {
    const m = e.data;
    if (!m || m.source !== "weave-panel") return;
    switch (m.kind) {
      case "size":
        if (m.part === "top") size.top = [Math.min(620, m.width), m.height];
        else if (m.part === "left" || m.part === "float") size[m.part] = Math.ceil(m.height);
        layout(); refresh();
        break;
      case "shown": ui.ask = !!m.shown; refresh(); break;
      case "idle": ui.idle = !!m.idle; refresh(); break;
      case "status":
        ui.connected = m.connected;
        setOrb(m.state || (m.connected ? "idle" : "off"));
        $(".st").textContent = m.text || "";
        break;
      case "roles":
        ui.roles = m.roles;
        if (menu.classList.contains("open")) renderMenu();
        break;
      case "attention":
        if (m.part === "left" && !ui.left) buttons.left.classList.add("new");
        if (m.part === "float" && !ui.float) buttons.float.classList.add("new");
        refresh();
        break;
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
  refresh();
  try {
    chrome.storage.local.get("wsUrl", (s) => load(s?.wsUrl));
  } catch {
    load();
  }
})();

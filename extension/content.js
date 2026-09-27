// Weave overlay: floats over the call page and keeps the faces clear.
//   top       "Ask her": a frosted pill, top center, that comes down when the talk pauses
//   left      the dictionary feed (words, then "Curious?" questions), middle left
//   float     pictures (with what they are) and meanings, top right, only as tall as there are cards
//   captions  the translation bubble, bottom center, directly above...
//   the line  ...a line that moves with what Weave is doing (quiet, listening, translating, speaking). Click it to hide or show everything. Beside it:
//             the words and pictures buttons, the Transcribe switch and the English / Telugu switch.
// Each panel is panel.html (an extension page) in its own frame, so the call site's security rules can't block its
// connection to the Weave engine on this Mac (ws://localhost:8765 by default; set "wsUrl" in chrome.storage.local
// to change it). background.js runs this when you turn Weave on; running it again shows or hides the overlay.
// Every frame is placed once per size change and shown, hidden and moved only with transform and opacity.
(() => {
  if (window.__weaveOverlay) {
    window.__weaveOverlay.toggle();
    return;
  }

  const Z = 2147483000, LINE_W = 240;
  const url = (p) => chrome.runtime.getURL(p);
  const icon = {
    words: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5"/><path d="M9 8h7M9 12h5"/></svg>`,
    pics: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3.5"/><circle cx="9" cy="10" r="1.8"/><path d="m21 16-4.6-4.6a1.5 1.5 0 0 0-2.1 0L6 19.5"/></svg>`,
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
        --grad: linear-gradient(135deg, #25d366 0%, #1db954 50%, #168d40 100%);
        --spring: cubic-bezier(.34,1.56,.64,1); --ease-out: cubic-bezier(.16,1,.3,1); --ease-sheet: cubic-bezier(.32,.72,0,1); --ease-in: cubic-bezier(.7,0,.84,0);
        --font: "Weave Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; }
      * { box-sizing: border-box; }
      button { all: unset; cursor: pointer; }

      /* ---- frames: placed once, then only transform + opacity move ---- */
      iframe { position: fixed; left: 0; top: 0; z-index: ${Z}; border: 0; background: transparent; color-scheme: normal;
               transform: var(--at); will-change: transform, opacity; }
      .glass { border-radius: 22px; background: linear-gradient(180deg, rgba(36,36,41,.7), rgba(16,16,18,.62)); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);
               box-shadow: var(--inner), var(--shadow); }
      .top { border-radius: 26px; box-shadow: var(--inner), 0 18px 50px -12px rgba(22,141,64,.45), var(--shadow);
             transition: opacity 420ms var(--ease-out), transform 560ms var(--spring); }
      .top.off { opacity: 0; transform: var(--at) translate3d(0, -18px, 0) scale(.96); pointer-events: none;
             transition: opacity 320ms var(--ease-in), transform 360ms var(--ease-in); }
      .left { transition: opacity 260ms var(--ease-out), transform 460ms var(--ease-sheet); }
      .left.off { opacity: 0; transform: var(--at) translate3d(-16px, 0, 0) scale(.98); pointer-events: none;
             transition: opacity 180ms var(--ease-in), transform 220ms var(--ease-in); }
      .float { transition: opacity 260ms var(--ease-out); pointer-events: none; }   /* pictures only show; clicks go to the call */
      .float.off { opacity: 0; pointer-events: none; }
      .captions { border-radius: 24px; transition: opacity 420ms var(--ease-out), transform 520ms var(--ease-sheet); }
      .captions.off { opacity: 0; transform: var(--at) translate3d(0, 10px, 0) scale(.98); pointer-events: none;
             transition: opacity 700ms var(--ease-in), transform 700ms var(--ease-in); }
      .hidden iframe { opacity: 0 !important; pointer-events: none !important; }

      /* ---- the line and its controls, bottom center ---- */
      /* one row, centered as a whole: the two groups are different widths, so pinning each to the middle leaned it right */
      .core { position: fixed; z-index: ${Z + 2}; left: 50%; transform: translateX(-50%); height: 56px; display: flex; align-items: center;
              gap: 12px; font: 700 13px/1 var(--font); color: var(--text); -webkit-font-smoothing: antialiased; }
      /* no bar in the middle any more (the pulsing line under the captions shows what Roots is doing); the controls meet at the center */
      .line-btn { display: none; position: absolute; left: -${LINE_W / 2}px; top: 0; width: ${LINE_W}px; height: 56px; border-radius: 28px; }
      .line-btn canvas { width: 100%; height: 100%; display: block; }
      .line-btn::after { content: ""; position: absolute; top: 6px; right: 14px; width: 8px; height: 8px; border-radius: 50%; background: var(--grad);
              box-shadow: 0 0 0 2px #121212; transform: scale(0); transition: transform 320ms var(--spring); }
      .core.new .line-btn::after { transform: scale(1); }
      .side { height: 40px; display: flex; align-items: center; gap: 8px; opacity: .55;
              transition: opacity 220ms var(--ease-out); }
      .core:hover .side, .core:focus-within .side { opacity: 1; }
      .ctl { position: relative; width: 40px; height: 40px; border-radius: 20px; display: grid; place-items: center; color: var(--text-2);
              background: var(--glass); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); box-shadow: var(--inner), var(--shadow);
              transition: color 140ms var(--ease-out), background 140ms var(--ease-out), transform 140ms var(--ease-out); }
      .ctl svg { width: 18px; height: 18px; }
      .ctl:hover { color: #fff; }
      .ctl:active, .sw:active, .seg button:active { transform: scale(.94); }
      .ctl.on { color: #fff; background: rgba(29,185,84,.26); box-shadow: var(--inner), inset 0 0 0 1px rgba(29,185,84,.45), var(--shadow); }
      .ctl .badge { position: absolute; top: 6px; right: 6px; width: 7px; height: 7px; border-radius: 50%; background: var(--grad);
              box-shadow: 0 0 0 2px rgba(18,18,20,.95); transform: scale(0); transition: transform 320ms var(--spring); }
      .ctl.new .badge { transform: scale(1); }
      /* Transcribe: drawn from what the engine says ("transcribing"), never from the click */
      .sw { height: 40px; padding: 0 14px 0 8px; border-radius: 20px; display: flex; align-items: center; gap: 9px; white-space: nowrap; color: var(--text-2);
              background: var(--glass); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); box-shadow: var(--inner), var(--shadow);
              transition: color 160ms var(--ease-out), transform 140ms var(--ease-out); }
      .sw .track { position: relative; width: 34px; height: 20px; border-radius: 10px; background: rgba(255,255,255,.12); transition: background 220ms var(--ease-out); }
      .sw .track::after { content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: #fff;
              box-shadow: 0 1px 3px rgba(0,0,0,.4); transform: translate3d(0, 0, 0); transition: transform 320ms var(--spring); }
      .sw.on { color: #fff; }
      .sw.on .track { background: var(--grad); }
      .sw.on .track::after { transform: translate3d(14px, 0, 0); }
      .seg { height: 40px; display: flex; align-items: center; padding: 4px; gap: 2px; border-radius: 20px;
              background: var(--glass); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur); box-shadow: var(--inner), var(--shadow); }
      .seg button { height: 32px; padding: 0 12px; border-radius: 16px; display: flex; align-items: center; color: var(--text-2);
              transition: color 140ms, background 180ms var(--ease-out), transform 140ms var(--ease-out); }
      .seg button:hover { color: #fff; }
      .seg button.on { background: var(--grad); color: #fff; }
      .seg.guess { box-shadow: var(--inner), var(--shadow), 0 0 0 1.5px rgba(179,166,212,.55); animation: ask 2.4s ease-in-out infinite; }
      @keyframes ask { 50% { box-shadow: var(--inner), var(--shadow), 0 0 0 1.5px rgba(179,166,212,.2), 0 0 16px rgba(179,166,212,.35); } }
      .sw.unknown { opacity: .45; }
      .sw.unknown .track::after { transform: translate3d(7px, 0, 0); }
    </style>
    <div class="wrap">
      <iframe class="left" title="Roots: words and questions" allowtransparency="true"></iframe>
      <iframe class="float off" title="Roots: pictures and meanings" allowtransparency="true"></iframe>
      <iframe class="captions glass off" title="Roots: captions" allowtransparency="true"></iframe>
      <iframe class="top glass off" title="Roots: ask her" allowtransparency="true"></iframe>
      <div class="core">
        <div class="side l">
          <button class="ctl on" data-panel="left" aria-label="Words and questions" title="Words and questions">${icon.words}<i class="badge"></i></button>
          <button class="ctl on" data-panel="float" aria-label="Pictures and meanings" title="Pictures and meanings">${icon.pics}<i class="badge"></i></button>
        </div>
        <button class="line-btn" title="Show or hide Roots (Alt+Shift+W)" aria-label="Show or hide Roots"><canvas></canvas></button>
        <div class="side r">
          <button class="sw on" data-act="transcribe" role="switch" aria-checked="true"><span class="track"></span>Transcribe</button>
          <span class="seg" role="radiogroup" aria-label="I speak"><button data-lang="en">English</button><button data-lang="te">Telugu</button></span>
        </div>
      </div>
    </div>`;
  document.documentElement.append(host);

  // The geometric face from the extension, for the controls (the panels load it themselves). Falls back to the system font.
  try {
    const face = new FontFace("Weave Manrope", `url(${url("fonts/manrope.woff2")})`, { weight: "200 800" });
    face.load().then((f) => document.fonts.add(f)).catch(() => {});
  } catch {}

  const $ = (s) => root.querySelector(s);
  const wrap = $(".wrap"), core = $(".core"), canvas = $("canvas");
  const frames = { top: $(".top"), left: $(".left"), float: $(".float"), captions: $(".captions") };
  const buttons = { left: $('[data-panel="left"]'), float: $('[data-panel="float"]') };
  const size = { top: [0, 0], left: 0, float: 0 };
  const ui = { shown: true, left: true, float: true, ask: false, idle: true, roles: null, lang: null, transcribing: null, state: "off", connected: false };

  // ---- layout: placed with transforms; sizes change only when content does ----
  const M = 16, ORB_BOTTOM = 66, ORB = 56, CAP_H = 148;   // ORB_BOTTOM clears the call's own buttons
  function place(frame, x, y, w, h) {
    frame.style.width = `${Math.round(w)}px`;
    frame.style.height = `${Math.max(1, Math.round(h))}px`;
    frame.style.setProperty("--at", `translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`);   // the class rules add to this
  }
  function layout() {
    const w = innerWidth, h = innerHeight;
    // bottom center: the line, and the translation bubble right above it
    core.style.bottom = `${ORB_BOTTOM}px`;
    const capY = h - ORB_BOTTOM - ORB - 12 - CAP_H;
    // top left: the dictionary, as tall as its words
    const leftW = Math.min(300, w - 2 * M), leftH = Math.min(size.left || 1, h - 2 * M);
    place(frames.left, M, M, leftW, leftH);
    const clear = M + leftH > capY - 8 ? M + leftW + 12 : M;   // keep the bubble clear of a long word list
    const capW = Math.max(Math.min(360, w - 2 * M), Math.min(720, w - 2 * clear));
    place(frames.captions, (w - capW) / 2, capY, capW, CAP_H);
    // top center: the "Ask her" pill
    const [tw, th] = size.top;
    place(frames.top, (w - (tw || 620)) / 2, M, tw || 620, th || 1);
    // top right: pictures and meanings, as tall as there are cards, above your camera tile in the bottom corner
    const fw = Math.min(320, w - 2 * M), fh = Math.min(size.float || 1, h - 2 * M);   // never squeezed in a small call window
    place(frames.float, w - M - fw, M, fw, fh);
  }
  function load(wsUrl) {
    const q = wsUrl ? `&ws=${encodeURIComponent(wsUrl)}` : "";
    for (const [part, frame] of Object.entries(frames)) frame.src = url(`panel.html?part=${part}${q}`);
  }
  function refresh() {
    frames.top.classList.toggle("off", !ui.ask);
    frames.left.classList.toggle("off", !ui.left || !size.left);
    frames.float.classList.toggle("off", !ui.float || !size.float);
    // Transcribe shows only what the engine says ("transcribing"); until it has said anything, it's dimmed.
    const sw = $(".sw");
    sw.classList.toggle("on", ui.transcribing === true);
    sw.classList.toggle("unknown", ui.transcribing === null);
    sw.setAttribute("aria-checked", String(ui.transcribing === true));
    sw.title = ui.transcribing === null ? "Waiting for the translator" : ui.transcribing ? "Transcribing the call: click to pause" : "Paused: the call isn't being transcribed. Click to resume";
    // English / Telugu: the language you speak. It's remembered and sent to the engine, which uses it in two-way calls
    // (where it also says who it thinks speaks what, "roles"; while it's guessing, the switch asks you to pick).
    const seg = $(".seg");
    seg.classList.toggle("guess", !!ui.roles && !ui.roles.sure);
    seg.title = !ui.roles ? "The language you speak (used in two-way calls)" : ui.roles.sure ? "The language you speak on this call" : "Roots is guessing which language you speak: pick yours";
    const mine = ui.roles?.you || ui.lang;
    root.querySelectorAll("[data-lang]").forEach((b) => { const on = b.dataset.lang === mine; b.classList.toggle("on", on); b.setAttribute("aria-checked", String(on)); });
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
  $(".line-btn").addEventListener("click", (e) => { e.stopPropagation(); toggle(); });
  buttons.left.addEventListener("click", (e) => { e.stopPropagation(); setPanel("left", !ui.left); });
  buttons.float.addEventListener("click", (e) => { e.stopPropagation(); setPanel("float", !ui.float); });
  const toCaptions = (msg) => frames.captions.contentWindow?.postMessage({ source: "weave-dock", ...msg }, "*");
  $(".sw").addEventListener("click", (e) => { e.stopPropagation(); toCaptions({ kind: "transcribe", on: !ui.transcribing }); });
  root.querySelectorAll("[data-lang]").forEach((b) => b.addEventListener("click", (e) => {
    e.stopPropagation();
    ui.lang = b.dataset.lang;
    if (ui.roles) ui.roles = { ...ui.roles, you: b.dataset.lang, sure: true };   // the engine confirms with "roles"
    toCaptions({ kind: "i_speak", lang: b.dataset.lang });
    refresh();
  }));

  // ---- the line: vibrates with the call's sound ----
  // Frequency bands arrive from offscreen.js (via background.js) about 30 times a second. Without them (no capture,
  // or the preview page), the line follows Weave's state instead. Drawn on a canvas: no layout, ever.
  const audio = { bands: null, at: 0 };
  try { chrome.runtime.onMessage.addListener((m) => { if (m?.weave === "bands") { audio.bands = m.bands; audio.at = performance.now(); } }); } catch {}
  function setOrb(state) { ui.state = state; }
  const N = 48, level = new Float32Array(N);
  let phase = 0, raf = 0;
  const dpr = Math.min(2, devicePixelRatio || 1);
  canvas.width = LINE_W * dpr; canvas.height = 56 * dpr;
  const g = canvas.getContext("2d");
  function target(i, t) {
    return 0;   // no wave: the handle stays a calm, flat line (the caption bubble's pulsing line shows activity instead)
    const live = audio.bands && t - audio.at < 400;
    if (live) {   // low frequencies in the middle of the line, higher ones toward the ends
      const k = Math.abs(i - (N - 1) / 2) / ((N - 1) / 2);
      return audio.bands[Math.min(audio.bands.length - 1, Math.round(k * (audio.bands.length - 1)))] || 0;
    }
    const s = ui.state, wob = 0.5 + 0.5 * Math.sin(t / 170 + i * 0.9) * Math.sin(t / 410 + i * 0.37);
    return s === "listening" ? 0.25 + 0.5 * wob : s === "speaking" ? 0.35 + 0.55 * wob : s === "thinking" ? 0.12 + 0.12 * wob : s === "idle" ? 0.05 : 0.015;
  }
  function draw(t) {
    raf = requestAnimationFrame(draw);
    if (document.hidden || !ui.shown && ui.state === "off") return;
    let energy = 0;
    for (let i = 0; i < N; i++) { const v = target(i, t); level[i] += (v - level[i]) * (v > level[i] ? 0.45 : 0.18); energy += level[i]; }
    energy /= N;
    phase += 0.12 + energy * 0.5;
    const W = canvas.width, H = canvas.height, mid = H / 2;
    g.clearRect(0, 0, W, H);
    const grad = g.createLinearGradient(0, 0, W, 0);
    if (ui.state === "off") { grad.addColorStop(0, "rgba(160,160,170,0)"); grad.addColorStop(.5, "rgba(160,160,170,.6)"); grad.addColorStop(1, "rgba(160,160,170,0)"); }
    else { grad.addColorStop(0, "rgba(37,211,102,0)"); grad.addColorStop(.18, "#25d366"); grad.addColorStop(.5, "#1db954"); grad.addColorStop(.82, "#b3a6d4"); grad.addColorStop(1, "rgba(179,166,212,0)"); }
    // two strands a little out of step: it reads as a string vibrating, not a chart
    for (const [off, width, alpha, blur] of [[Math.PI * 0.6, 1.2 * dpr, 0.45, 0], [0, 2.4 * dpr, 1, 14 * dpr]]) {
      g.beginPath();
      for (let x = 0; x <= W; x += 2 * dpr) {
        const u = x / W, f = u * (N - 1), i0 = Math.floor(f), a = level[i0] + (level[Math.min(N - 1, i0 + 1)] - level[i0]) * (f - i0);
        const env = Math.sin(Math.PI * u);   // pinned at both ends
        const y = mid + Math.sin(u * 22 + phase + off) * a * env * (H * 0.42) + Math.sin(u * 9 - phase * 0.7) * a * env * (H * 0.12);
        x === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
      }
      g.strokeStyle = grad; g.lineWidth = width; g.globalAlpha = alpha; g.lineCap = "round";
      g.shadowColor = "rgba(29,185,84,.9)"; g.shadowBlur = blur * (0.4 + energy);
      g.stroke();
    }
    g.globalAlpha = 1;
  }
  // (the bar is hidden, so its drawing loop isn't started)

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
        if (!m.connected && ui.connected) { ui.transcribing = null; ui.roles = null; refresh(); }   // the engine went away: unknown again
        ui.connected = m.connected;
        setOrb(m.state || (m.connected ? "idle" : "off"));
        break;
      case "roles": ui.roles = m.roles; refresh(); break;
      case "lang": ui.lang = m.lang; refresh(); break;   // the language you picked before (kept by the captions panel)
      case "transcribing": ui.transcribing = !!m.on; refresh(); break;
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

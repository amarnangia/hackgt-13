// One Weave overlay panel (?part=top | left | float | captions). Each reads the engine's WebSocket (subtitles.py,
// ws://localhost:8765 unless ?ws= says otherwise) and draws its share of the messages (see idea.md, "One standard"):
//   top       prompt ("ask her"), shown when the talk pauses
//   left      topic (words for what the call is about), details (words she said)
//   float     picture, details (cards for sayings, slang, customs), as bubbles above the captions
//   captions  speaking, partial, draft, original, english, details (intent), voice, warning, roles
// Everything comes from the call: until the engine sends words (topic, details), the word panel is empty.
// Clicks go back to the engine: forget (a kept word you don't know),
// i_speak (two-way calls, from the dock's menu). Everything is drawn in place: rows keep their elements and only
// transform and opacity animate, so nothing jumps or flickers over the call.
const params = new URLSearchParams(location.search);
const PART = params.get("part") || "captions";
const WS_URL = params.get("ws") || "ws://localhost:8765";
const HTTP_URL = WS_URL.replace(/^ws/, "http").replace(/\/+$/, "");
document.body.dataset.part = PART;

const root = document.getElementById("root");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const asset = (path) => (/^(https?:|data:)/.test(path) ? path : `${HTTP_URL}/${String(path).replace(/^\/+/, "")}`);
// Nothing in Telugu script is shown: romanized words and English only. noTe() is the last line of defence.
const TE = /[\u0C00-\u0C7F]/;
const noTe = (s) => String(s ?? "").replace(/[\u0C00-\u0C7F]+/g, "").replace(/[“"‘']\s*[”"’']/g, "").replace(/\(\s*\)/g, "")
  .replace(/\s+([,.!?;:])/g, "$1").replace(/\s{2,}/g, " ").replace(/^[\s,.;:·-]+/, "").trim();
const tellParent = (msg) => parent.postMessage({ source: "weave-panel", part: PART, ...msg }, "*");

// ---------- connection ----------
let ws = null;
const conn = { on: false, name: "", me: "" };  // name: who you're calling; me: you (the engine's "call" message)
function connect() {
  try { ws = new WebSocket(WS_URL); } catch { setTimeout(connect, 2500); return; }
  ws.onopen = () => {
    conn.on = true; status();
    const lang = savedLanguage();  // two-way calls: tell the engine who speaks what, so it never has to guess
    if (lang && PART === "captions") send({ type: "i_speak", lang });
  };
  ws.onclose = () => { conn.on = false; status(); setTimeout(connect, 2500); };
  ws.onerror = () => {};
  ws.onmessage = (e) => { let m; try { m = JSON.parse(e.data); } catch { return; } handle(m); };
}
function send(msg) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(msg)); }

// "I speak English / Telugu" (two-way calls): remembered, and sent again whenever the engine (re)connects
function savedLanguage() { try { return localStorage.getItem("weave-i-speak"); } catch { return null; } }
function chooseLanguage(lang) {
  try { localStorage.setItem("weave-i-speak", lang); } catch {}
  send({ type: "i_speak", lang });
}

// Your side (subtitles.py --two-way's second page, two ports up): what you said and the Telugu she heard, in the captions
const YOU_URL = (() => { try { const u = new URL(WS_URL); u.port = String(Number(u.port || 80) + 2); return u.href.replace(/\/$/, ""); } catch { return null; } })();
function connectYou() {
  if (!YOU_URL) return;
  let you;
  try { you = new WebSocket(YOU_URL); } catch { setTimeout(connectYou, 5000); return; }
  you.onclose = () => setTimeout(connectYou, 5000);
  you.onerror = () => {};
  you.onmessage = (e) => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    if (m.type !== "original" && m.type !== "english") return;
    handleCaptions({ ...m, id: `you:${m.id}`, you: true });
  };
}
// The top pill also needs to know when *you* talk (--two-way's second page), not just her
function hearYou() {
  if (!YOU_URL) return;
  let you;
  try { you = new WebSocket(YOU_URL); } catch { setTimeout(hearYou, 5000); return; }
  you.onclose = () => setTimeout(hearYou, 5000);
  you.onerror = () => {};
  you.onmessage = (e) => {
    let m; try { m = JSON.parse(e.data); } catch { return; }
    if (["speaking", "original"].includes(m.type) || (m.type === "partial" && m.text)) { heardTalk(); renderTop(); }
  };
}
function status() {
  if (PART === "captions") renderCaptions();
}

// ---------- captions ----------
const cap = { lines: [], byId: {}, partial: "", draft: "", speaking: false, warning: "", warnTimer: 0, roles: null,
  voiceUntil: 0, lastActivity: 0, idleTimer: 0 };
const IDLE_AFTER_MS = 9000;   // captions fade away this long after the last words
// The dock's orb: off (no engine), idle, listening (someone is talking), thinking (translating), speaking (Weave's voice is playing)
function orbState() {
  if (!conn.on) return "off";
  if (Date.now() < cap.voiceUntil) return "speaking";
  if (cap.lines.some((l) => l.pending && !l.you)) return "thinking";
  if (cap.speaking || cap.partial) return "listening";
  return "idle";
}
function captionLine(id) {
  let l = cap.byId[id];
  if (!l) {
    l = cap.byId[id] = { id, orig: "", en: "", kept: [], pending: false, english: false, tag: "" };
    cap.lines.push(l);
    while (cap.lines.length > 2) delete cap.byId[cap.lines.shift().id];
  }
  return l;
}
// The dock sends back the language you picked (two-way calls)
addEventListener("message", (e) => {
  if (PART === "captions" && e.data?.source === "weave-dock" && e.data.kind === "transcribe") send({ type: "transcribe", on: !!e.data.on });
  if (PART === "captions" && e.data?.source === "weave-dock" && e.data.kind === "i_speak") { chooseLanguage(e.data.lang); cap.roles && (cap.roles.you = e.data.lang); renderCaptions(); }
});

function withKept(text, kept) {
  // Words kept in her language are underlined with their English; clicking one tells the engine you don't know it.
  let html = "", rest = text;
  for (const k of kept || []) {
    const at = rest.indexOf(k.telugu);
    if (at < 0) continue;
    const word = TE.test(k.telugu) ? noTe(k.roman) : k.telugu;
    html += esc(noTe(rest.slice(0, at))) + " " + (word
      ? `<span class="kept" data-id="${esc(k.id)}" data-en="${esc(k.english)}" title="Click if you don't know this word">${esc(word)}<small>(${esc(k.english)})</small></span>`
      : esc(k.english)) + " ";
    rest = rest.slice(at + k.telugu.length);
  }
  return (html + esc(noTe(rest))).replace(/\s+([,.!?;:])/g, "$1").trim();
}
// Captions are drawn in place: each line keeps its element and only its text changes, so nothing flashes. What she's
// saying right now (the partial) becomes that line's element when the sentence is done; older lines glide up and fade.
const view = { els: new Map(), live: null, built: false };
const DOTS = `<span class="dots"><i></i><i></i><i></i></span>`;
function setHTML(node, html) { if (node._h !== html) { node.innerHTML = html; node._h = html; } }
function lineEl() {
  const el = document.createElement("div");
  el.className = "cl entering";
  el.innerHTML = `<div class="en"></div>`;
  el.addEventListener("animationend", (e) => { if (e.animationName === "line-in") el.classList.remove("entering"); });
  return el;
}
function fillLine(el, l) {   // l: a caption line, or null for what's being said right now
  el.classList.toggle("you", !!l?.you);
  let en, kind;   // kind: final | draft | pending
  if (!l) {
    const heard = noTe(cap.partial);   // English said aloud shows as it's heard; Telugu waits for its English
    [en, kind] = cap.draft ? [esc(noTe(cap.draft)), "draft"] : heard ? [esc(heard), "draft"] : [cap.partial ? DOTS : "", "pending"];
  } else if (l.to ? l.to !== "en" : l.english || l.you) {
    [en, kind] = [`${l.tag && !l.you ? `<span class="tag">${esc(l.tag)}</span>` : ""}${esc(noTe(l.orig))}`, "final"];   // said in English
  } else {
    [en, kind] = l.pending ? (l.draft ? [esc(noTe(l.draft)), "draft"] : [DOTS, "pending"])
      : [`${l.tag ? `<span class="tag">${esc(l.tag)}</span>` : ""}${withKept(l.en, l.kept)}`, "final"];
  }
  const enEl = el.querySelector(".en");
  // The English writes itself in once, when it arrives from nothing; a draft just firms up in place.
  if (kind === "final" && enEl.dataset.kind !== "final" && enEl.dataset.kind !== "draft") enEl.classList.add("reveal");
  enEl.dataset.kind = kind;
  enEl.classList.toggle("draft", kind === "draft");
  setHTML(enEl, en);
}
function renderCaptions() {
  const who = conn.name || "her";
  const state = orbState();
  const statusText = !conn.on ? "Waiting for the Weave engine" : { speaking: "Speaking for you", thinking: "Translating",
    listening: `${who[0].toUpperCase() + who.slice(1)} is speaking`, idle: conn.me && conn.name ? `${conn.me} ↔ ${conn.name}` : `Listening to ${who}` }[state];
  tellParent({ kind: "status", connected: conn.on, state, text: statusText });
  // Two-way calls: the "I speak" switch lives in the dock's menu
  tellParent({ kind: "roles", roles: cap.roles ? { you: cap.roles.you, sure: !!(savedLanguage() || cap.roles.fixed) } : null });
  document.body.dataset.state = state;

  if (!view.built) {
    root.innerHTML = `<div class="glow"></div><div class="warning" hidden></div><div class="stage"></div>`;
    view.built = true;
  }
  const warn = root.querySelector(".warning"), stage = root.querySelector(".stage");
  warn.hidden = !cap.warning; setHTML(warn, esc(cap.warning));

  // Captions sit on the bottom edge, so lines are tracked by their bottoms: a line that grows or shrinks stays put and
  // only the lines above it move.
  const before = new Map([...stage.children].filter((el) => !el.classList.contains("leaving"))
    .map((el) => { const b = el.getBoundingClientRect(); return [el, { bottom: b.bottom, height: b.height }]; }));
  const liveNow = !!(cap.partial || cap.draft);
  const items = cap.lines.map((l) => ({ key: l.id, l }));
  if (liveNow) items.push({ key: "live", l: null });
  const visible = items.slice(-2);
  const keep = new Set();
  const order = visible.map(({ key, l }) => {
    let el = key === "live" ? view.live : view.els.get(key);
    if (!el && l && !l.you && view.live) { el = view.live; view.live = null; }   // her finished sentence takes over the live line
    if (!el) el = lineEl();
    if (key === "live") view.live = el; else view.els.set(key, el);
    fillLine(el, l);
    keep.add(el);
    return el;
  });
  // Lines that scrolled off leave upward from where they are
  for (const [key, el] of [...view.els, ["live", view.live]]) {
    if (!el || keep.has(el)) continue;
    if (key === "live") view.live = null; else view.els.delete(key);
    if (el.isConnected) {
      Object.assign(el.style, { position: "absolute", left: "0", right: "0", top: `${el.offsetTop}px` });
      el.classList.add("leaving");
      setTimeout(() => el.remove(), 450);
    }
  }
  order.forEach((el, i) => {
    el.classList.toggle("now", i === order.length - 1);
    el.classList.toggle("past", i < order.length - 1);
    const at = [...stage.children].filter((c) => !c.classList.contains("leaving"))[i];
    if (at !== el) stage.insertBefore(el, at || null);
  });
  const same = order.length > 0 && order.length === before.size && order.every((el) => before.has(el));
  if (same) {
    // Same lines, new words: the current line grows or shrinks smoothly and pushes the line above along with it.
    const el = order[order.length - 1], was = before.get(el).height, now = el.getBoundingClientRect().height;
    if (Math.abs(now - was) > 2) {
      el.getAnimations().filter((a) => a.id === "grow").forEach((a) => a.cancel());
      el.style.overflow = "clip";
      const a = el.animate([{ height: `${was}px` }, { height: `${now}px` }], { duration: 340, easing: "cubic-bezier(.32,.72,0,1)", id: "grow" });
      a.id = "grow";
      a.onfinish = a.oncancel = () => { el.style.overflow = ""; };
    }
  } else {
    // A line came or went: the ones that stayed glide to their new place.
    for (const [el, b] of before) {
      if (!el.isConnected || el.classList.contains("leaving")) continue;
      const d = b.bottom - el.getBoundingClientRect().bottom;
      if (Math.abs(d) > 1) el.animate([{ translate: `0 ${d}px` }, { translate: "0 0" }], { duration: 480, easing: "cubic-bezier(.32,.72,0,1)" });
    }
  }

  // Subtitles only while there's something to read: they fade out after a quiet moment and come back with the next words.
  const quietFor = Date.now() - cap.lastActivity;
  const idle = !cap.warning && (!order.length || (state === "idle" && quietFor > IDLE_AFTER_MS));
  document.body.classList.toggle("idle", idle);
  tellParent({ kind: "idle", idle });
  clearTimeout(cap.idleTimer);
  if (!idle) {
    const next = state === "speaking" ? cap.voiceUntil - Date.now() : IDLE_AFTER_MS - quietFor;
    cap.idleTimer = setTimeout(renderCaptions, Math.max(300, next + 50));
  }
}
root.addEventListener("click", (e) => {
  const k = e.target.closest(".kept");
  if (!k || PART !== "captions") return;
  send({ type: "forget", id: k.dataset.id });
  k.replaceWith(document.createTextNode(k.dataset.en));
});


// ---------- keyed lists: rows keep their elements, new rows spring in, rows that move glide (transform and opacity only) ----------
const GLIDE = { duration: 420, easing: "cubic-bezier(.32,.72,0,1)" };
function syncList(box, items, keyOf, make, update) {
  const els = box._els || (box._els = new Map());
  const live = () => [...box.children].filter((c) => !c.classList.contains("out"));
  const before = new Map(live().map((el) => [el, el.getBoundingClientRect().top]));
  const want = new Set(items.map(keyOf));
  const going = [];
  for (const [k, el] of els) if (!want.has(k)) { els.delete(k); going.push(el); }
  leave(going);
  items.forEach((it, i) => {
    const k = keyOf(it);
    let el = els.get(k);
    if (!el) {
      el = make(it);
      el.classList.add("in");
      el.style.setProperty("--d", `${160 + Math.min(i, 6) * 70}ms`);   // after the old ones have gone, one after another
      el.style.setProperty("--i", String(i));                    // and drift out of step with each other
      el.addEventListener("animationend", () => el.classList.remove("in"), { once: true });
      els.set(k, el);
    }
    update(el, it);
    const at = live()[i];
    if (at !== el) box.insertBefore(el, at || null);
  });
  for (const [el, top] of before) {
    if (!el.isConnected || el.classList.contains("out")) continue;
    const d = top - el.getBoundingClientRect().top;
    if (Math.abs(d) > 1) el.animate([{ transform: `translate3d(0, ${d}px, 0)` }, { transform: "translate3d(0, 0, 0)" }], GLIDE);
  }
}
function leave(list) {   // lift out of the flow where they are (all measured first, so none jump), then fade away
  const at = list.filter((el) => el.isConnected).map((el) => [el, el.offsetLeft, el.offsetTop, el.offsetWidth]);
  for (const [el, x, y, w] of at) {
    Object.assign(el.style, { position: "absolute", left: `${x}px`, top: `${y}px`, width: `${w}px` });
    el.classList.add("out");
    setTimeout(() => el.remove(), 320);
  }
}
function html(tag, cls, inner = "") { const el = document.createElement(tag); el.className = cls; el.innerHTML = inner; return el; }
const report = () => tellParent({ kind: "size", width: Math.ceil(root.scrollWidth), height: Math.ceil(root.scrollHeight) });

// ---------- top: "Ask her", a frosted pill that comes down when the talk pauses ----------
// It waits for a real pause (2 s) before coming in and then stays up, however long the quiet lasts, until someone (either
// of you) has been talking for 5 s: then it's done. If nobody talks for 30 s, the engine sends a fresh one instead.
const SPARK = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5c.4 3.9 1.9 6.6 4.2 8 1.3.8 2.9 1.3 5.3 1.5-2.4.2-4 .7-5.3 1.5-2.3 1.4-3.8 4.1-4.2 8-.4-3.9-1.9-6.6-4.2-8C6.5 12.7 4.9 12.2 2.5 12c2.4-.2 4-.7 5.3-1.5 2.3-1.4 3.8-4.1 4.2-8z"/></svg>`;
const PAUSE_MS = 2000, TALK_MS = 5000;
const askState = { ask: null, drawn: null, expire: 0, lastTalk: 0, talkStart: 0, shown: false, shownAt: 0, tick: 0 };
function heardTalk() {
  const now = Date.now();
  if (now - askState.lastTalk > 900) askState.talkStart = now;
  askState.lastTalk = now;
}
function renderTop() {
  const now = Date.now();
  if (askState.ask && askState.ask !== askState.drawn) {
    const a = askState.ask;
    const say = noTe(a.roman) || noTe(a.english), means = noTe(a.roman) ? noTe(a.english) : "";
    root.innerHTML = `<div class="pill">
        <span class="spark">${SPARK}</span>
        <div class="pill-text"><div class="q-roman">${esc(say)}</div>${means ? `<div class="q-sub">${esc(means)}</div>` : ""}</div>
      </div>`;
    askState.drawn = a;
    report();
  }
  const talking = now - askState.lastTalk < 900;
  if (askState.ask && askState.shown && talking && now - askState.talkStart > TALK_MS) askState.ask = null;  // they moved on
  let show = askState.shown;
  if (!askState.ask) show = false;
  else if (!askState.shown) show = !talking && (now - askState.lastTalk > PAUSE_MS || !askState.lastTalk);
  if (show !== askState.shown) {
    askState.shown = show;
    if (show) askState.shownAt = now;
    tellParent({ kind: "shown", shown: show });
  }
  clearInterval(askState.tick);
  if (askState.ask) askState.tick = setInterval(renderTop, 250);
}
function handleTop(m) {
  if (["speaking", "original"].includes(m.type) || (m.type === "partial" && m.text)) heardTalk();
  if (m.type === "prompt") askState.ask = m;  // stays until someone has talked for a while, or a newer one comes
  renderTop();
}

// ---------- left: the dictionary feed (words for the topic, the ones she said first) ----------
const left = { topic: "", words: [], engineTopic: false, said: [], built: false };
const MAX_WORDS = 5;

function rememberSaid(card) {  // words she used this call, pinned above the topic words (not whole proverbs)
  const key = (card.title || "").toLowerCase();
  if (!card.id || !card.telugu || card.category === "idiom" || left.said.some((w) => w.id === card.id || w.roman.toLowerCase() === key)) return;
  left.said.unshift({ id: card.id, telugu: card.telugu, roman: card.title, english: card.english || card.note || "" });
  left.said = left.said.slice(0, 4);
}
const norm = (r) => String(r).toLowerCase().replace(/\?$/, "");
function renderLeft() {
  if (!left.built) {
    root.innerHTML = `<section class="dict"><div class="rows"></div></section>`;
    left.built = true;
  }
  const said = new Set(left.said.flatMap((w) => [w.id, norm(w.roman)]));
  const words = [...left.said.map((w) => ({ ...w, said: true })),
    ...left.words.filter((w) => !said.has(w.id) && !said.has(norm(w.roman)))]
    .filter((w) => noTe(w.roman) && !TE.test(w.roman)).slice(0, MAX_WORDS);
  syncList(root.querySelector(".rows"), words, (w) => w.id || norm(w.roman),
    () => html("div", "w", `<b class="w-roman"></b><div class="w-en"></div>`),
    (el, w) => {
      el.classList.toggle("said", !!w.said);
      el.querySelector(".w-roman").textContent = noTe(w.roman);
      el.querySelector(".w-en").textContent = noTe(w.english);
    });
  report();
}
// ---------- float: pictures and meanings as small bubbles that spring up above the captions ----------
// Each holds for a while and fades away; hover one to see it, click to keep it.
const float = { items: [] };
// Pictures pop up, stay about 2.5 s and fade away; they can't be clicked (the call underneath gets every click).
const MAX_ITEMS = 2, HOLD_MS = 3200, FADE_MS = 700;
const MEANING_KINDS = new Set(["idiom", "slang", "phrase", "culture"]);
const LABELS = { idiom: "Saying", slang: "Slang", phrase: "Phrase", culture: "Custom" };
function addFloat(item) {
  const words = item.words || [];
  if (item.kind === "picture") float.items = float.items.filter((x) => !(x.kind === "meaning" && words.includes(x.word)));
  if (item.kind === "meaning" && float.items.some((x) => x.kind === "picture" && (x.words || []).includes(item.word))) return;
  const existing = float.items.find((x) => x.key === item.key);
  if (existing) { existing.at = Date.now(); return; }
  float.items.push({ ...item, at: Date.now() });
  while (float.items.length > MAX_ITEMS) float.items.shift();
  tellParent({ kind: "attention", what: "new" });
}
function renderFloat() {
  const now = Date.now();
  float.items = float.items.filter((x) => now - x.at < HOLD_MS);
  syncList(root.querySelector(".bubs") || (root.innerHTML = `<div class="bubs"></div>`, root.querySelector(".bubs")), float.items, (x) => x.key,
    (x) => {
      const el = html("div", `bub ${x.kind}`, x.kind === "picture"
        ? `<img class="big" src="${esc(asset(x.image))}" alt=""><div class="bub-body"><b>${esc(noTe(x.name))}</b>${noTe(x.description) ? `<p>${esc(noTe(x.description))}</p>` : ""}</div>`
        : `<div class="bub-body"><span class="kind">${esc(x.label)}</span><b>${esc(x.title)}</b>${noTe(x.note) ? `<p>${esc(noTe(x.note))}</p>` : ""}</div>`);
      el.dataset.key = x.key;
      return el;
    },
    (el, x) => { el.classList.toggle("fading", now - x.at > HOLD_MS - FADE_MS); });
  report();
  clearTimeout(float.timer);
  const next = float.items.flatMap((x) => [x.at + HOLD_MS - FADE_MS - now, x.at + HOLD_MS - now]).filter((t) => t > 0);
  if (next.length) float.timer = setTimeout(renderFloat, Math.min(...next) + 30);
}


// ---------- messages ----------
function handle(m) {
  if (m.type === "call") { conn.name = m.caller || conn.name; conn.me = m.you && m.you !== "You" ? m.you : ""; status(); }
  else if (m.caller && m.caller !== conn.name) { conn.name = m.caller; status(); }
  if (PART === "captions") return handleCaptions(m);
  if (PART === "top") return handleTop(m);
  if (PART === "left") return handleLeft(m);
  if (PART === "float") return handleFloat(m);
}
function handleCaptions(m) {
  cap.lastActivity = Date.now();
  switch (m.type) {
    case "voice": cap.voiceUntil = Date.now() + 2600; break;
    case "transcribing": tellParent({ kind: "transcribing", on: !!m.on }); return;   // the engine says; the switch draws this
    case "speaking": cap.speaking = true; break;
    case "partial": cap.partial = m.text || ""; if (!m.text) cap.speaking = false; break;
    case "draft": cap.draft = m.text || ""; break;
    case "roles": cap.roles = { you: m.you, them: m.them, fixed: m.fixed }; break;
    case "original": {
      const l = captionLine(m.id);
      l.orig = m.text; l.english = m.route === "english"; l.to = m.to; l.you = !!m.you;
      l.pending = l.to ? l.to === "en" : !l.english;
      if (!m.you) { cap.partial = ""; cap.speaking = false; }
      l.draft = cap.draft; cap.draft = "";  // keep showing the draft until the final English arrives
      break;
    }
    case "english": {
      const l = cap.byId[m.id]; if (!l) return;
      l.en = m.text; l.kept = m.kept || []; l.pending = false;
      break;
    }
    case "details": {
      const l = cap.byId[m.id]; if (!l) return;
      if (m.intent === "question") l.tag = "Asked you";
      else if (m.intent === "request") l.tag = "Request";
      break;
    }
    case "warning":
      cap.warning = String(m.text || "").split(". ")[0];
      clearTimeout(cap.warnTimer); cap.warnTimer = setTimeout(() => { cap.warning = ""; renderCaptions(); }, 15000);
      break;
    default: return;
  }
  renderCaptions();
}
function handleLeft(m) {
  switch (m.type) {
    case "topic":
      left.engineTopic = true;
      left.topic = m.topic || left.topic;
      left.words = m.words || left.words;
      break;
    case "details":
      for (const c of m.cards || []) if (c.id) rememberSaid(c);  // sayings and idioms stay on the right (float)
      break;
    default: return;
  }
  renderLeft();
}
function handleFloat(m) {
  if (m.type === "picture" && m.image) {
    addFloat({ key: `pic:${m.id}`, kind: "picture", name: m.name, description: m.description, image: m.image, words: m.lexicon_ids || [] });
  } else if (m.type === "details") {
    for (const c of m.cards || []) {
      if (!c.note || !MEANING_KINDS.has(c.category)) continue;
      const title = TE.test(c.title) ? noTe(c.english) : noTe(c.title);   // a saying in Telugu script goes by its English
      if (!title) continue;
      addFloat({ key: `card:${c.id || c.title}`, kind: "meaning", word: c.id, label: LABELS[c.category] || "Meaning", title, note: c.note });
    }
  } else return;
  renderFloat();
}

// ---------- start ----------
if (PART === "captions") { renderCaptions(); connectYou(); tellParent({ kind: "lang", lang: savedLanguage() }); }
if (PART === "top") hearYou();
if (PART === "top") { renderTop(); new ResizeObserver(report).observe(root); }
if (PART === "left") { renderLeft(); setInterval(renderLeft, 15000); new ResizeObserver(report).observe(root); }
if (PART === "float") { renderFloat(); new ResizeObserver(report).observe(root); addEventListener("load", report, true); }
connect();

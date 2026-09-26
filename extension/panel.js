// One Weave overlay panel (?part=left | right | captions). Each reads the engine's WebSocket (subtitles.py,
// ws://localhost:8765 unless ?ws= says otherwise) and draws its share of the messages (see idea.md, "One standard"):
//   captions  speaking, partial, original, english, details (intent), voice, warning
//   left      prompt ("ask her"), curious + answer ("Curious?" questions), topic (words for the topic)
//   right     picture, details (cards for sayings, slang, customs)
// Until the engine sends curious/topic messages, the left panel builds simple questions from the word cards and
// pictures (answered from their notes) and shows starter words, so it works with today's engine.
// Clicks go back to the engine: forget (a kept word you don't know), ask (a question), practiced (hear a word).
const params = new URLSearchParams(location.search);
const PART = params.get("part") || "captions";
const WS_URL = params.get("ws") || "ws://localhost:8765";
const HTTP_URL = WS_URL.replace(/^ws/, "http").replace(/\/+$/, "");
document.body.dataset.part = PART;

const root = document.getElementById("root");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const asset = (path) => (/^(https?:|data:)/.test(path) ? path : `${HTTP_URL}/${String(path).replace(/^\/+/, "")}`);
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
function status() {
  if (PART === "captions") {
    const who = conn.me && conn.name ? `${conn.me} ↔ ${conn.name}` : conn.name ? `listening to ${conn.name}` : "";
    tellParent({ kind: "status", connected: conn.on, name: who });
    renderCaptions();
  }
}

// ---------- captions ----------
const cap = { lines: [], byId: {}, partial: "", draft: "", speaking: false, warning: "", warnTimer: 0, roles: null };
function captionLine(id) {
  let l = cap.byId[id];
  if (!l) {
    l = cap.byId[id] = { id, orig: "", en: "", kept: [], pending: false, english: false, tag: "" };
    cap.lines.push(l);
    while (cap.lines.length > 2) delete cap.byId[cap.lines.shift().id];
  }
  return l;
}
// Only in two-way calls (the engine sends "roles"): which language you speak; the other person gets the other one
function languageSwitch() {
  const mine = cap.roles.you, chosen = savedLanguage();
  const button = (lang, label) => `<button class="lang ${mine === lang ? "on" : ""}" data-lang="${lang}">${label}</button>`;
  return `<span class="speak">${chosen || cap.roles.fixed ? "I speak" : "I speak (guessing)"} ${button("en", "English")}${button("te", "తెలుగు")}</span>`;
}

function withKept(text, kept) {
  // Words kept in Telugu are underlined with their English; clicking one tells the engine you don't know it.
  let html = "", rest = text;
  for (const k of kept || []) {
    const i = rest.indexOf(k.telugu);
    if (i < 0) continue;
    html += esc(rest.slice(0, i)) + `<span class="kept" data-id="${esc(k.id)}" data-en="${esc(k.english)}" title="Click if you don't know this word">${esc(k.telugu)}<small>(${esc(k.english)})</small></span>`;
    rest = rest.slice(i + k.telugu.length);
  }
  return html + esc(rest);
}
function renderCaptions() {
  const dot = !conn.on ? "" : cap.speaking ? "speaking" : "on";
  const who = conn.name || "her";
  const statusText = !conn.on ? `Waiting for the Weave engine (${esc(WS_URL)})` : cap.speaking ? `${esc(who)} is speaking…` : `Listening to ${esc(who)}`;
  const lines = cap.lines.map((l, i) => `
    <div class="line ${i < cap.lines.length - 1 || cap.partial ? "old" : ""}">
      <div class="orig ${l.english && !l.you ? "faint" : l.you ? "" : "te"}">${l.you ? `<span class="tag you">${esc(conn.me || "You")}</span>${esc(l.orig)}` : l.english ? "said in English" : esc(l.orig)}</div>
      ${l.english ? `<div class="en">${l.tag ? `<span class="tag">${esc(l.tag)}</span>` : ""}${esc(l.orig)}</div>`
        : l.you ? (l.english ? "" : `<div class="en te ${l.pending ? "pending" : ""}">${l.pending ? "translating…" : esc(l.en)}</div>`)
        : `<div class="en ${l.pending ? (l.draft ? "draft" : "pending") : ""}">${l.tag ? `<span class="tag">${esc(l.tag)}</span>` : ""}${l.pending ? esc(l.draft || "translating…") : withKept(l.en, l.kept)}</div>`}
    </div>`).join("");
  // While she's mid-sentence: her words so far, and a faded draft of the English that firms up when she finishes
  const partial = cap.partial || cap.draft ? `<div class="line partial"><div class="orig te">${esc(cap.partial)}</div>
      ${cap.draft ? `<div class="en draft">${esc(cap.draft)}</div>` : ""}</div>` : "";
  root.innerHTML = `<div class="card captions">
      ${cap.warning ? `<div class="warning">⚠️ ${esc(cap.warning)}</div>` : ""}
      <div class="status"><span class="dot ${dot}"></span>${statusText}${cap.roles ? languageSwitch() : ""}</div>
      ${lines || partial ? lines + partial : `<div class="faint">Her words and the English will appear here.</div>`}
    </div>`;
  tellParent({ kind: "height", height: root.offsetHeight });
}
root.addEventListener("click", (e) => {
  const lang = e.target.closest(".lang");
  if (lang && PART === "captions") { chooseLanguage(lang.dataset.lang); return; }
  const k = e.target.closest(".kept");
  if (!k || PART !== "captions") return;
  send({ type: "forget", id: k.dataset.id });
  k.replaceWith(document.createTextNode(k.dataset.en));
});

// ---------- left: ask her, curious questions, topic words ----------
const GREETINGS = [  // starter words until the engine picks a topic
  { telugu: "నమస్కారం", roman: "namaskaram", english: "hello (respectful)" },
  { telugu: "బాగున్నారా?", roman: "bagunnara?", english: "are you well? (to an elder)" },
  { telugu: "నేను బాగున్నాను", roman: "nenu bagunnanu", english: "I'm well" },
  { telugu: "అన్నం తిన్నారా?", roman: "annam tinnara?", english: "have you eaten?" },
  { telugu: "తిన్నాను", roman: "tinnanu", english: "I ate" },
  { telugu: "అవును", roman: "avunu", english: "yes" },
  { telugu: "సరే", roman: "sare", english: "okay" },
  { telugu: "మళ్ళీ మాట్లాడదాం", roman: "malli matladadam", english: "let's talk again" },
];
const left = { ask: null, askTimer: 0, questions: [], engineQuestions: false, topic: "Greetings", words: GREETINGS, engineTopic: false,
  said: [], open: null };
const MAX_QUESTIONS = 4, QUESTION_TTL_MS = 90000;
const QUESTION_KINDS = new Set(["idiom", "slang", "phrase", "culture", "festival", "food", "family", "clothing"]);

function stemFor(card) {
  const t = card.title;
  switch (card.category) {
    case "idiom": case "phrase": case "slang": return `What does “${t}” mean?`;
    case "family": return `Who is “${t}”?`;
    case "culture": return `What is “${t}”?`;
    default: return `What is ${t}?`;
  }
}
function addLocalQuestion(q) {
  if (left.engineQuestions) return;
  const same = (x) => x.id === q.id || (q.word && x.word === q.word);
  const old = left.questions.find(same);
  if (old && !q.replace) return;
  if (old) { left.questions = left.questions.filter((x) => !same(x)); q.answer = old.answer || q.answer; }
  left.questions.unshift({ ...q, at: Date.now() });
  left.questions = left.questions.slice(0, MAX_QUESTIONS);
}
function rememberSaid(card) {  // words she used this call, pinned above the topic words (not whole proverbs)
  const key = (card.title || "").toLowerCase();
  if (!card.id || !card.telugu || card.category === "idiom" || left.said.some((w) => w.id === card.id || w.roman.toLowerCase() === key)) return;
  left.said.unshift({ id: card.id, telugu: card.telugu, roman: card.title, english: card.english || card.note || "" });
  left.said = left.said.slice(0, 4);
}
// New questions push the list down; while the mouse is over the panel, hold it still so a click lands where you aimed.
let leftHeld = false, leftPending = false;
document.addEventListener("mouseover", () => { leftHeld = true; });
document.documentElement.addEventListener("mouseleave", () => { leftHeld = false; if (leftPending) { leftPending = false; renderLeft(); } });
function renderLeft(force = false) {
  if (leftHeld && !force) { leftPending = true; return; }
  const now = Date.now();
  left.questions = left.questions.filter((q) => q.id === left.open || now - q.at < QUESTION_TTL_MS);
  const ask = left.ask ? `<section class="card ask ${left.ask.fresh ? "enter" : ""}">
      <div class="eyebrow">${esc(left.ask.context ? `${left.ask.context} · ask ${conn.name || "her"}` : `Ask ${conn.name || "her"}${left.ask.about ? ` about ${left.ask.about}` : ""}`)}</div>
      <div class="q-te te">${esc(left.ask.telugu)}</div><div class="q-roman">“${esc(left.ask.roman)}”</div><div class="q-en">${esc(left.ask.english || "")}</div>
    </section>` : "";
  if (left.ask) left.ask.fresh = false;
  const questions = left.questions.length ? left.questions.map((q) => `
      <button class="question ${q.id === left.open ? "open" : ""}" data-q="${esc(q.id)}">
        <div class="q">${esc(q.text)}</div>
        <div class="answer">${q.answer ? formatAnswer(q.answer) : `<span class="loading">Looking it up</span>`}</div>
      </button>`).join("") : `<div class="empty">Questions about what she says will show up here. Click one to find out.</div>`;
  const wordRow = (w, said) => `<div class="word ${said ? "said" : ""}">
      <div><span class="w-te te">${esc(w.telugu)}</span> · <span class="w-roman">${esc(w.roman)}</span>${said ? `<span class="tag-said">she said</span>` : w.learning ? `<span class="tag-said">learning</span>` : ""}</div>
      <div class="w-en">${esc(w.english)}</div>
      <button class="hear" title="Hear it" data-hear="${esc(w.telugu)}" data-roman="${esc(w.roman)}" data-id="${esc(w.id || "")}">🔊</button>
    </div>`;
  const said = new Set(left.said.flatMap((w) => [w.id, w.roman.toLowerCase().replace(/\?$/, "")]));
  const words = [...left.said.map((w) => wordRow(w, true)),
    ...left.words.filter((w) => !said.has(w.id) && !said.has(String(w.roman).toLowerCase().replace(/\?$/, ""))).map((w) => wordRow(w, false))].join("");
  root.innerHTML = `${ask}
    <section class="card section">
      <div class="head"><span class="eyebrow">Curious?</span></div>
      <div class="questions scroll">${questions}</div>
    </section>
    <section class="card section grow">
      <div class="head"><span class="eyebrow">Words for</span><span class="topic">${esc(left.topic)}</span></div>
      <div class="words scroll">${words}</div>
    </section>`;
}
function formatAnswer(a) {
  const say = a.telugu || a.roman ? `<div class="say">${a.telugu ? `<span class="te">${esc(a.telugu)}</span>` : ""}${a.telugu && a.roman ? " · " : ""}${esc(a.roman || "")}</div>` : "";
  return `${say}${esc(a.text || "")}`;
}
root.addEventListener("click", (e) => {
  if (PART !== "left") return;
  const q = e.target.closest(".question");
  if (q) {
    const item = left.questions.find((x) => x.id === q.dataset.q);
    if (!item) return;
    left.open = left.open === item.id ? null : item.id;
    if (left.open && !item.asked) {
      item.asked = true;
      send({ type: "ask", id: item.id, word: item.word || null, text: item.text });  // the engine answers (and learns you asked)
    }
    renderLeft(true);
    return;
  }
  const hear = e.target.closest(".hear");
  if (hear) {
    speak(hear.dataset.hear, hear.dataset.roman);
    if (hear.dataset.id) send({ type: "practiced", id: hear.dataset.id });
  }
});
function speak(telugu, roman) {
  if (!("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const voice = speechSynthesis.getVoices().find((v) => v.lang && v.lang.toLowerCase().startsWith("te"));
  const u = new SpeechSynthesisUtterance(voice ? telugu : roman);
  if (voice) u.voice = voice;
  u.lang = voice ? voice.lang : "en-IN";
  u.rate = 0.85;
  speechSynthesis.speak(u);
}

// ---------- right: pictures and meanings ----------
const right = { items: [] };
const MAX_ITEMS = 4, ITEM_TTL_MS = 45000;
const MEANING_KINDS = new Set(["idiom", "slang", "phrase", "culture"]);
function addRight(item) {
  const words = item.words || [];
  if (item.kind === "picture") right.items = right.items.filter((x) => !(x.kind === "meaning" && words.includes(x.word)));
  if (item.kind === "meaning" && right.items.some((x) => x.kind === "picture" && (x.words || []).includes(item.word))) return;
  const existing = right.items.find((x) => x.key === item.key);
  if (existing) { existing.at = Date.now(); return; }
  right.items.unshift({ ...item, at: Date.now(), fresh: true });
  right.items = right.items.filter((x, i) => x.pinned || i < MAX_ITEMS);
}
function renderRight() {
  const now = Date.now();
  right.items = right.items.filter((x) => x.pinned || now - x.at < ITEM_TTL_MS);
  root.innerHTML = right.items.length ? `<div class="stack">${right.items.map((x) => {
    const fading = !x.pinned && now - x.at > ITEM_TTL_MS - 8000 ? "fading" : "";
    const enter = x.fresh ? "enter" : "";  // animate only when it first appears, not on every redraw
    x.fresh = false;
    return x.kind === "picture"
      ? `<div class="card pic ${enter} ${x.pinned ? "pinned" : ""} ${fading}" data-key="${esc(x.key)}" title="Click to keep it">
           <img src="${esc(asset(x.image))}" alt=""><div class="body"><div class="name">${esc(x.name)}</div><div class="desc">${esc(x.description || "")}</div></div></div>`
      : `<div class="card meaning ${enter} ${x.pinned ? "pinned" : ""} ${fading}" data-key="${esc(x.key)}" title="Click to keep it">
           <div class="body"><div class="eyebrow kind">${esc(x.label)}</div><div class="title ${/[ఀ-౿]/.test(x.title) ? "te" : ""}">${esc(x.title)}</div>
           <div class="desc">${esc(x.note)}</div></div></div>`;
  }).join("")}</div>` : `<div class="card"><div class="empty">Pictures of what she mentions, and what her sayings mean, will show up here.</div></div>`;
}
root.addEventListener("click", (e) => {
  if (PART !== "right") return;
  const el = e.target.closest("[data-key]");
  const item = el && right.items.find((x) => x.key === el.dataset.key);
  if (item) { item.pinned = !item.pinned; item.at = Date.now(); renderRight(); }
});
const LABELS = { idiom: "Saying", slang: "Slang", phrase: "Phrase", culture: "Custom" };

// ---------- messages ----------
function handle(m) {
  if (m.type === "call") { conn.name = m.caller || conn.name; conn.me = m.you && m.you !== "You" ? m.you : ""; status(); }
  else if (m.caller && m.caller !== conn.name) { conn.name = m.caller; status(); }
  if (PART === "captions") return handleCaptions(m);
  if (PART === "left") return handleLeft(m);
  if (PART === "right") return handleRight(m);
}
function handleCaptions(m) {
  switch (m.type) {
    case "speaking": cap.speaking = true; break;
    case "partial": cap.partial = m.text || ""; if (!m.text) cap.speaking = false; break;
    case "draft": cap.draft = m.text || ""; break;
    case "roles": cap.roles = { you: m.you, them: m.them, fixed: m.fixed }; break;
    case "original": {
      const l = captionLine(m.id);
      l.orig = m.text; l.english = m.route === "english"; l.pending = !l.english; l.you = !!m.you;
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
    case "prompt":
      left.ask = { ...m, fresh: true };
      clearTimeout(left.askTimer); left.askTimer = setTimeout(() => { left.ask = null; renderLeft(); }, 45000);
      break;
    case "curious":  // the engine's questions (Laya-picked), newest first
      left.engineQuestions = true;
      for (const q of (m.questions || []).slice().reverse()) {
        if (left.questions.some((x) => x.id === q.id)) continue;
        left.questions.unshift({ id: q.id, text: q.text, word: q.word || null, kind: q.kind, answer: q.answer || null, at: Date.now() });
      }
      left.questions = left.questions.slice(0, MAX_QUESTIONS);
      break;
    case "answer": {
      const q = left.questions.find((x) => x.id === m.id);
      if (q) q.answer = { text: m.text, telugu: m.telugu, roman: m.roman };
      renderLeft(true);  // an answer you're waiting for shows even while the list is held still
      return;
    }
    case "topic":
      left.engineTopic = true;
      left.topic = m.topic || left.topic;
      left.words = m.words || left.words;
      break;
    case "details":
      for (const c of m.cards || []) {
        if (!c.id) continue;
        rememberSaid(c);
        // Questions for things worth asking about; everyday words (illu, ooru) go to the word list, and words they
        // probably know (p >= 0.7) need no question. Pictures add their own "What is ___?".
        if (!QUESTION_KINDS.has(c.category) || c.p >= 0.7) continue;
        addLocalQuestion({ id: c.id, word: c.id, text: stemFor(c),
          answer: c.note ? { text: c.note, telugu: c.telugu, roman: c.title } : null });
      }
      break;
    case "picture":
      // Pictures carry the word-list ids they show, so "What is NTR?" replaces the card's question for the same word.
      addLocalQuestion({ id: `pic:${m.id}`, word: (m.lexicon_ids || [])[0] || null, replace: true, text: `What is ${m.name}?`,
        answer: { text: m.description || "", roman: m.name } });
      break;
    default: return;
  }
  renderLeft();
}
function handleRight(m) {
  if (m.type === "picture" && m.image) {
    addRight({ key: `pic:${m.id}`, kind: "picture", name: m.name, description: m.description, image: m.image, words: m.lexicon_ids || [] });
  } else if (m.type === "details") {
    for (const c of m.cards || []) {
      if (!c.note || !MEANING_KINDS.has(c.category)) continue;
      addRight({ key: `card:${c.id || c.title}`, kind: "meaning", word: c.id, label: LABELS[c.category] || "Meaning", title: c.title, note: c.note });
    }
  } else return;
  renderRight();
}

// ---------- start ----------
if (PART === "captions") { renderCaptions(); connectYou(); new ResizeObserver(() => tellParent({ kind: "height", height: root.offsetHeight })).observe(root); }
if (PART === "left") { renderLeft(); setInterval(renderLeft, 15000); }
if (PART === "right") { renderRight(); setInterval(renderRight, 5000); }
connect();

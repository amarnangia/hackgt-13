// Weave captions: reads the translator's WebSocket (subtitles.py on :8765, and --outgoing on :8767) and shows the
// live line over the WhatsApp call. Same messages overlay.html reads.
const HOST = "localhost";
const PORTS = { them: 8765, you: 8767 };
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const img = (path) => `http://${HOST}:${PORTS.them}/${path}`;
const tell = (state) => parent.postMessage({ source: "weave-captions", state }, "*");

const st = { name: "Grandma", lines: [], byKey: {}, partial: {}, connected: {}, translating: 0, pulses: {}, typing: 0 };

function connect(side) {
  let ws;
  try { ws = new WebSocket(`ws://${HOST}:${PORTS[side]}`); } catch { return setTimeout(() => connect(side), 3000); }
  ws.onopen = () => { st.connected[side] = true; status(); };
  ws.onclose = () => { st.connected[side] = false; status(); setTimeout(() => connect(side), 2500); };
  ws.onerror = () => {};
  ws.onmessage = (e) => { try { handle(side, JSON.parse(e.data)); } catch (err) { console.warn(err); } };
  if (side === "them") st.ws = ws;
}

function status() {
  const on = st.connected.them;
  $("dot").classList.toggle("on", on); $("p-dot").classList.toggle("on", on);
  $("p-text").textContent = on ? `Listening to ${st.name}` : "Waiting for subtitles.py";
  if (!on) tell("idle");
}

function speaking(side, on) {
  const wire = $("wire");
  clearInterval(st.pulses[side]);
  if (!on) return;
  const shoot = () => { const p = document.createElement("i"); p.className = "pulse" + (side === "them" ? " rev" : ""); wire.append(p); p.onanimationend = () => p.remove(); };
  shoot(); st.pulses[side] = setInterval(shoot, 620);
}

function translating(delta) {
  st.translating = Math.max(0, st.translating + delta);
  $("wire").classList.toggle("translating", st.translating > 0);
}

function newLine(side, key) {
  const line = { side, key, orig: "", tr: "", pending: false, kept: [], tag: null, pic: null, caret: "orig" };
  st.lines.push(line); if (st.lines.length > 6) st.lines.shift();
  st.byKey[key] = line;
  tell("line");
  return line;
}

function handle(side, m) {
  const key = (id) => `${side}:${id}`;
  if (m.type === "prompt") { if (m.caller) { st.name = m.caller; $("name").textContent = m.caller; } return showAsk(m); }
  if (m.type === "speaking") { speaking(side, true); st.partial[side] = st.partial[side] || newLine(side, key("p" + Date.now())); return render(); }
  if (m.type === "partial") {
    if (!m.text) return;
    const l = st.partial[side] || (st.partial[side] = newLine(side, key("p" + Date.now())));
    l.orig = m.text; l.caret = "orig"; return render();
  }
  if (m.type === "original") {
    speaking(side, false);
    const l = st.partial[side] || newLine(side, key(m.id)); st.partial[side] = null;
    delete st.byKey[l.key]; l.key = key(m.id); st.byKey[l.key] = l;
    l.orig = m.text; l.caret = null;
    if (m.route === "english") { l.english = true; } else { l.pending = true; translating(+1); }
    return render();
  }
  const l = st.byKey[key(m.id)] || (m.type === "picture" ? st.lines.filter((x) => x.side === side).at(-1) : null);
  if (!l) return;
  if (m.type === "english") {
    if (l.pending) { l.pending = false; translating(-1); }
    if (m.route === "english") return render();
    l.kept = m.kept || [];
    typeOut(l, m.text);
  } else if (m.type === "details") {
    if (side === "them" && (m.intent === "question" || m.intent === "request")) l.tag = m.intent === "question" ? "Asked you" : "Request";
    render();
  } else if (m.type === "picture") {
    l.pic = { name: m.name, description: m.description, image: m.image };
    render();
  }
}

// Reveal the English a few letters at a time, like the rest of Weave.
function typeOut(l, text) {
  const chars = [...text]; let n = 0; l.caret = "tr";
  const t = setInterval(() => {
    n = Math.min(chars.length, n + 2); l.tr = chars.slice(0, n).join("");
    if (n >= chars.length) { clearInterval(t); l.caret = null; }
    render();
  }, 22);
}

function withKept(text, kept) {
  let html = esc(text);
  kept.forEach((k, i) => {
    const re = new RegExp(`(^|[^\\p{L}])(${esc(k.telugu).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})(?![\\p{L}])`, "iu");
    html = html.replace(re, `$1<span class="w" data-k="${i}">$2</span>`);
  });
  return html;
}

function render() {
  const lines = st.lines.filter((l) => l.orig || l.tr);
  const cur = lines.at(-1), prev = lines.at(-2);
  $("prev").textContent = prev ? (prev.tr || prev.orig) : "";
  if (!cur) { $("cur").innerHTML = `<div class="pending" style="color:var(--text-3)">Captions appear when ${esc(st.name)} speaks</div>`; return; }
  const translated = !cur.english;
  $("cur").innerHTML = `<div class="who ${cur.side}">${cur.side === "you" ? "You" : esc(st.name)}${cur.tag ? `<span class="tag">${cur.tag}</span>` : ""}</div>
    ${translated ? `<div class="orig ${cur.caret === "orig" ? "caret" : ""}">${esc(cur.orig)}</div>` : ""}
    ${!translated ? `<div class="tr">${esc(cur.orig)}</div>` : cur.pending ? `<div class="pending">Translating</div>`
      : cur.tr ? `<div class="tr ${cur.caret === "tr" ? "caret" : ""}">${withKept(cur.tr, cur.caret ? [] : cur.kept)}</div>` : ""}
    ${cur.pic ? `<button class="pic" id="pic"><img src="${esc(img(cur.pic.image))}" alt=""><span>${esc(cur.pic.name)}</span></button>` : ""}`;
  $("cur").querySelectorAll(".w").forEach((w) => w.onclick = () => { const k = cur.kept[+w.dataset.k]; showCard({ big: k.telugu, en: k.english }); });
  const pic = $("pic"); if (pic) pic.onclick = () => showCard({ image: img(cur.pic.image), big: cur.pic.name, en: cur.pic.description });
}

let askTimer = 0, cardTimer = 0;
function showAsk(m) {
  const a = $("ask");
  a.innerHTML = `<span class="eyebrow" style="color:var(--accent)">Ask</span><span class="te">${esc(m.telugu)}</span><span class="rom">“${esc(m.roman)}”</span><span class="en">${esc(m.english || "")}</span>`;
  a.hidden = false; $("prev").hidden = true; tell("line");
  clearTimeout(askTimer); askTimer = setTimeout(() => { a.hidden = true; $("prev").hidden = false; }, 25000);
}
function showCard(c) {
  $("card").innerHTML = `<div class="card">${c.image ? `<img src="${esc(c.image)}" alt="">` : ""}<div class="t"><div class="big">${esc(c.big)}</div><div class="en">${esc(c.en || "")}</div></div>
    <button class="x" aria-label="Close">✕</button></div>`;
  $("card").querySelector(".x").onclick = () => ($("card").innerHTML = "");
  clearTimeout(cardTimer); cardTimer = setTimeout(() => ($("card").innerHTML = ""), 12000);
}

render(); status();
connect("them"); connect("you");

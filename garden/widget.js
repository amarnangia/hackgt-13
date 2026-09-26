// Weave garden widget for iPhone (Scriptable app: https://scriptable.app)
// Setup: paste this into a new Scriptable script, add a Scriptable widget to the home screen,
// long-press it > Edit Widget > Script: this one, Parameter: http://<your Mac's IP>:8770
// (`python -m garden` prints that URL). The phone must be on the same Wi-Fi as the Mac.

const SERVER = (args.widgetParameter || "http://192.168.1.10:8770").replace(/\/$/, "");
const FAMILY = config.widgetFamily || "medium";
const NIGHT = Device.isUsingDarkAppearance();
const SIZES = { small: [158, 158], medium: [338, 158], large: [338, 354] };
const [W, H] = SIZES[FAMILY] || SIZES.medium;

const T = NIGHT
  ? { skyTop: "#0a1430", skyBot: "#2a3160", hill1: "#1b3024", hill2: "#213b2a", g1: "#294628", g2: "#1c331d", soil: "#6b4a2e", stem: "#4f8f45", leaf: "#5c9c50", leaf2: "#74b061", ink: "#edf2ea", ink2: "#b8c4b9", accent: "#f0a040" }
  : { skyTop: "#a9d8ee", skyBot: "#fce8cc", hill1: "#bcd9a4", hill2: "#9dc687", g1: "#8cbd67", g2: "#6f9f4c", soil: "#8a5a33", stem: "#4c8b3f", leaf: "#5fa052", leaf2: "#7dbb62", ink: "#1d2a20", ink2: "#4c5a4f", accent: "#d4700c" };

// ---------- data (cached so the widget still shows something off Wi-Fi) ----------
const fm = FileManager.local();
const cachePath = fm.joinPath(fm.documentsDirectory(), "weave-garden.json");
async function load() {
  try {
    const req = new Request(`${SERVER}/api/garden`);
    req.timeoutInterval = 6;
    const data = await req.loadJSON();
    fm.writeString(cachePath, JSON.stringify(data));
    return { data, stale: false };
  } catch (e) {
    if (fm.fileExists(cachePath)) return { data: JSON.parse(fm.readString(cachePath)), stale: true };
    return { data: null, stale: true };
  }
}

// ---------- drawing helpers ----------
const col = (hex, a = 1) => new Color(hex, a);
const hash = (s) => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };
const rng = (seed) => () => ((seed = Math.imul(seed ^ (seed >>> 15), 2246822507) + 0x9e3779b9 >>> 0) % 10000) / 10000;
const mix = (a, b, t) => {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
};

const dc = new DrawContext();
dc.size = new Size(W, H);
dc.opaque = true;
dc.respectScreenScale = true;

function fill(path, hex, a = 1) { dc.addPath(path); dc.setFillColor(col(hex, a)); dc.fillPath(); }
function stroke(path, hex, w) { dc.addPath(path); dc.setStrokeColor(col(hex)); dc.setLineWidth(w); dc.strokePath(); }
function circle(x, y, r, hex, a = 1) { dc.setFillColor(col(hex, a)); dc.fillEllipse(new Rect(x - r, y - r, r * 2, r * 2)); }
function vgrad(y0, y1, top, bot) {
  const n = Math.ceil(y1 - y0);
  for (let i = 0; i < n; i++) { dc.setFillColor(col(mix(top, bot, i / n))); dc.fillRect(new Rect(0, y0 + i, W, 1.5)); }
}
// A leaf/petal pointing at `ang` degrees from (x, y): two quad curves from base to tip and back.
function petal(x, y, ang, len, wid, hex) {
  const a = (ang * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
  const at = (u, v) => new Point(x + u * c - v * s, y + u * s + v * c);
  const p = new Path();
  p.move(at(0, 0));
  p.addQuadCurve(at(len, 0), at(len * 0.45, -wid));
  p.addQuadCurve(at(0, 0), at(len * 0.45, wid));
  p.closeSubpath();
  fill(p, hex);
}

function flower(x, y, cat, s) {
  const R = (n, rad, r, hex, off = 0) => { for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2 + off; circle(x + Math.cos(a) * rad * s, y + Math.sin(a) * rad * s, r * s, hex); } };
  const P = (n, len, wid, hex, start = -90, step) => { for (let i = 0; i < n; i++) petal(x, y, start + i * (step ?? 360 / n), len * s, wid * s, hex); };
  switch (cat) {
    case "food": R(14, 12, 5.2, "#d9700a"); R(11, 7.5, 4.6, "#f09a1a", 0.3); R(7, 3.6, 3.6, "#fbb934", 0.6); circle(x, y, 2.6 * s, "#ffd25e"); break;
    case "place": petal(x, y + 2 * s, 190, 24 * s, 6 * s, "#e97ba1"); petal(x, y + 2 * s, -10, 24 * s, 6 * s, "#e97ba1");
      P(5, 25, 7, "#ec8fb0", -154, 32); P(3, 20, 5, "#f8c3d6", -122, 32); circle(x, y - 2 * s, 4 * s, "#f7cf4a"); break;
    case "festival": P(5, 21, 11, "#dc2f55", -80); circle(x, y, 4 * s, "#8e1230"); circle(x + 6 * s, y - 12 * s, 2.2 * s, "#f7d36b"); break;
    case "vehicle": P(14, 19, 3.6, "#f2b705"); P(14, 14, 2.8, "#f7cf3a", -77); circle(x, y, 7 * s, "#6b3f1d"); circle(x, y, 4 * s, "#4d2c13"); break;
    case "clothing": circle(x, y, 14 * s, "#4f6bd8"); P(5, 13, 2.5, "#8ea3ef"); circle(x, y, 5.5 * s, "#f4f6ff"); circle(x, y, 2 * s, "#f2d66b"); break;
    case "family": R(9, 10, 5.6, "#a92b64"); R(7, 6.2, 5, "#c2417a", 0.4); R(4, 2.8, 3.6, "#e2709e", 0.9); circle(x, y, 2.4 * s, "#f4a3c2"); break;
    case "slang":
    case "idiom": for (let i = 0; i < 6; i++) circle(x + (i % 2 ? 3 : -3) * s, y - i * 5.5 * s + 10 * s, (4.2 - i * 0.4) * s, i % 2 ? "#b18ae0" : "#9a6ad0"); break;
    default: P(5, 16, 6, "#b8ae8c"); P(5, 15, 5.2, "#fbfaf4"); circle(x, y, 3 * s, "#e6c95a");
  }
}

function plant(p, x, y, s) {
  const r = rng(hash(p.phrase)), g = p.growth;
  const mound = new Path();
  mound.move(new Point(x - 15 * s, y + 1)); mound.addQuadCurve(new Point(x + 15 * s, y + 1), new Point(x, y - 9 * s)); mound.closeSubpath();
  fill(mound, T.soil);
  if (p.stage === "seed") {
    circle(x - 2 * s, y - 4 * s, 3.4 * s, "#6e4322");
    if (g >= 1) { const st = new Path(); st.move(new Point(x, y - 5 * s)); st.addLine(new Point(x, y - (6 + g * 6) * s)); stroke(st, T.stem, 2 * s); }
    if (g >= 2) { petal(x, y - 16 * s, -35, 9 * s, 3.5 * s, T.leaf2); petal(x, y - 16 * s, 215, 8 * s, 3.5 * s, T.leaf); }
    return;
  }
  const bloom = p.stage === "bloom";
  const h = (bloom ? 84 + Math.min(20, (p.heard - 8) * 1.2) : 30 + (g - 3) * 9) * s;
  const bend = (r() - 0.5) * 16 * s, tip = bend * 0.45;
  const stem = new Path();
  stem.move(new Point(x, y)); stem.addQuadCurve(new Point(x + tip, y - h), new Point(x + bend, y - h / 2));
  stroke(stem, T.stem, (bloom ? 3.2 : 2.6) * s);
  const n = bloom ? 6 : Math.min(5, g - 1);
  for (let i = 0; i < n; i++) {
    const t = 0.12 + (i / n) * 0.7, side = i % 2 ? 1 : -1, len = (bloom ? 22 : 16) * (1.1 - t * 0.5) * s;
    const lx = x + 2 * (1 - t) * t * bend + t * t * tip;
    petal(lx, y - h * t, side > 0 ? -28 - r() * 16 : 208 + r() * 16, len, len * 0.3, i % 3 ? T.leaf : T.leaf2);
  }
  if (bloom) flower(x + tip, y - h, p.category, s * (1 + Math.min(0.35, (p.heard - 8) * 0.025)));
  else if (g >= 6) { petal(x + tip, y - h, -90, 12 * s, 4.5 * s, "#e8850c"); petal(x + tip, y - h, -60, 8 * s, 3 * s, T.leaf); petal(x + tip, y - h, -120, 8 * s, 3 * s, T.leaf); }
  else { petal(x + tip, y - h, -50, 11 * s, 4 * s, T.leaf2); petal(x + tip, y - h, 230, 10 * s, 4 * s, T.leaf); }
}

function scene(data) {
  const horizon = H * (FAMILY === "large" ? 0.52 : 0.5);
  vgrad(0, horizon + 20, T.skyTop, T.skyBot);
  if (NIGHT) {
    const r = rng(42);
    for (let i = 0; i < 40; i++) circle(r() * W, r() * horizon * 0.9, r() * 0.8 + 0.3, "#ffffff", r() * 0.6 + 0.3);
    if (FAMILY !== "small") { circle(W * 0.68, 28, 10, "#f3ecd2"); circle(W * 0.68 + 5, 24, 9, T.skyTop); }
  } else if (FAMILY !== "small") {
    circle(W * 0.68, 30, 22, "#ffd76a", 0.25); circle(W * 0.68, 30, 12, "#ffd76a");
  }
  const hill = (y0, a, hex) => {
    const p = new Path(); p.move(new Point(0, y0));
    p.addCurve(new Point(W * 0.55, y0 - a * 0.2), new Point(W * 0.2, y0 - a), new Point(W * 0.35, y0 + a * 0.6));
    p.addCurve(new Point(W, y0 - a * 0.5), new Point(W * 0.75, y0 - a * 1.1), new Point(W * 0.9, y0 + a * 0.3));
    p.addLine(new Point(W, H)); p.addLine(new Point(0, H)); p.closeSubpath(); fill(p, hex);
  };
  hill(horizon - 6, 22, T.hill1);
  hill(horizon + 4, 12, T.hill2);
  vgrad(horizon + 12, H, T.g1, T.g2);

  if (!data) return;
  const max = { small: 5, medium: 10, large: 15 }[FAMILY] || 10;
  const shown = [...data.plants].sort((a, b) => b.growth - a.growth || b.last_heard - a.last_heard).slice(0, max)
    .sort((a, b) => hash(a.phrase) - hash(b.phrase));
  const rows = FAMILY === "large" ? [{ y: H * 0.74, s: 0.62 }, { y: H * 0.95, s: 0.78 }] : [{ y: H - 10, s: FAMILY === "small" ? 0.55 : 0.5 }];
  shown.forEach((p, i) => {
    const row = rows[i % rows.length], k = Math.floor(i / rows.length), per = Math.ceil(shown.length / rows.length);
    const x = 16 + ((k + 0.5 + (i % rows.length) * 0.35) / per) * (W - 32);
    plant(p, x, row.y, row.s);
  });
}

// ---------- widget ----------
const { data, stale } = await load();
scene(data);

const w = new ListWidget();
w.backgroundImage = dc.getImage();
w.setPadding(12, 14, 12, 14);
w.url = SERVER;
w.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);

const text = (parent, str, size, hex, bold = false, serif = false) => {
  const t = parent.addText(str);
  t.font = serif ? new Font(bold ? "Georgia-Bold" : "Georgia", size) : bold ? Font.semiboldSystemFont(size) : Font.systemFont(size);
  t.textColor = col(hex);
  return t;
};

if (!data) {
  text(w, "Weave", 15, T.ink, true, true);
  w.addSpacer(4);
  text(w, "Can't reach the garden. Start it on your Mac with python -m garden, then set this widget's parameter to the URL it prints.", 11, T.ink2);
  w.addSpacer();
} else {
  const t = data.totals;
  const top = w.addStack();
  top.layoutHorizontally();
  top.centerAlignContent();
  const left = top.addStack();
  left.layoutVertically();
  text(left, "WEAVE", 9, T.ink2, true).textOpacity = 0.8;
  text(left, `${t.bloom} blooming`, FAMILY === "small" ? 17 : 19, T.ink, true, true);
  if (FAMILY !== "small") text(left, `${t.sprout} sprouting · ${t.seed} seeds`, 11, T.ink2);
  if (FAMILY !== "small" && (data.calls.live || stale))
    text(left, data.calls.live ? "● on a call, growing live" : "offline · last saved garden", 9, data.calls.live ? (NIGHT ? "#6cc07a" : "#2f6f39") : T.ink2, true);
  top.addSpacer();
  if (data.streak > 0 && FAMILY !== "small") {
    const pill = top.addStack();
    pill.setPadding(3, 8, 3, 8);
    pill.cornerRadius = 10;
    pill.backgroundColor = col(NIGHT ? "#000000" : "#ffffff", NIGHT ? 0.35 : 0.6);
    text(pill, `🔥 ${data.streak}`, 12, T.accent, true);
  }
  if (FAMILY === "small") text(w, `${t.sprout} sprouting${data.streak ? ` · 🔥 ${data.streak}` : ""}`, 10, T.ink2);
  if (FAMILY === "large") {
    w.addSpacer(8);
    const next = data.plants.filter((p) => p.stage === "sprout").sort((a, b) => a.to_next - b.to_next).slice(0, 3);
    if (next.length) {
      text(w, "ALMOST BLOOMING", 9, T.ink2, true);
      for (const p of next) text(w, `${p.phrase} · ${p.to_next} more`, 12, T.ink);
    }
  }
  w.addSpacer();
}

if (config.runsInWidget) Script.setWidget(w);
else if (FAMILY === "small") await w.presentSmall();
else if (FAMILY === "large") await w.presentLarge();
else await w.presentMedium();
Script.complete();

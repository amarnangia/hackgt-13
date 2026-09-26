// Puts the Weave caption bar on top of WhatsApp Web. The captions themselves live in captions.html (an extension
// page, so WhatsApp's security rules don't block its connection to the translator on this Mac).
(() => {
  if (document.getElementById("weave-captions")) return;
  const KEY = "weave-captions-box";
  const saved = (() => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } })();

  const host = document.createElement("div");
  host.id = "weave-captions";
  const root = host.attachShadow({ mode: "open" });
  root.innerHTML = `
    <style>
      :host { all: initial; }
      .box { position: fixed; z-index: 2147483000; left: ${saved.left ?? "calc(50% - 280px)"}; top: ${saved.top ?? "auto"};
             bottom: ${saved.top ? "auto" : "88px"}; width: ${saved.width ?? "560px"}; height: ${saved.height ?? "208px"};
             min-width: 300px; min-height: 120px; resize: both; overflow: hidden; border-radius: 18px;
             background: rgba(8, 9, 11, .74); backdrop-filter: blur(18px) saturate(1.2); -webkit-backdrop-filter: blur(18px) saturate(1.2);
             border: 1px solid rgba(255, 255, 255, .12); box-shadow: 0 24px 60px -18px rgba(0, 0, 0, .8);
             transition: opacity .3s cubic-bezier(.2,.8,.2,1), transform .35s cubic-bezier(.32,.72,0,1), width .35s cubic-bezier(.32,.72,0,1), height .35s cubic-bezier(.32,.72,0,1); }
      .box.idle { width: 212px !important; height: 40px !important; resize: none; border-radius: 999px; }
      iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; background: transparent; color-scheme: normal; }
      .grip { position: absolute; left: 0; right: 44px; top: 0; height: 30px; cursor: grab; z-index: 2; }
      .box.idle .grip { right: 0; height: 100%; }
      .grip:active { cursor: grabbing; }
      .min { position: absolute; top: 6px; right: 8px; z-index: 3; width: 26px; height: 22px; border-radius: 7px; border: 0; cursor: pointer;
             background: transparent; color: rgba(243, 243, 241, .5); font: 600 13px/22px system-ui; transition: background .2s, color .2s; }
      .min:hover { background: rgba(255, 255, 255, .08); color: #f3f3f1; }
      .box.idle .min { display: none; }
    </style>
    <div class="box idle" part="box">
      <div class="grip" title="Drag to move"></div>
      <button class="min" title="Hide captions until the next line">–</button>
      <iframe allowtransparency="true" src="${chrome.runtime.getURL("captions.html")}"></iframe>
    </div>`;
  document.documentElement.append(host);
  const box = root.querySelector(".box"), grip = root.querySelector(".grip");

  // captions.html says when a line starts (open up) and when the translator isn't running (shrink to a pill).
  // "–" shrinks it until she says the next line.
  addEventListener("message", (e) => {
    if (!e.data || e.data.source !== "weave-captions") return;
    if (e.data.state === "line") box.classList.remove("idle");
    if (e.data.state === "idle") box.classList.add("idle");
  });
  root.querySelector(".min").onclick = () => box.classList.add("idle");

  // drag anywhere along the top edge; remember where it was left
  let start = null;
  grip.addEventListener("pointerdown", (e) => {
    const r = box.getBoundingClientRect();
    start = { x: e.clientX, y: e.clientY, left: r.left, top: r.top };
    grip.setPointerCapture(e.pointerId);
    box.style.transition = "none";
  });
  grip.addEventListener("pointermove", (e) => {
    if (!start) return;
    const left = Math.min(innerWidth - 80, Math.max(-box.offsetWidth + 80, start.left + e.clientX - start.x));
    const top = Math.min(innerHeight - 40, Math.max(0, start.top + e.clientY - start.y));
    Object.assign(box.style, { left: left + "px", top: top + "px", bottom: "auto" });
  });
  const save = () => {
    const r = box.getBoundingClientRect();
    if (box.classList.contains("idle")) return;
    localStorage.setItem(KEY, JSON.stringify({ left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px" }));
  };
  grip.addEventListener("pointerup", () => { start = null; box.style.transition = ""; save(); });
  new ResizeObserver(() => { if (!start) save(); }).observe(box);
})();

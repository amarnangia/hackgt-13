# The family story keeper: every call becomes something both sides keep.
#
# During the call, CallRecorder keeps every line (Telugu, English, pictures, cards, prompts) and records the
# caller's side of the audio (the same audio Muse hears; your mic is never recorded). When the call ends it
#   - cuts a clip of her real voice for every line,
#   - asks Muse Spark to find the stories she told and suggest questions for next time,
#   - writes calls/<date-time>/index.html: the call's story page (stories with her voice, pictures, words, questions,
#     and a Telugu message to send her),
#   - updates calls/dictionary.html: the family dictionary of every word the grandkid has heard, with her voice.
# Everything stays on this Mac (calls/ is gitignored). --no-record keeps the page but saves no audio.
import datetime
import html
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CALLS_DIR = os.path.join(HERE, "calls")
SR = 24000
CLIP_PAD_S = (0.35, 0.45)  # a little before and after each line, so clips don't start mid-word


class CallRecorder:
    def __init__(self, caller="Grandma", record_audio=True):
        self.started = datetime.datetime.now()
        self.id = self.started.strftime("%Y-%m-%d_%H-%M")
        self.dir = os.path.join(CALLS_DIR, self.id)
        os.makedirs(os.path.join(self.dir, "clips"), exist_ok=True)
        self.caller, self.record_audio = caller, record_audio
        self.lines, self.prompts = [], []
        self.lock = threading.Lock()
        # audio: samples are counted as they arrive; Muse's clock restarts on every reconnect (new_session)
        self.samples, self.session_offset = 0, 0
        self.turn_start_ms, self.last_end_ms = 0, 0
        self.frames = queue.Queue()
        self.closing = False
        self.wav, self.writer = None, None
        if record_audio:
            self.wav = wave.open(os.path.join(self.dir, "call.wav"), "wb")
            self.wav.setnchannels(1)
            self.wav.setsampwidth(2)
            self.wav.setframerate(SR)
            self.writer = threading.Thread(target=self._write_audio, daemon=True)
            self.writer.start()

    # ---------- during the call ----------
    def add_frame(self, pcm16):
        """Called from the audio thread with each 80 ms frame sent to Muse; written to disk on another thread."""
        if self.closing:
            return
        self.samples += len(pcm16)
        if self.wav:
            self.frames.put(pcm16)

    def new_session(self):
        self.session_offset = self.samples
        self.turn_start_ms, self.last_end_ms = 0, 0

    def on_event(self, ev):
        if ev.get("type") == "speechStart":
            self.turn_start_ms = ev.get("audioProcessedMs") or 0
            self.last_end_ms = self.turn_start_ms

    def span(self, end_ms):
        """Where a line sits in the call audio (seconds): from the end of the previous piece of this utterance
        (or the start of the utterance) to Muse's position when the line's last word appeared."""
        end_ms = end_ms if end_ms is not None else self.last_end_ms
        start_ms = max(self.turn_start_ms, self.last_end_ms)
        self.last_end_ms = end_ms
        to_s = lambda ms: (self.session_offset + ms / 1000 * SR) / SR
        return to_s(start_ms), to_s(end_ms)

    def add_line(self, **line):
        with self.lock:
            line.setdefault("time", datetime.datetime.now().strftime("%H:%M:%S"))
            self.lines.append(line)

    def add_prompt(self, prompt):
        with self.lock:
            self.prompts.append({**prompt, "time": datetime.datetime.now().strftime("%H:%M:%S")})

    def _write_audio(self):
        while True:
            pcm = self.frames.get()
            if pcm is None:
                break
            self.wav.writeframes(pcm.tobytes())

    # ---------- after the call ----------
    def finish(self, progress_before, heard_before, progress, lexicon, lang):
        """Save clips, the story page and the dictionary. Returns the story page path (or None if nothing was said)."""
        self.closing = True  # live audio keeps arriving after Ctrl+C; stop taking it before draining the queue
        if self.wav:
            self.frames.put(None)
            self.writer.join(timeout=10)
            self.wav.close()
        with self.lock:
            lines = sorted(self.lines, key=lambda l: l["id"])
        if not lines:
            shutil.rmtree(self.dir, ignore_errors=True)  # nothing was said: don't leave an empty call behind
            return None
        if self.record_audio:
            self._cut_clips(lines)
        duration = (datetime.datetime.now() - self.started).seconds
        story = summarize(lines, self.caller)
        words = words_from_call(lines, progress_before, heard_before, progress, lexicon, lang)
        call = {"id": self.id, "caller": self.caller, "started": self.started.isoformat(timespec="minutes"),
                "duration_s": duration, "lines": lines, "prompts": self.prompts, "story": story, "words": words}
        json.dump(call, open(os.path.join(self.dir, "call.json"), "w"), ensure_ascii=False, indent=1)
        page = os.path.join(self.dir, "index.html")
        open(page, "w", encoding="utf-8").write(story_page(call))
        if story and story.get("message_te"):
            open(os.path.join(self.dir, "message_for_grandma.txt"), "w", encoding="utf-8").write(story["message_te"])
        update_dictionary(call, lexicon, lang, progress)
        return page

    def _cut_clips(self, lines):
        src = os.path.join(self.dir, "call.wav")
        for line in lines:
            if line.get("start_s") is None:
                continue
            start = max(0.0, line["start_s"] - CLIP_PAD_S[0])
            length = max(0.6, line["end_s"] - line["start_s"] + sum(CLIP_PAD_S))
            out = os.path.join(self.dir, "clips", f"{line['id']}.m4a")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", src,
                            "-c:a", "aac", "-b:a", "64k", out], check=False)
            if os.path.exists(out):
                line["clip"] = f"clips/{line['id']}.m4a"
        # Keep the whole call too, compressed (a 30-minute call is ~15 MB instead of ~90 MB).
        full = os.path.join(self.dir, "call.m4a")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-c:a", "aac", "-b:a", "64k", full], check=False)
        if os.path.exists(full):
            os.remove(src)


# ---------- the story (Muse Spark) ----------
def summarize(lines, caller):
    """Find the stories she told, a short summary in both languages, and questions for next time."""
    from muse import spark_json

    convo = "\n".join(f"[{l['id']}] {caller}: {l['english_full']}" + (f"  (Telugu: {l['telugu']})" if l["route"] != "english" else "")
                      for l in lines)
    system = (
        f"You turn a phone call between a Telugu-speaking grandparent ({caller}) and their US-raised grandchild into a "
        "keepsake for the family. Only the grandparent's side was transcribed. Keys: "
        '"title" (a warm title for this call, max 8 words), '
        '"summary" (2-3 sentences in English, written for the family), '
        '"summary_te" (the same summary in simple Telugu script, for the grandparent), '
        '"stories" (list of the stories or memories the grandparent told, each {"title", "summary", "line_ids": [ids]}; '
        "empty list if there were none; everyday news is not a story unless it is told as one), "
        '"highlights" (list of up to 3 short sweet or important moments, in English), '
        '"questions" (3 questions the grandchild could ask next call, each {"english", "telugu", "roman"}: simple spoken '
        "Telugu a beginner can say, and its pronunciation in English letters), "
        '"message_te" (a short, loving WhatsApp message in Telugu from the grandchild to the grandparent about this call).'
    )
    return spark_json(system, convo, model="muse-spark-1.3", effort="low", timeout=90)


def status(entry, times_total, progress, wid):
    """new (first time) / learning / known. Hearing a word once isn't knowing it, even though it's already kept in
    Telugu from its second hearing; call it known once it has come up at least twice (family words start known)."""
    if entry.get("start_known") or (times_total >= 2 and progress.known(wid)):
        return "known"
    return "new" if times_total <= 1 else "learning"


def words_from_call(lines, progress_before, heard_before, progress, lexicon, lang):
    """Word-list words heard on this call: how often, and new / learning / known."""
    heard = {}
    for line in lines:
        if line["route"] == "english":
            continue
        for e in lexicon.find(line["telugu"], lang):
            w = heard.setdefault(e["id"], {"id": e["id"], "times": 0, "first_line": line["id"]})
            w["times"] += 1
    by_id = {e["id"]: e for e in lexicon.entries.get(lang, [])}
    out = []
    for wid, w in heard.items():
        e = by_id.get(wid, {})
        english = e.get("translate_as") or e.get("note", "").split(",")[0] or (e.get("match_english") or [""])[0]
        total = heard_before.get(wid, 0) + w["times"]
        out.append({**w, "telugu": e.get("forms", [""])[0].lstrip("^").rstrip(",.!?"), "roman": (e.get("roman") or "").rstrip(","),
                    "english": english.rstrip(","), "note": "" if e.get("note", "") == english else e.get("note", ""),
                    "category": e.get("category", ""), "first_time": heard_before.get(wid, 0) == 0,
                    "status": status(e, total, progress, wid)})
    return sorted(out, key=lambda w: (-w["times"], w["id"]))


# ---------- pages ----------
ICONS = {"food": "🍛", "vehicle": "🛺", "place": "🛕", "clothing": "🥻", "festival": "🪔", "family": "👵", "idiom": "💬",
         "slang": "💬", "phrase": "💬", "culture": "🙏", "word": "🔤", "web": "🖼️"}

STYLE = """
:root { --bg:#fbf7f1; --card:#ffffff; --ink:#2a2420; --muted:#7a6f66; --accent:#c2410c; --soft:#fde8d7; --line:#eee4d8; }
@media (prefers-color-scheme: dark) { :root { --bg:#17130f; --card:#221c17; --ink:#f3ece4; --muted:#a8998b; --accent:#fb923c; --soft:#3a2a1d; --line:#352c24; } }
* { box-sizing:border-box; } body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 -apple-system, "Noto Sans Telugu", system-ui, sans-serif; }
main { max-width:860px; margin:0 auto; padding:28px 16px 60px; }
h1 { font-size:30px; line-height:1.2; margin:0 0 6px; } h2 { font-size:20px; margin:34px 0 12px; } h3 { margin:0 0 4px; font-size:18px; }
.meta { color:var(--muted); font-size:14px; } .te { font-family:"Noto Sans Telugu", sans-serif; }
.card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:16px 18px; margin:12px 0; }
.story { border-left:5px solid var(--accent); }
.line { display:flex; gap:12px; align-items:flex-start; padding:8px 0; border-top:1px solid var(--line); }
.line:first-of-type { border-top:0; } .line .text { flex:1; } .line .en { font-weight:600; } .line .orig { color:var(--muted); font-size:14px; }
audio { height:32px; width:220px; min-width:170px; max-width:100%; }
.pics { display:grid; grid-template-columns:repeat(auto-fill, minmax(150px, 1fr)); gap:12px; }
.pic img { width:100%; height:110px; object-fit:cover; border-radius:10px; display:block; } .pic b { display:block; margin-top:4px; } .pic span { color:var(--muted); font-size:13px; }
table { width:100%; border-collapse:collapse; } td, th { text-align:left; padding:8px 6px; border-top:1px solid var(--line); vertical-align:top; font-size:15px; }
th { color:var(--muted); font-weight:500; font-size:13px; } .new { background:var(--soft); color:var(--accent); border-radius:999px; padding:1px 8px; font-size:12px; font-weight:600; white-space:nowrap; }
.q { padding:10px 0; border-top:1px solid var(--line); } .q:first-child { border-top:0; } .q .roman { color:var(--accent); font-weight:600; }
textarea { width:100%; min-height:110px; border-radius:10px; border:1px solid var(--line); padding:10px; font:16px "Noto Sans Telugu", sans-serif; background:var(--bg); color:var(--ink); }
button { background:var(--accent); color:#fff; border:0; border-radius:10px; padding:8px 14px; font-size:15px; cursor:pointer; margin-top:8px; }
details summary { cursor:pointer; color:var(--muted); } a { color:var(--accent); }
@media (max-width:600px) { .line { flex-direction:column; } audio { width:100%; } h1 { font-size:24px; } }
"""


def _esc(s):
    return html.escape(str(s or ""))


def _image_src(card, depth):
    """Pictures live in images/ at the repo root; pages are one or two folders below it."""
    return "../" * depth + card["image"] if card and card.get("image") else ""


def _line_html(line, depth=2):
    clip = f'<audio controls preload="none" src="{_esc(line["clip"])}"></audio>' if line.get("clip") else ""
    orig = "" if line["route"] == "english" else f'<div class="orig te">{_esc(line["telugu"])}</div>'
    pic = line.get("picture")
    thumb = f' <img src="{_esc(_image_src(pic, depth))}" alt="" style="width:46px;height:34px;object-fit:cover;border-radius:6px;vertical-align:middle">' if pic else ""
    return f'<div class="line"><div class="text"><div class="en">{_esc(line["english"])}{thumb}</div>{orig}</div>{clip}</div>'


def story_page(call):
    story = call.get("story") or {}
    lines = {l["id"]: l for l in call["lines"]}
    when = datetime.datetime.fromisoformat(call["started"])
    mins = max(1, round(call["duration_s"] / 60))
    title = story.get("title") or f"Call with {call['caller']}"
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
             f"<title>{_esc(title)}</title><style>{STYLE}</style></head><body><main>",
             f"<div class='meta'>{_esc(call['caller'])} · {when:%A, %B %-d, %Y · %-I:%M %p} · {mins} min</div><h1>{_esc(title)}</h1>"]
    if story.get("summary"):
        parts.append(f"<p>{_esc(story['summary'])}</p>")
    if story.get("summary_te"):
        parts.append(f"<p class='te meta'>{_esc(story['summary_te'])}</p>")
    if story.get("highlights"):
        parts.append("<div class='card'><b>Moments</b><ul>" + "".join(f"<li>{_esc(h)}</li>" for h in story["highlights"]) + "</ul></div>")

    for s in story.get("stories") or []:
        ids = [i for i in s.get("line_ids", []) if i in lines]
        body = "".join(_line_html(lines[i]) for i in ids)
        parts.append(f"<h2>📖 {_esc(s.get('title'))}</h2><div class='card story'><p>{_esc(s.get('summary'))}</p>{body}</div>")

    pics = [l["picture"] for l in call["lines"] if l.get("picture")]
    if pics:
        parts.append("<h2>🖼️ Things that came up</h2><div class='pics'>" + "".join(
            f"<div class='pic'><img src='{_esc(_image_src(p, 2))}' alt=''><b>{_esc(p['name'])}</b><span>{_esc((p.get('description') or '')[:110])}</span></div>"
            for p in pics) + "</div>")

    words = call.get("words") or []
    if words:
        rows = "".join(
            f"<tr><td class='te'>{_esc(w['telugu'])}</td><td><b>{_esc(w['roman'])}</b></td><td>{_esc(w['english'])}"
            f"<div class='meta'>{_esc(w['note'])}</div></td><td>{w['times']}×</td>"
            f"<td>{_badge(w)}</td></tr>"
            for w in words)
        new = sum(1 for w in words if w["status"] == "new")
        known = sum(1 for w in words if w["status"] == "known")
        parts.append(f"<h2>🔤 Words from this call</h2><div class='meta'>{len(words)} words heard · {new} new · {known} known · "
                     f"<a href='../dictionary.html'>family dictionary</a></div>"
                     f"<div class='card'><table><tr><th>Telugu</th><th>Say it</th><th>Meaning</th><th>Heard</th><th></th></tr>{rows}</table></div>")

    asked = call.get("prompts") or []
    nxt = story.get("questions") or []
    if asked or nxt:
        qhtml = lambda q: (f"<div class='q'><div class='te'>{_esc(q.get('telugu'))}</div><div class='roman'>{_esc(q.get('roman'))}</div>"
                           f"<div class='meta'>{_esc(q.get('english'))}</div></div>")
        if asked:
            parts.append("<h2>💬 Questions suggested during the call</h2><div class='card'>" + "".join(qhtml(q) for q in asked) + "</div>")
        if nxt:
            parts.append("<h2>☎️ Ask next time</h2><div class='card'>" + "".join(qhtml(q) for q in nxt) + "</div>")

    if story.get("message_te"):
        parts.append("<h2>💌 Send to " + _esc(call["caller"]) + "</h2><div class='card'><div class='meta'>Copy this into WhatsApp so she keeps this call too.</div>"
                     f"<textarea id='msg' class='te'>{_esc(story['message_te'])}</textarea>"
                     "<button onclick=\"navigator.clipboard.writeText(document.getElementById('msg').value);this.textContent='Copied ✓'\">Copy message</button></div>")

    parts.append("<h2>🗒️ The whole call</h2><details><summary>Show every line</summary><div class='card'>"
                 + "".join(_line_html(l) for l in call["lines"]) + "</div></details>")
    if os.path.exists(os.path.join(CALLS_DIR, call["id"], "call.m4a")):
        parts.append("<p class='meta'>Full recording of her side: <audio controls preload='none' src='call.m4a'></audio></p>")
    parts.append("<p class='meta'>Pictures from Wikipedia. Everything on this page stays on this computer.</p></main></body></html>")
    return "".join(parts)


def update_dictionary(call, lexicon, lang, progress):
    """Add this call's words to the family dictionary (calls/family_dictionary.json) and rebuild calls/dictionary.html."""
    path = os.path.join(CALLS_DIR, "family_dictionary.json")
    book = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    lines = {l["id"]: l for l in call["lines"]}
    for w in call.get("words") or []:
        entry = book.setdefault(w["id"], {"first_heard": call["started"][:10], "calls": 0, "times": 0})
        entry.update({k: w[k] for k in ("telugu", "roman", "english", "note", "category")})
        entry["calls"] += 1
        entry["times"] += w["times"]
        line = lines.get(w["first_line"], {})
        if line.get("clip") and not entry.get("clip"):  # her voice saying it, from the first call it came up in
            entry.update({"clip": f"{call['id']}/{line['clip']}", "example_te": line.get("telugu"), "example_en": line.get("english")})
    by_id = {e["id"]: e for e in lexicon.entries.get(lang, [])}
    for wid, entry in book.items():
        entry["status"] = status(by_id.get(wid, {}), entry["times"], progress, wid)
    json.dump(book, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    order = {"known": 0, "learning": 1, "new": 2}
    rows = sorted(book.items(), key=lambda kv: (order[kv[1]["status"]], -kv[1]["times"], kv[0]))
    known = sum(1 for _, e in rows if e["status"] == "known")
    body = "".join(
        f"<tr><td>{ICONS.get(e.get('category'), '🔖')}</td><td class='te'>{_esc(e.get('telugu'))}</td><td><b>{_esc(e.get('roman'))}</b></td>"
        f"<td>{_esc(e.get('english'))}<div class='meta'>{_esc(e.get('note'))}</div>"
        + (f"<div class='meta te'>“{_esc(e.get('example_te'))}” — {_esc(e.get('example_en'))}</div>" if e.get("example_te") else "")
        + f"</td><td>{e['times']}× · {e['calls']} call{'s' if e['calls'] != 1 else ''}<div class='meta'>since {_short_date(e.get('first_heard'))}</div></td>"
        f"<td>{_badge(e)}</td>"
        f"<td>{_audio(e.get('clip'))}</td></tr>"
        for _, e in rows)
    calls = sorted((d for d in os.listdir(CALLS_DIR) if os.path.exists(os.path.join(CALLS_DIR, d, "index.html"))), reverse=True)
    links = "".join(f"<li><a href='{d}/index.html'>{_esc(_call_title(d))}</a></li>" for d in calls)
    page = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>Family Dictionary</title><style>{STYLE}</style></head><body><main>"
            f"<div class='meta'>Every Telugu word heard on calls, in her voice</div><h1>Our family dictionary</h1>"
            f"<p>{len(rows)} words · {known} known · {len(calls)} call{'s' if len(calls) != 1 else ''}</p>"
            f"<div class='card'><table><tr><th></th><th>Telugu</th><th>Say it</th><th>Meaning</th><th>Heard</th><th></th><th>Her voice</th></tr>{body}</table></div>"
            f"<h2>📚 Calls</h2><div class='card'><ul>{links}</ul></div></main></body></html>")
    open(os.path.join(CALLS_DIR, "dictionary.html"), "w", encoding="utf-8").write(page)


def _badge(w):
    return {"known": "✓ known", "learning": "learning", "new": "<span class=new>🆕 new</span>"}.get(w.get("status"), "")


def _short_date(iso):
    try:
        return datetime.date.fromisoformat(iso).strftime("%b %-d")
    except (TypeError, ValueError):
        return iso or ""


def _audio(src):
    return f"<audio controls preload='none' src='{_esc(src)}'></audio>" if src else ""


def _call_title(call_id):
    try:
        c = json.load(open(os.path.join(CALLS_DIR, call_id, "call.json"), encoding="utf-8"))
        return f"{c['started'][:10]} — {(c.get('story') or {}).get('title') or 'Call with ' + c['caller']}"
    except (OSError, ValueError, KeyError):
        return call_id

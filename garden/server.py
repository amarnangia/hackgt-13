"""Serves the Weave app and its JSON API (for the web app, the iPhone app and widget, and the overlay).

GET  /              redirects to /app
GET  /app           the Weave connection app (live call + demo)
GET  /api/garden    snapshot JSON
GET  /api/progress   which words the translator keeps in Telugu (from the team's progress.json)
GET  /api/calls      the calls saved by the story keeper (calls/*/call.json), newest first
GET  /api/live       the live call for phones: subtitles.py's messages as Server-Sent Events (relay.py)
POST /api/forget     {"id"}: "Didn't know it" from a phone, passed on to subtitles.py
GET  /images/..., /lexicon.json, /samples/call_script.json, /calls/...   the team's files, read only
POST /api/heard     {"phrase", "english"?, "category"?, "note"?, "roman"?}  -> {"mode"}
POST /api/asked     {"phrase"}
GET  /api/people    the family, for "who are you?": [{id, name, voice}] (voice: has a personalized voice)
POST /api/people    {"name"}: add someone
POST /api/voice?name=Saanvi&consent=1   body: ~1 min recording (m4a) -> ElevenLabs voice clone (eleven.py)
POST /api/voice/remove  {"name"}: delete their voice at ElevenLabs
"""
import json, mimetypes, os, queue, re, socket, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from lexicon import Lexicon  # noqa: E402  (the translator's own word list and progress rules, so the numbers match)
from progress import Progress  # noqa: E402
import origins  # noqa: E402  (who may read the call: our own pages only)
import eleven  # noqa: E402  (personalized voices)
import people  # noqa: E402  (the family: who's who, who has a voice)
import sync  # noqa: E402  (Firestore; quietly off without FIREBASE_KEY)
# Team files the app reads. Anything else in the repo stays private.
# calls/ is the story keeper's output (story pages, family dictionary, voice clips); it stays on this Mac.
# (not calls/people.json: /api/people serves it without the voice ids)
CALLS = re.compile(r"^/calls/(?!people\.json$)[\w-]+(?:/[\w-]+){0,2}\.(?:html|m4a|json)$")
MAX_VOICE_BYTES = 25 * 2**20  # a few minutes of m4a; ElevenLabs needs ~1 min
# Where the story keeper saves calls (same setting as calls.py; tests point both at a temp folder)
CALLS_ROOT = Path(os.environ.get("HACKGT_CALLS_DIR") or ROOT / "calls")
SHARED = re.compile(r"^/(images/(?:cache/)?[\w.-]+\.(?:jpg|jpeg|png|webp|json)|lexicon\.json|samples/call_script\.json)$")


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def progress():
    """Real learning numbers from the translator's progress.json, or None before the first call."""
    try:
        saved = json.load(open(ROOT / "progress.json", encoding="utf-8"))
        lexicon = Lexicon()
        tracker = Progress(lexicon, "te", path=str(ROOT / "progress.json"))
    except (OSError, ValueError):
        return None
    heard = saved.get("heard", {})
    entries = {e["id"]: e for items in lexicon.entries.values() for e in items}
    words = []
    for key, n in sorted(heard.items(), key=lambda kv: -kv[1]):
        e = entries.get(key)
        if not e or n <= 0:
            continue
        known = tracker.known(key)  # exactly what the translator does: kept in Telugu or not
        words.append({"id": key, "telugu": e["forms"][0].strip(" ,."), "roman": e.get("roman") or key.replace("_", " "),
                      "english": e.get("translate_as") or e.get("note", ""), "heard": n, "known": known,
                      "p": round(tracker.probability(key), 2)})
    return {"met": len(words), "known": sum(w["known"] for w in words), "hearings": sum(w["heard"] for w in words),
            "keep_at": tracker.keep_at, "words": words}


STAGE_OF = {"new": "seed", "learning": "sprout", "known": "bloom"}  # progress.py's status -> the app's plant stages


def learning(garden):
    """The translator's learning model (progress.json), which decides which words stay in Telugu, so every screen takes
    new / learning / known from it; plus, per word, how often it has come up (the most any of our records counted: the
    model, the family dictionary, the garden), so the plant and the Words tab use the same count. (None, {}, {}) before
    the first call."""
    if not (ROOT / "progress.json").exists():
        return None, {}, {}
    try:
        lexicon = Lexicon()
        tracker = Progress(lexicon, "te", path=str(ROOT / "progress.json"))
    except (OSError, ValueError):
        return None, {}, {}
    from .store import _key  # how the garden spells a phrase (its first Telugu form, see store.from_lexicon)
    by_phrase = {_key(e["forms"][0].strip(" ,.^")): e["id"] for e in lexicon.entries.get("te", []) if e.get("forms")}
    times = dict(tracker.heard)
    try:
        for wid, entry in json.load(open(CALLS_ROOT / "family_dictionary.json", encoding="utf-8")).items():
            times[wid] = max(times.get(wid, 0), entry.get("times") or 0)
    except (OSError, ValueError):
        pass
    for p in garden.snapshot()["plants"]:
        wid = by_phrase.get(p["phrase"])
        if wid:
            times[wid] = max(times.get(wid, 0), p["heard"])
    return tracker, by_phrase, times


def garden_snapshot(garden):
    """The garden, with each word's stage from the learning model (not the garden's own hearing count)."""
    tracker, by_phrase, times = learning(garden)
    if tracker is None:
        return garden.snapshot()

    def stage_for(plant):
        wid = by_phrase.get(plant["phrase"])
        if wid is None or wid not in tracker.entries:
            return None  # not in the word list: the hearing count decides
        return STAGE_OF[tracker.status(wid, times.get(wid, 0))]
    return garden.snapshot(stage_for=stage_for)


def family_dictionary(garden):
    """calls/family_dictionary.json with each word's status worked out now, from the learning model, rather than as it
    was when the last call ended (a "Didn't know it" or a few days of forgetting since then change it)."""
    book = json.load(open(CALLS_ROOT / "family_dictionary.json", encoding="utf-8"))
    tracker, _, times = learning(garden)
    if tracker is not None:
        for wid, entry in book.items():
            if wid in tracker.entries:
                entry["status"] = tracker.status(wid, times.get(wid, 0))
    return book


def calls():
    """The calls the story keeper saved, newest first, with what the home screen and call list need."""
    out = []
    for f in sorted(CALLS_ROOT.glob("*/call.json"), reverse=True):
        try:
            c = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        story = c.get("story") or {}
        words = c.get("words") or []
        out.append({
            "id": c["id"], "caller": c.get("caller", "Grandma"), "started": c.get("started"),
            "duration_s": c.get("duration_s", 0), "title": story.get("title") or f"Call with {c.get('caller', 'Grandma')}",
            "summary": story.get("summary", ""), "stories": [s.get("title") for s in story.get("stories") or []],
            "questions": story.get("questions") or [],   # what to ask next call (Muse Spark, from this call's stories)
            "message_te": story.get("message_te") or None,   # a WhatsApp message in Telugu to send her (the app's Message tab)
            "message_en": story.get("message_en") or None,   # ...and what it says, in English
            "has_audio": (f.parent / "call.m4a").exists(),
            "lines": len(c.get("lines") or []), "words": len(words),
            "new_words": sum(1 for w in words if w.get("status") == "new"),
            "pictures": [p["image"] for p in (l.get("picture") for l in c.get("lines") or []) if p and p.get("image")][:6],
            "page": f"/calls/{c['id']}/index.html" if (f.parent / "index.html").exists() else None,
        })
    return out


def family():
    """Everyone for "who are you?": the people added in the app, plus whoever the saved calls were between."""
    everyone = {pid: {"id": pid, "name": p["name"], "voice": bool(p.get("voice_id"))} for pid, p in people.load().items()}
    for f in CALLS_ROOT.glob("*/call.json"):
        try:
            c = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for name in (c.get("caller"), c.get("you")):
            if name and name not in ("You", "Grandma") and people.person_id(name) not in everyone:
                everyone[people.person_id(name)] = {"id": people.person_id(name), "name": name, "voice": False}
    return sorted(everyone.values(), key=lambda p: p["name"].lower())


def make_handler(garden):
    from .relay import Relay
    relay = Relay()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json", extra=None):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self._allow_origin()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _allow_origin(self):
            """Only our own pages may read answers from another origin (origins.py); other websites can't."""
            origin = self.headers.get("Origin")
            if origin and origins.allowed(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def do_OPTIONS(self):
            self.send_response(204)
            self._allow_origin()
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                self.send_response(302)
                self.send_header("Location", "/app")
                self.end_headers()
            elif path in ("/app", "/app/"):
                self._send(200, (HERE / "web" / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/garden":
                self._send(200, garden_snapshot(garden))
            elif path == "/calls/family_dictionary.json" and (CALLS_ROOT / "family_dictionary.json").is_file():
                self._send(200, json.dumps(family_dictionary(garden), ensure_ascii=False).encode(), "application/json; charset=utf-8")
            elif path == "/api/progress":
                self._send(200, progress() or {"met": 0})
            elif path == "/api/calls":
                self._send(200, calls())
            elif path == "/api/people":
                self._send(200, family())
            elif path == "/api/live":
                self._live()
            elif path == "/api/live/status":
                self._send(200, relay.status())
            elif (SHARED.match(path) and (ROOT / path[1:]).is_file()) or (CALLS.match(path) and (CALLS_ROOT / path[len("/calls/"):]).is_file()):
                file = ROOT / path[1:] if SHARED.match(path) else CALLS_ROOT / path[len("/calls/"):]
                ctype = "audio/mp4" if path.endswith(".m4a") else mimetypes.guess_type(path)[0] or "application/octet-stream"
                if ctype == "text/html":
                    ctype = "text/html; charset=utf-8"
                data = file.read_bytes()
                rng = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
                if rng and path.endswith(".m4a"):  # Safari and iOS only play audio from servers that answer byte ranges
                    start = int(rng[1] or 0)
                    end = min(int(rng[2]) if rng[2] else len(data) - 1, len(data) - 1)
                    return self._send(206, data[start:end + 1], ctype, extra={"Content-Range": f"bytes {start}-{end}/{len(data)}", "Accept-Ranges": "bytes"})
                self._send(200, data, ctype + ("; charset=utf-8" if ctype.endswith("json") else ""),
                           extra={"Accept-Ranges": "bytes"} if path.endswith(".m4a") else None)
            else:
                self._send(404, {"error": "not found"})

        def _live(self):
            q = relay.subscribe()
            self.send_response(200)
            for k, v in (("Content-Type", "text/event-stream"), ("Cache-Control", "no-cache"), ("Connection", "keep-alive")):
                self.send_header(k, v)
            self._allow_origin()
            self.end_headers()
            try:
                self.wfile.write(("data: " + json.dumps({"type": "status", **relay.status()}) + "\n\n").encode())
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=15)
                    except queue.Empty:
                        self.wfile.write(b": still here\n\n")  # keeps phones and proxies from closing an idle stream
                    else:
                        self.wfile.write(("data: " + json.dumps(msg, ensure_ascii=False) + "\n\n").encode())
                    self.wfile.flush()
            except OSError:
                pass
            finally:
                relay.unsubscribe(q)

        def do_POST(self):
            if not origins.allowed(self.headers.get("Origin")):  # another website posting to this Mac
                return self._send(403, {"error": "only Roots' own pages can do this"})
            if self.path == "/api/forget":
                try:
                    word = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")["id"]
                except (ValueError, KeyError):
                    return self._send(400, {"error": "expected JSON with an 'id'"})
                return self._send(200, {"ok": relay.forget(word)})
            if self.path.startswith("/api/voice"):
                return self._voice()
            if self.path == "/api/people":
                try:
                    name = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")["name"].strip()
                except (ValueError, KeyError, AttributeError):
                    return self._send(400, {"error": "expected JSON with a 'name'"})
                if not name or len(name) > 40:
                    return self._send(400, {"error": "a name, please (up to 40 letters)"})
                people.add(name)
                threading.Thread(target=sync.people, daemon=True).start()  # the other laptops, through Firestore
                return self._send(200, family())
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
                phrase = body["phrase"]
            except (ValueError, KeyError):
                return self._send(400, {"error": "expected JSON with a 'phrase'"})
            if self.path == "/api/heard":
                self._send(200, {"mode": garden.heard(phrase, body.get("english"), body.get("category"), body.get("note"), body.get("roman"))})
            elif self.path == "/api/asked":
                garden.asked(phrase)
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})

        def _voice(self):
            """Record a personalized voice (the phone uploads the recording) or remove one."""
            from urllib.parse import parse_qs, urlsplit
            url = urlsplit(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            size = int(self.headers.get("Content-Length", 0))
            if size > MAX_VOICE_BYTES:
                return self._send(413, {"error": "recording too long"})
            body = self.rfile.read(size)
            if not eleven.api_key():
                return self._send(503, {"error": "the Mac has no ELEVENLABS_API_KEY in .env"})
            try:
                if url.path == "/api/voice/remove":
                    try:
                        name = json.loads(body or b"{}")["name"]
                    except (ValueError, KeyError):
                        return self._send(400, {"error": "expected JSON with a 'name'"})
                    result = (200, {"removed": eleven.remove(name)})
                elif url.path == "/api/voice":
                    name = q.get("name", "").strip()
                    if not name or q.get("consent") != "1":
                        return self._send(400, {"error": "needs ?name= and consent=1 (they agreed to have their voice cloned)"})
                    if size < 50_000:
                        return self._send(400, {"error": "recording too short"})
                    pid, record = eleven.clone(name, body, content_type=self.headers.get("Content-Type", "audio/mp4"),
                                               consent_by=name)
                    print(f"Personalized voice for {name}: {record['voice_id']}", flush=True)
                    result = (200, {"id": pid, "name": name, "voice": True})
                else:
                    return self._send(404, {"error": "not found"})
            except Exception as e:  # ElevenLabs refused it (bad key, out of voice slots, unreadable audio) or offline
                return self._send(502, {"error": f"ElevenLabs: {type(e).__name__}: {str(e)[:200]}"})
            threading.Thread(target=sync.people, daemon=True).start()  # the other laptops, through Firestore
            self._send(*result)

        def log_message(self, *args):
            pass

    return Handler


def serve(garden, port=8770, lan=False):  # 8765 is subtitles.py's overlay
    # Only this laptop by default: on shared Wi-Fi (a hackathon, a cafe) anyone could otherwise open the saved calls,
    # her voice clips and the live call. --lan opens it to the network for the iPhone app, on a network you trust.
    server = ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", port), make_handler(garden))
    print(f"Roots:             http://localhost:{port}/app")
    if lan:
        print(f"phone widget URL:  http://{lan_ip()}:{port}   (open to everyone on this Wi-Fi until you stop it)")
    else:
        print("(this laptop only; python -m garden --lan to let your iPhone connect over Wi-Fi)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")

"""Serves the garden dashboard and a JSON API (for the dashboard, the phone widget and the overlay).

GET  /              dashboard
GET  /app           the Weave connection app (live call + demo)
GET  /api/garden    snapshot JSON
GET  /api/progress   which words the translator keeps in Telugu (from the team's progress.json)
GET  /images/..., /lexicon.json, /samples/call_script.json, /calls/...   the team's files, read only
POST /api/heard     {"phrase", "english"?, "category"?, "note"?, "roman"?}  -> {"mode"}
POST /api/asked     {"phrase"}
"""
import json, mimetypes, re, socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# Team files the app reads. Anything else in the repo stays private.
# calls/ is the story keeper's output (story pages, family dictionary, voice clips); it stays on this Mac.
CALLS = re.compile(r"^/calls/[\w-]+(?:/[\w-]+){0,2}\.(?:html|m4a|json)$")
LEARN_AFTER = 3  # progress.py: a word is kept in Telugu once it has come up this many times
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
        lex = json.load(open(ROOT / "lexicon.json", encoding="utf-8"))
    except (OSError, ValueError):
        return None
    heard = saved.get("heard", {})
    entries = {e["id"]: e for lang, items in lex.items() if not lang.startswith("_") for e in items}
    words = []
    for key, n in sorted(heard.items(), key=lambda kv: -kv[1]):
        e = entries.get(key)
        if not e or n <= 0:
            continue
        known = n >= LEARN_AFTER  # progress.py resets the count to 0 when you say you forgot it
        words.append({"id": key, "telugu": e["forms"][0].strip(" ,."), "roman": e.get("roman") or key.replace("_", " "),
                      "english": e.get("translate_as") or e.get("note", ""), "heard": n, "known": known})
    return {"met": len(words), "known": sum(w["known"] for w in words), "hearings": sum(w["heard"] for w in words),
            "learn_after": LEARN_AFTER, "words": words}


def make_handler(garden):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                self._send(200, (HERE / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
            elif path in ("/app", "/app/"):
                self._send(200, (HERE / "web" / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/garden":
                self._send(200, garden.snapshot())
            elif path == "/api/progress":
                self._send(200, progress() or {"met": 0})
            elif (SHARED.match(path) or CALLS.match(path)) and (ROOT / path[1:]).is_file():
                ctype = "audio/mp4" if path.endswith(".m4a") else mimetypes.guess_type(path)[0] or "application/octet-stream"
                if ctype == "text/html":
                    ctype = "text/html; charset=utf-8"
                self._send(200, (ROOT / path[1:]).read_bytes(), ctype + ("; charset=utf-8" if ctype.endswith("json") else ""))
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
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

        def log_message(self, *args):
            pass

    return Handler


def serve(garden, port=8770):  # 8765 is subtitles.py's overlay
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(garden))
    print(f"garden dashboard:  http://localhost:{port}")
    print(f"phone widget URL:  http://{lan_ip()}:{port}   (phone must be on the same Wi-Fi)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")

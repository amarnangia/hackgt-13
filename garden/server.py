"""Serves the garden dashboard and a JSON API (for the dashboard, the phone widget and the overlay).

GET  /              dashboard
GET  /api/garden    snapshot JSON
POST /api/heard     {"phrase", "english"?, "category"?, "note"?, "roman"?}  -> {"mode"}
POST /api/asked     {"phrase"}
"""
import json, socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


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
            elif path == "/api/garden":
                self._send(200, garden.snapshot())
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

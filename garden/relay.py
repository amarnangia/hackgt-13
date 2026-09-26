"""Passes the live call from subtitles.py to phones.

subtitles.py serves its WebSocket on this Mac only (localhost:8765, and :8767 with --outgoing). The Weave server
connects to it as a client and re-sends every message to phones as Server-Sent Events on /api/live, so the iPhone
app can show the live call over Wi-Fi without changing subtitles.py. Standard library only.
"""
import base64, json, os, queue, socket, struct, threading, time

PORTS = {"them": 8765, "you": 8767}   # the caller's side, and --outgoing (your side)


class Relay:
    def __init__(self, host="localhost"):
        self.host = host
        self.subscribers = set()
        self.lock = threading.Lock()
        self.socks = {}
        self.connected = {side: False for side in PORTS}
        for side in PORTS:
            threading.Thread(target=self._run, args=(side,), daemon=True).start()

    # --- phones ---

    def subscribe(self):
        q = queue.Queue(maxsize=500)
        with self.lock:
            self.subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            self.subscribers.discard(q)

    def _publish(self, msg):
        with self.lock:
            subs = list(self.subscribers)
        for q in subs:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass

    def status(self):
        return {"live": self.connected["them"], "outgoing": self.connected["you"]}

    def forget(self, word_id):
        """The phone's "Didn't know it": same message overlay.html sends."""
        s = self.socks.get("them")
        if s:
            try:
                _send_frame(s, json.dumps({"type": "forget", "id": word_id}))
                return True
            except OSError:
                pass
        return False

    # --- subtitles.py ---

    def _run(self, side):
        while True:
            try:
                s = _connect(self.host, PORTS[side])
            except OSError:
                time.sleep(2)
                continue
            self.socks[side], self.connected[side] = s, True
            self._publish({"side": side, "type": "connected"})
            try:
                for text in _frames(s):
                    try:
                        msg = json.loads(text)
                    except ValueError:
                        continue
                    self._publish({"side": side, **msg})
            except OSError:
                pass
            self.socks.pop(side, None)
            self.connected[side] = False
            self._publish({"side": side, "type": "disconnected"})
            time.sleep(1)


def _connect(host, port):
    s = socket.create_connection((host, port), timeout=3)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = s.recv(1024)
        if not chunk:
            raise OSError("closed during handshake")
        head += chunk
    if b" 101 " not in head.split(b"\r\n", 1)[0]:
        raise OSError("not a websocket")
    s.settimeout(None)
    return s


def _recv_exact(s, n):
    buf = b""
    while len(buf) < n:
        chunk = s.recv(n - len(buf))
        if not chunk:
            raise OSError("closed")
        buf += chunk
    return buf


def _frames(s):
    """Text messages from the server (unmasked frames), joining fragments; answers pings."""
    parts = []
    while True:
        b0, b1 = _recv_exact(s, 2)
        op, n = b0 & 0x0F, b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", _recv_exact(s, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", _recv_exact(s, 8))[0]
        mask = _recv_exact(s, 4) if b1 & 0x80 else None
        data = _recv_exact(s, n)
        if mask:
            data = bytes(c ^ mask[i % 4] for i, c in enumerate(data))
        if op == 8:
            raise OSError("closed")
        if op == 9:
            _send_frame(s, data, opcode=10)
            continue
        if op in (0, 1):
            parts.append(data)
            if b0 & 0x80:
                yield b"".join(parts).decode("utf-8", "replace")
                parts = []


def _send_frame(s, payload, opcode=1):
    """Client frames must be masked."""
    data = payload.encode() if isinstance(payload, str) else payload
    mask = os.urandom(4)
    n = len(data)
    head = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
    s.sendall(head + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(data)))

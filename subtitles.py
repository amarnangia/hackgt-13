# Steps 2-3 of plan.md: live call audio -> Muse Voice Transcribe -> Muse Spark translation -> overlay.
#   python subtitles.py --out "MacBook Air Speakers"         # live call (see Audio setup in plan.md)
#   python subtitles.py --file samples/telugu_grandma.wav    # no call needed, replays a recording
# Then open http://localhost:8765 for the subtitle overlay.
# The offline Whisper version of this file is in git history (commit d111471).
import argparse
import asyncio
import http
import json
import re
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from websockets.datastructures import Headers
from websockets.http11 import Response

from muse import Translator, transcribe

PORT = 8765
CHUNK_MS = 80
SENTENCE_END = re.compile(r"[.?!।]+")
CLAUSE_END = re.compile(r"[,;]")
MIN_CLAUSE_WORDS = 5  # Muse often joins sentences with commas; cut there once a clause is long enough to translate well

clients = set()


def broadcast(msg):
    data = json.dumps(msg, ensure_ascii=False)
    for c in list(clients):
        try:
            c.send(data)
        except Exception:
            clients.discard(c)


def ws_handler(conn):
    clients.add(conn)
    try:
        for _ in conn:
            pass
    finally:
        clients.discard(conn)


def serve_overlay(conn, request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None
    with open("overlay.html", "rb") as f:
        body = f.read()
    # Build the response directly: conn.respond() adds text/plain headers, and setting them again
    # duplicates them, which Chrome rejects ("localhost sent an invalid response").
    return Response(http.HTTPStatus.OK, "OK", Headers([
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Connection", "close"),
    ]), body)


class Captioner:
    """Turns Muse's live partials into sentences and translates each one as soon as it ends.

    Translation runs on a single worker thread so sentences finish in order and each one gets the
    previous lines as context.
    """

    def __init__(self, lang):
        self.translate = Translator(lang)
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.pool.submit(self.translate.warm_up)  # the first request pays for TLS setup (~3 s)
        self.next_id = 0
        self.partial = ""  # latest cumulative transcript for the current turn
        self.done = 0      # how many characters of it have been sent for translation

    def on_event(self, ev):
        kind = ev.get("type")
        if kind == "speechStart":
            self.partial, self.done = "", 0
            broadcast({"type": "speaking"})
        elif kind == "transcript" and not ev.get("final"):
            self.partial = ev["transcript"]
            self._cut(final=False)
            broadcast({"type": "partial", "text": self.partial[self.done:].strip()})
        elif kind == "speechEnd":
            self._cut(final=True)
            broadcast({"type": "partial", "text": ""})

    def _cut(self, final):
        rest = self.partial[self.done:]
        ends = sorted({m.end() for m in SENTENCE_END.finditer(rest)} | {m.end() for m in CLAUSE_END.finditer(rest)})
        if final and rest.strip():
            ends.append(len(rest))
        start = 0
        for end in ends:
            piece = rest[start:end].strip()
            is_sentence = bool(SENTENCE_END.search(piece[-1:])) or end == len(rest) and final
            if not piece or (not is_sentence and len(piece.split()) < MIN_CLAUSE_WORDS):
                continue  # short clause: keep it and send it together with what follows
            self._submit(piece)
            start = end
        self.done += start

    def _submit(self, sentence):
        self.next_id += 1
        seg_id, ended_at = self.next_id, time.monotonic()
        broadcast({"type": "original", "id": seg_id, "text": sentence})

        def work():
            try:
                english = self.translate(sentence)
            except Exception as e:
                english = f"(translation failed: {type(e).__name__})"
            broadcast({"type": "english", "id": seg_id, "text": english})
            print(f"[+{time.monotonic() - ended_at:.1f}s] {sentence}  ->  {english}", flush=True)

        self.pool.submit(work)


async def file_audio(path, audio_q):
    """Send a recording at real-time pace, like a live call (Muse rejects audio sent much faster)."""
    with wave.open(path) as w:
        rate, pcm = w.getframerate(), w.readframes(w.getnframes())
    assert rate in (16000, 24000), "file must be 16 or 24 kHz mono 16-bit wav"
    pcm += b"\0" * (rate * 2 * 2)  # 2 s of trailing silence lets Muse close the last utterance
    size = rate * 2 * CHUNK_MS // 1000
    start = time.monotonic()
    for i in range(0, len(pcm), size):
        await audio_q.put(pcm[i:i + size])
        await asyncio.sleep(max(0, start + (i + size) / (rate * 2) - time.monotonic()))
    await audio_q.put(None)


def start_live_audio(args, loop, target):
    """Pass call audio through to the speakers (audio_loop.py) and copy it to Muse as 24 kHz 16-bit PCM.

    `target["q"]` is the queue of the current Muse session; it is swapped on reconnect.
    """
    import sounddevice as sd
    from audio_loop import AudioLoop, find_device

    in_dev = find_device(args.inp, "input")
    out_dev = find_device(args.out, "output") if args.out else sd.default.device[1]
    buf = []

    def on_audio(mono48k):
        # 48 kHz -> 24 kHz by averaging pairs; batch 10 ms blocks into 80 ms frames.
        buf.append((mono48k.reshape(-1, 2).mean(axis=1) * 32767).clip(-32768, 32767).astype(np.int16))
        if len(buf) * 10 >= CHUNK_MS:
            frame = np.concatenate(buf).tobytes()
            buf.clear()
            loop.call_soon_threadsafe(target["q"].put_nowait, frame)

    audio = AudioLoop(in_dev, out_dev, on_audio=on_audio)
    threading.Thread(target=audio.run, daemon=True).start()


async def run(args):
    captioner = Captioner(args.lang)
    loop = asyncio.get_running_loop()
    target = {"q": asyncio.Queue()}
    if not args.file:
        start_live_audio(args, loop, target)
    while True:
        audio_q = target["q"] = asyncio.Queue()
        if args.file:
            encoding = "PCM_24KHZ" if wave.open(args.file).getframerate() == 24000 else "PCM_16KHZ"
            feeder = asyncio.create_task(file_audio(args.file, audio_q))
        else:
            encoding = "PCM_24KHZ"
        try:
            async for ev in transcribe(audio_q, args.lang, encoding):
                captioner.on_event(ev)
        except Exception as e:
            if args.file:
                raise
            print(f"Muse connection dropped ({e}); reconnecting...", flush=True)
            await asyncio.sleep(1)
            continue
        if args.file:
            await feeder
            await loop.run_in_executor(None, lambda: captioner.pool.shutdown(wait=True))  # let the last translations finish
            await asyncio.sleep(0.5)
            return


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lang", default="te", help="language code: te (Telugu), hi (Hindi), ta, kn, ml, bn, mr")
    p.add_argument("--file", help="replay a 16/24 kHz mono wav instead of listening to the call")
    p.add_argument("--in", dest="inp", default="BlackHole")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    from websockets.sync.server import serve
    server = serve(ws_handler, "localhost", PORT, process_request=serve_overlay)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Overlay: http://localhost:{PORT}", flush=True)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()

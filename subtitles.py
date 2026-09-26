# Steps 2-3 of plan.md: live call audio -> speech segments -> Telugu text + English translation -> overlay.
#   python subtitles.py --out "MacBook Air Speakers"         # live call (see Audio setup in plan.md)
#   python subtitles.py --file samples/telugu_grandma.wav    # no call needed, replays a recording
# Then open http://localhost:8765 for the subtitle overlay.
import argparse
import http
import json
import queue
import threading
import time
import wave

import mlx_whisper
import numpy as np
import torch
from silero_vad import VADIterator, load_silero_vad
from websockets.sync.server import serve

SR = 16000
VAD_CHUNK = 512  # silero needs 512 samples at 16 kHz
MAX_SEGMENT_S = 8  # cut long monologues so subtitles keep flowing
TRANSCRIBE_MODEL = "mlx-community/whisper-large-v3-turbo"  # fast, but can't translate
TRANSLATE_MODEL = "mlx-community/whisper-large-v3-mlx"     # fallback translator when Claude isn't configured
CLAUDE_MODEL = "claude-opus-5"
MERGE_BELOW_S = 1.5  # phrases shorter than this wait for the next one...
MERGE_WAIT_S = 1.0   # ...for up to this long, so "nanna," isn't translated on its own
PORT = 8765

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
        resp = conn.respond(http.HTTPStatus.OK, "")
        resp.body = f.read()
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        resp.headers["Content-Length"] = str(len(resp.body))
        return resp


class Segmenter:
    """Feeds 16 kHz audio through silero VAD and emits one numpy array per spoken phrase."""

    def __init__(self, out_q):
        self.vad = VADIterator(load_silero_vad(), sampling_rate=SR, min_silence_duration_ms=500, speech_pad_ms=200)
        self.out_q = out_q
        self.pending = np.zeros(0, dtype=np.float32)
        self.speech = None  # list of chunks while someone is talking
        self.holding = 0    # chunks of silence waited after a too-short phrase ended

    def feed(self, audio16k):
        self.pending = np.concatenate([self.pending, audio16k])
        while len(self.pending) >= VAD_CHUNK:
            chunk, self.pending = self.pending[:VAD_CHUNK], self.pending[VAD_CHUNK:]
            ev = self.vad(torch.from_numpy(chunk))
            if ev and "start" in ev:
                if self.speech is None:
                    self.speech = []
                    broadcast({"type": "speaking"})
                self.holding = 0  # speech resumed, so a held fragment joins this phrase
            if self.speech is None:
                continue
            self.speech.append(chunk)
            n = len(self.speech) * VAD_CHUNK
            if self.holding:
                self.holding += 1
                if self.holding * VAD_CHUNK >= MERGE_WAIT_S * SR:  # nobody continued; send the fragment alone
                    self._emit()
            elif n >= MAX_SEGMENT_S * SR:
                self._emit()
                self.vad.reset_states()
            elif ev and "end" in ev:
                if n < MERGE_BELOW_S * SR:
                    self.holding = 1  # e.g. a lone "nanna," — wait to see if the sentence continues
                else:
                    self._emit()

    def _emit(self):
        self.out_q.put(np.concatenate(self.speech))
        self.speech = None
        self.holding = 0


LANG_NAMES = {"te": "Telugu", "hi": "Hindi", "ta": "Tamil", "kn": "Kannada", "ml": "Malayalam", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi", "bn": "Bengali"}


class Translator:
    """Claude when credentials are configured (much better Telugu -> English), otherwise Whisper's own translate task."""

    def __init__(self, lang):
        self.lang = lang
        self.history = []  # recent (original, english) pairs so pronouns and topics carry over
        self.client = None
        try:
            import anthropic
            self.client = anthropic.Anthropic()
            self.client.models.retrieve(CLAUDE_MODEL)  # fail fast if there are no usable credentials
            print(f"Translating with {CLAUDE_MODEL}", flush=True)
        except Exception as e:
            self.client = None
            print(f"Translating with Whisper; Claude unavailable ({str(e)[:80]}). Set ANTHROPIC_API_KEY for better translations.", flush=True)

    def __call__(self, audio, original):
        english = self._claude(original) if self.client else None
        if english is None:
            # Whisper's fallback temperatures matter: at temperature=0 it often stops after a few words.
            english = mlx_whisper.transcribe(audio, path_or_hf_repo=TRANSLATE_MODEL, language=self.lang, task="translate")["text"].strip()
        self.history = (self.history + [(original, english)])[-4:]
        return english

    def _claude(self, original):
        lang_name = LANG_NAMES.get(self.lang, self.lang)
        context = "\n".join(f"{o} => {e}" for o, e in self.history)
        try:
            response = self.client.beta.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=512,
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=(f"You translate a live {lang_name} phone call between grandparents and their grandchild into natural, "
                        "warm English subtitles. The text comes from speech recognition and may have small errors; translate "
                        "what the speaker most likely said. Keep names of foods, places, festivals and objects in romanized "
                        f"{lang_name} (e.g. pulihora, auto) so the app can show a picture of them. Reply with only the translation."),
                messages=[{"role": "user", "content": (f"Earlier in the call:\n{context}\n\n" if context else "") + f"Translate:\n{original}"}],
            )
        except Exception as e:
            print(f"Claude translation failed ({type(e).__name__}); using Whisper for this line.", flush=True)
            return None
        if response.stop_reason == "refusal":
            return None
        return "".join(b.text for b in response.content if b.type == "text").strip() or None


def recognizer(seg_q, lang, idle):
    translate = Translator(lang)
    opts = dict(language=lang, temperature=0.0, condition_on_previous_text=False)
    seg_id = 0
    while True:
        idle.set()
        audio = seg_q.get()
        idle.clear()
        if len(audio) < SR * 0.4:
            continue
        seg_id += 1
        t0 = time.time()
        original = mlx_whisper.transcribe(audio, path_or_hf_repo=TRANSCRIBE_MODEL, task="transcribe", **opts)["text"].strip()
        if not original:
            continue
        t1 = time.time()
        broadcast({"type": "original", "id": seg_id, "text": original})
        english = translate(audio, original)
        t2 = time.time()
        broadcast({"type": "english", "id": seg_id, "text": english})
        print(f"[{len(audio)/SR:4.1f}s audio | text {t1-t0:.2f}s, english {t2-t1:.2f}s] {original}  ->  {english}", flush=True)


def warm_up(lang):
    print("Loading Whisper models (first run downloads ~4.5 GB)...", flush=True)
    silence = np.zeros(SR, dtype=np.float32)
    mlx_whisper.transcribe(silence, path_or_hf_repo=TRANSCRIBE_MODEL, language=lang)
    mlx_whisper.transcribe(silence, path_or_hf_repo=TRANSLATE_MODEL, language=lang, task="translate")


def feed_file(path, seg):
    with wave.open(path) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1, "file must be 16 kHz mono wav"
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    audio = np.concatenate([audio, np.zeros(SR, dtype=np.float32)])  # trailing silence closes the last phrase
    step = SR // 10
    for i in range(0, len(audio), step):  # real-time pace, like a call
        seg.feed(audio[i:i + step])
        time.sleep(0.1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lang", default="te", help="Whisper language code: te (Telugu), hi (Hindi), ta, kn, ...")
    p.add_argument("--file", help="replay a 16 kHz mono wav instead of listening to the call")
    p.add_argument("--in", dest="inp", default="BlackHole")
    p.add_argument("--out", default=None)
    a = p.parse_args()

    warm_up(a.lang)
    seg_q = queue.Queue()
    seg = Segmenter(seg_q)
    idle = threading.Event()
    threading.Thread(target=recognizer, args=(seg_q, a.lang, idle), daemon=True).start()
    server = serve(ws_handler, "localhost", PORT, process_request=serve_overlay)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Overlay: http://localhost:{PORT}", flush=True)

    if a.file:
        feed_file(a.file, seg)
        while not (seg_q.empty() and idle.wait(timeout=60)):  # let the last phrases finish
            time.sleep(0.5)
        time.sleep(1)
        return

    from audio_loop import AudioLoop, find_device
    import sounddevice as sd
    in_dev = find_device(a.inp, "input")
    out_dev = find_device(a.out, "output") if a.out else sd.default.device[1]
    # Keep VAD out of the realtime audio callback; 48 kHz -> 16 kHz by averaging groups of 3 samples.
    audio_q = queue.Queue()
    threading.Thread(target=lambda: [seg.feed(audio_q.get()) for _ in iter(int, 1)], daemon=True).start()
    loop = AudioLoop(in_dev, out_dev, on_audio=lambda x: audio_q.put(x.reshape(-1, 3).mean(axis=1)))
    try:
        loop.run()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()

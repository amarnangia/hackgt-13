# Local, deterministic Indic -> English translation with IndicTrans2 1B (AI4Bharat), on the Mac's GPU.
# For --two-way it also translates English -> Indic (IndicTrans2 en-indic 1B) and speaks Telugu (Meta MMS-TTS, CPU);
# both load on first use (POST /load), so one-way calls start as fast as before.
# Runs in its own virtualenv because IndicTrans2's model code needs transformers 4.51 and mlx-audio needs 5.x:
#   python3 -m venv .venv-translate && .venv-translate/bin/pip install -r requirements-translate.txt
#   .venv-translate/bin/python translate_server.py        # leave running; subtitles.py talks to it
# The models are gated: accept their terms at https://huggingface.co/ai4bharat/indictrans2-indic-en-1B (and, for
# --two-way, https://huggingface.co/ai4bharat/indictrans2-en-indic-1B) and run `hf auth login`.
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from lexicon import Lexicon

PORT = 8766
KEEP_WARM_S = 3
MODEL = "ai4bharat/indictrans2-indic-en-1B"
TO_INDIC_MODEL = "ai4bharat/indictrans2-en-indic-1B"
FLORES = {"te": "tel_Telu", "hi": "hin_Deva", "ta": "tam_Taml", "kn": "kan_Knda", "ml": "mal_Mlym", "bn": "ben_Beng", "mr": "mar_Deva"}
MMS_TTS = {"te": "tel", "hi": "hin", "ta": "tam", "kn": "kan", "ml": "mal", "bn": "ben", "mr": "mar"}  # facebook/mms-tts-<code>
GPU_LOCK = threading.Lock()  # one GPU, one translation at a time (either direction)


class IndicTranslator:
    def __init__(self):
        import torch
        from IndicTransToolkit.processor import IndicProcessor
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.ip = IndicProcessor(inference=True)
        self.tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL, trust_remote_code=True, torch_dtype=torch.float16 if self.device == "mps" else torch.float32
        ).to(self.device).eval()
        self.lexicon = Lexicon()
        self.lexicon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lexicon.json")
        self.lexicon_mtime = os.path.getmtime(self.lexicon_path)
        self.lock = GPU_LOCK
        self.last_used = time.monotonic()

    def __call__(self, text, lang="te", use_lexicon=True):
        self.last_used = time.monotonic()
        if not text.strip():
            return ""
        src = FLORES[lang]
        if os.path.getmtime(self.lexicon_path) != self.lexicon_mtime:  # pick up edits to lexicon.json live
            self.lexicon, self.lexicon_mtime = Lexicon(), os.path.getmtime(self.lexicon_path)
        prepared = self.lexicon.substitute(text, lang) if use_lexicon else text
        # IndicTrans2 is trained on single sentences and silently drops the second of two, so split and batch.
        sentences = [s for s in re.split(r"(?<=[.?!।])\s+", prepared.strip()) if s]
        # A sentence the word list already turned fully into English ("sweetheart, are you doing well?") must not go
        # through the model: it expects Telugu and garbled it ("Sweetheart is you doing well, having you eat").
        english_already = [not re.search(r"[\u0900-\u0DFF]", s) for s in sentences]
        to_translate = [s for s, done in zip(sentences, english_already) if not done]
        if not to_translate:
            return " ".join(s[:1].upper() + s[1:] for s in sentences)
        with self.lock:  # IndicProcessor deadlocks when two threads call it at once, so it stays inside the lock too
            batch = self.ip.preprocess_batch(to_translate, src_lang=src, tgt_lang="eng_Latn")
            inputs = self.tok(batch, return_tensors="pt", padding=True, truncation=True).to(self.device)
            with self.torch.no_grad():
                # Greedy decoding: the same input always gives the same English.
                out = self.model.generate(**inputs, num_beams=1, do_sample=False, max_new_tokens=128, use_cache=True)
            decoded = self.tok.batch_decode(out, skip_special_tokens=True, clean_up_tokenization_spaces=True)
            translated = iter(self.ip.postprocess_batch(decoded, lang="eng_Latn"))
        return " ".join((s[:1].upper() + s[1:]) if done else next(translated) for s, done in zip(sentences, english_already))


class ToIndicTranslator:
    """English -> Telugu (or another Indian language) for the Telugu speaker in --two-way calls."""

    def __init__(self):
        import torch
        from IndicTransToolkit.processor import IndicProcessor
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self.torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.ip = IndicProcessor(inference=True)
        self.tok = AutoTokenizer.from_pretrained(TO_INDIC_MODEL, trust_remote_code=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            TO_INDIC_MODEL, trust_remote_code=True, torch_dtype=torch.float16 if self.device == "mps" else torch.float32
        ).to(self.device).eval()
        self.last_used = time.monotonic()

    def __call__(self, text, lang="te"):
        self.last_used = time.monotonic()
        sentences = [s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s]
        if not sentences:
            return ""
        with GPU_LOCK:
            batch = self.ip.preprocess_batch(sentences, src_lang="eng_Latn", tgt_lang=FLORES[lang])
            inputs = self.tok(batch, return_tensors="pt", padding=True, truncation=True).to(self.device)
            with self.torch.no_grad():
                out = self.model.generate(**inputs, num_beams=1, do_sample=False, max_new_tokens=128, use_cache=True)
            decoded = self.tok.batch_decode(out, skip_special_tokens=True, clean_up_tokenization_spaces=True)
            return " ".join(self.ip.postprocess_batch(decoded, lang=FLORES[lang]))


class IndicVoice:
    """Speaks Telugu (or another Indian language) with Meta's MMS-TTS. On the CPU: ~0.4 s a sentence, faster than
    the GPU once warm (and the GPU stays free for translation). A stock voice: cloning doesn't cover Telugu here."""

    def __init__(self, lang):
        import torch
        from transformers import AutoTokenizer, VitsModel

        name = f"facebook/mms-tts-{MMS_TTS[lang]}"
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(name)
        self.model = VitsModel.from_pretrained(name).eval()
        self.sample_rate = self.model.config.sampling_rate
        self.lock = threading.Lock()

    def __call__(self, text):
        """16-bit mono PCM bytes at self.sample_rate."""
        import numpy as np

        with self.lock, self.torch.no_grad():
            self.torch.manual_seed(0)  # VITS samples its prosody; seed it so a line sounds the same every time
            wave = self.model(**self.tok(text, return_tensors="pt")).waveform[0].numpy()
        return (np.clip(wave, -1, 1) * 32767).astype(np.int16).tobytes()


class LocalTranslator:
    """Client used by subtitles.py (main virtualenv) to call this server."""

    def __init__(self, lang):
        import requests

        self.lang = lang
        self.session = requests.Session()

    def available(self):
        try:
            self("")
            return True
        except Exception:
            return False

    def warm_up(self):
        pass

    def __call__(self, text):
        r = self.session.post(f"http://localhost:{PORT}", json={"text": text, "lang": self.lang}, timeout=10)
        r.raise_for_status()
        return r.json()["english"]

    def load_two_way(self):
        """Load English -> Telugu and the Telugu voice (first time only; ~20 s). Returns an error string or None."""
        try:
            r = self.session.post(f"http://localhost:{PORT}/load", json={"lang": self.lang}, timeout=600)
            return r.json().get("error") if r.ok else f"HTTP {r.status_code}"
        except Exception as e:
            return f"{type(e).__name__}: {e}"

    def to_indic(self, text):
        r = self.session.post(f"http://localhost:{PORT}/to_indic", json={"text": text, "lang": self.lang}, timeout=10)
        r.raise_for_status()
        return r.json()["text"]

    def speak(self, text):
        """(16-bit mono PCM samples as int16 numpy, sample rate) of `text` spoken in self.lang."""
        import numpy as np

        r = self.session.post(f"http://localhost:{PORT}/speak", json={"text": text, "lang": self.lang}, timeout=20)
        r.raise_for_status()
        return np.frombuffer(r.content, dtype=np.int16), int(r.headers["X-Sample-Rate"])


def main():
    print(f"Loading {MODEL}...", flush=True)
    translate = IndicTranslator()
    translate("నీ చదువు ఎలా ఉంది?")  # warm up the GPU kernels

    two_way = {"to_indic": None, "voices": {}}
    load_lock = threading.Lock()

    def load(lang):
        with load_lock:
            if two_way["to_indic"] is None:
                print(f"Loading {TO_INDIC_MODEL}...", flush=True)
                two_way["to_indic"] = ToIndicTranslator()
                two_way["to_indic"]("How are you?", lang)  # warm up
            if lang not in two_way["voices"]:
                print(f"Loading the {lang} voice (facebook/mms-tts-{MMS_TTS[lang]})...", flush=True)
                two_way["voices"][lang] = IndicVoice(lang)
                two_way["voices"][lang]("సరే" if lang == "te" else "ok")  # warm up
            print("Two-way models ready.", flush=True)

    class Handler(BaseHTTPRequestHandler):
        timeout = 5  # a client that never finishes its request can't tie up a thread

        def _send(self, body, kind="application/json", headers=()):
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            start = time.monotonic()
            lang = req.get("lang", "te")
            if self.path == "/load":
                try:
                    load(lang)
                    return self._send(b"{}")
                except Exception as e:
                    return self._send(json.dumps({"error": f"{type(e).__name__}: {e}"}).encode())
            if self.path == "/to_indic":
                load(lang)
                text = two_way["to_indic"](req["text"], lang)
                return self._send(json.dumps({"text": text, "ms": round((time.monotonic() - start) * 1000)}).encode())
            if self.path == "/speak":
                load(lang)
                voice = two_way["voices"][lang]
                return self._send(voice(req["text"]), "audio/L16", [("X-Sample-Rate", str(voice.sample_rate))])
            english = translate(req["text"], lang, req.get("use_lexicon", True))
            self._send(json.dumps({"english": english, "ms": round((time.monotonic() - start) * 1000)}).encode())

        def log_message(self, *args):
            pass

    def keep_warm():
        # macOS swaps out memory that hasn't been touched lately; under memory pressure that made translations
        # take ~10 s instead of ~0.4 s. A tiny translation every few idle seconds keeps the model in RAM.
        while True:
            time.sleep(KEEP_WARM_S)
            if time.monotonic() - translate.last_used > KEEP_WARM_S:
                translate("సరే", use_lexicon=False)
            to_indic = two_way["to_indic"]
            if to_indic and time.monotonic() - to_indic.last_used > KEEP_WARM_S:
                to_indic("Okay.")

    threading.Thread(target=keep_warm, daemon=True).start()
    print(f"Translator ready on http://localhost:{PORT}", flush=True)
    ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

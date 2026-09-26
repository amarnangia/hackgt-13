# Local, deterministic Indic -> English translation with IndicTrans2 1B (AI4Bharat), on the Mac's GPU.
# Runs in its own virtualenv because IndicTrans2's model code needs transformers 4.51 and mlx-audio needs 5.x:
#   python3 -m venv .venv-translate && .venv-translate/bin/pip install -r requirements-translate.txt
#   .venv-translate/bin/python translate_server.py        # leave running; subtitles.py talks to it
# The model is gated: accept its terms at https://huggingface.co/ai4bharat/indictrans2-indic-en-1B and run `hf auth login`.
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
FLORES = {"te": "tel_Telu", "hi": "hin_Deva", "ta": "tam_Taml", "kn": "kan_Knda", "ml": "mal_Mlym", "bn": "ben_Beng", "mr": "mar_Deva"}


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
        self.lock = threading.Lock()  # one GPU, one translation at a time
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
        batch = self.ip.preprocess_batch(sentences, src_lang=src, tgt_lang="eng_Latn")
        with self.lock:
            inputs = self.tok(batch, return_tensors="pt", padding=True, truncation=True).to(self.device)
            with self.torch.no_grad():
                # Greedy decoding: the same input always gives the same English.
                out = self.model.generate(**inputs, num_beams=1, do_sample=False, max_new_tokens=128, use_cache=True)
        decoded = self.tok.batch_decode(out, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        return " ".join(self.ip.postprocess_batch(decoded, lang="eng_Latn"))


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


def main():
    print(f"Loading {MODEL}...", flush=True)
    translate = IndicTranslator()
    translate("నీ చదువు ఎలా ఉంది?")  # warm up the GPU kernels

    class Handler(BaseHTTPRequestHandler):
        timeout = 5  # a client that never finishes its request can't tie up a thread

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            start = time.monotonic()
            english = translate(req["text"], req.get("lang", "te"), req.get("use_lexicon", True))
            body = json.dumps({"english": english, "ms": round((time.monotonic() - start) * 1000)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    def keep_warm():
        # macOS swaps out memory that hasn't been touched lately; under memory pressure that made translations
        # take ~10 s instead of ~0.4 s. A tiny translation every few idle seconds keeps the model in RAM.
        while True:
            time.sleep(KEEP_WARM_S)
            if time.monotonic() - translate.last_used > KEEP_WARM_S:
                translate("సరే", use_lexicon=False)

    threading.Thread(target=keep_warm, daemon=True).start()
    print(f"Translator ready on http://localhost:{PORT}", flush=True)
    ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

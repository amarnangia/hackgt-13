# Meta Model API clients: Muse Voice Transcribe (live speech -> text) and Muse Spark (translation).
# The key is read from MODEL_API_KEY, or from a gitignored .env file containing MODEL_API_KEY=...
import asyncio
import json
import os
import ssl
import sys
from collections import deque

import certifi
import requests
import websockets

API_URL = "https://api.meta.ai/v1"
ASR_URL = "wss://api.meta.ai/v1/asr/realtime"
ASR_MODEL = "muse-voice-transcribe-1.0"
SPARK_MODEL = "muse-spark-1.2"  # ~1.9 s per sentence at minimal reasoning; 1.3 was ~2.8 s

# python.org's Python ships without CA certificates, so HTTPS fails unless we point it at certifi's bundle.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

LANGUAGES = {"te": "Telugu", "hi": "Hindi", "ta": "Tamil", "kn": "Kannada", "ml": "Malayalam", "bn": "Bengali", "mr": "Marathi"}


def api_key():
    key = os.environ.get("MODEL_API_KEY")
    if not key and os.path.exists(".env"):
        for line in open(".env"):
            name, _, value = line.strip().partition("=")
            if name == "MODEL_API_KEY":
                key = value
    if not key:
        sys.exit("Missing MODEL_API_KEY. Put MODEL_API_KEY=<your key> in .env (it is gitignored).")
    return key


async def transcribe(audio_q, lang, encoding="PCM_24KHZ"):
    """Stream raw 16-bit mono PCM chunks from `audio_q` (None ends the stream) and yield Muse events.

    Events: speechStart / transcript (cumulative partials for the current turn) / speechEnd / speechComplete.
    """
    handshake = {
        "mode": "ENDPOINTING",  # Muse decides where each utterance ends
        "authorization": {"accessToken": api_key()},
        "audioEncoding": encoding,
        "model": ASR_MODEL,
        "partialMode": "CUMULATIVE",
        "emitAudioProgress": False,
        # Without the hint, the first word sometimes comes back romanized ("Nanna").
        "languageBias": [LANGUAGES.get(lang, lang).lower()],
    }
    async with websockets.connect(ASR_URL, ssl=SSL_CONTEXT, max_size=None) as ws:
        await ws.send(json.dumps(handshake))
        ack = json.loads(await ws.recv())
        if ack.get("type") == "error":
            raise RuntimeError(f"Muse rejected the session: {ack.get('message')}")

        async def send_audio():
            while (chunk := await audio_q.get()) is not None:
                await ws.send(chunk)
            await ws.send(json.dumps({"type": "endStream"}))

        sender = asyncio.create_task(send_audio())
        try:
            async for message in ws:
                if isinstance(message, bytes):
                    continue
                event = json.loads(message)
                if event.get("type") == "error":
                    raise RuntimeError(f"Muse error: {event.get('message')}")
                yield event
        finally:
            sender.cancel()


class Translator:
    """Translates one sentence at a time with Muse Spark, passing the last few lines as context."""

    def __init__(self, lang):
        self.lang_name = LANGUAGES.get(lang, lang)
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key()}"
        self.history = deque(maxlen=3)
        self.system = (
            f"You translate a live {self.lang_name} phone call from grandparents to their grandchild into natural, "
            "warm English subtitles. The text comes from live speech recognition. Keep names of foods, festivals and "
            f"objects in romanized {self.lang_name} (e.g. pulihora, auto) so the app can show a picture of them, but "
            "translate everyday words (gudi -> temple). Reply with only the translation."
        )

    def warm_up(self):
        """Open the HTTPS connection before the call starts, so the first real sentence isn't slow."""
        try:
            self.session.post(f"{API_URL}/chat/completions", timeout=20, json={
                "model": SPARK_MODEL, "reasoning_effort": "minimal", "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            })
        except requests.RequestException:
            pass

    def __call__(self, text):
        messages = [{"role": "system", "content": self.system}]
        for original, english in self.history:
            messages += [{"role": "user", "content": original}, {"role": "assistant", "content": english}]
        messages.append({"role": "user", "content": text})
        r = self.session.post(f"{API_URL}/chat/completions", timeout=20, json={
            "model": SPARK_MODEL, "messages": messages, "reasoning_effort": "minimal",
        })
        r.raise_for_status()
        english = r.json()["choices"][0]["message"]["content"].strip()
        self.history.append((text, english))
        return english

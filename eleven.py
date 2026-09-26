# ElevenLabs: personalized voices. The iPhone app records someone reading for ~1 minute, the Weave server on the Mac
# (garden/server.py) sends it to ElevenLabs Instant Voice Cloning, and the voice_id is kept with that person in
# people.py (calls/people.json and Firestore), so every laptop on the team has it. subtitles.py then
# speaks each side's translation in that person's own voice: English through Flash v2.5 (~75 ms to first audio),
# Telugu through v3 Conversational (~280 ms; Multilingual v2 and Flash don't support Telugu).
#
# The key is read from ELEVENLABS_API_KEY, or from the gitignored .env. It stays on the Mac: the phone never sees it.
# Standard library only (the Weave server installs nothing); the streaming voice in dub.py uses requests.
import json
import os
import ssl
import time
import urllib.request
import uuid

import people

HERE = os.path.dirname(os.path.abspath(__file__))
API_URL = "https://api.elevenlabs.io/v1"
ENGLISH_MODEL = "eleven_flash_v2_5"         # fastest; reads romanized Telugu words (pappu, annam) phonetically
INDIC_MODEL = "eleven_v3_conversational"    # the realtime model that speaks Telugu
MODEL_LANGS = {"te", "hi", "ta", "kn", "ml", "bn", "mr"}

try:  # python.org's Python ships without CA certificates (see muse.py)
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


def api_key():
    key = os.environ.get("ELEVENLABS_API_KEY")
    env = os.path.join(HERE, ".env")
    if not key and os.path.exists(env):
        for line in open(env):
            name, _, value = line.strip().partition("=")
            if name == "ELEVENLABS_API_KEY":
                key = value.strip().strip("\"'")
    return key or None


# ---------- clone / remove ----------
def _request(method, path, body=None, headers=None, timeout=60):
    req = urllib.request.Request(API_URL + path, data=body, method=method,
                                 headers={"xi-api-key": api_key(), **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as r:
        return json.loads(r.read() or b"{}")


def clone(name, audio, filename="voice.m4a", content_type="audio/mp4", consent_by=None):
    """Make an Instant Voice Clone of `name` from one recording (bytes). Replaces their old voice. Returns the record."""
    if not api_key():
        raise RuntimeError("no ELEVENLABS_API_KEY in .env")
    boundary = uuid.uuid4().hex
    fields = [("name", f"Weave: {name}"),
              ("description", f"{name}'s voice for Weave call translation, recorded in the Weave app"),
              ("remove_background_noise", "false")]  # a phone in a quiet room; noise removal can hurt clean audio
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
                 f"Content-Type: {content_type}\r\n\r\n".encode() + audio + b"\r\n")
    body = b"".join(parts) + f"--{boundary}--\r\n".encode()
    voice_id = _request("POST", "/voices/add", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})["voice_id"]

    old = people.voice_for(name)
    pid, record = people.update(name, voice_id=voice_id, voice_created=time.time(), consent_by=consent_by or name,
                                bytes=len(audio))
    if old and old != voice_id:
        _delete_remote(old)  # re-recorded: don't leave the old copy of their voice at ElevenLabs
    return pid, record


def remove(name):
    """Delete this person's voice at ElevenLabs and here (they stay in the family list). True if they had one."""
    voice_id = people.voice_for(name)
    if not voice_id:
        return False
    _delete_remote(voice_id)
    people.update(name, voice_id=None)
    return True


def _delete_remote(voice_id):
    try:
        _request("DELETE", f"/voices/{voice_id}", timeout=15)
    except Exception as e:
        print(f"Couldn't delete ElevenLabs voice {voice_id} ({type(e).__name__}: {e})", flush=True)


# ---------- speaking (dub.py) ----------
class Speaker:
    """Streams one person's voice as 24 kHz 16-bit PCM. Keeps one HTTPS connection open between lines, so each line
    costs the model's time to first audio plus one round trip, not a new TLS handshake."""

    SR = 24000

    def __init__(self, voice_id):
        import requests

        self.voice_id = voice_id
        self.session = requests.Session()
        self.session.headers["xi-api-key"] = api_key()
        # Opens the connection and checks the voice still exists (someone may have removed it from another laptop).
        r = self.session.get(f"{API_URL}/voices/{voice_id}", timeout=10)
        r.raise_for_status()
        self.name = r.json().get("name", voice_id)

    def stream(self, text, lang="en", speed=1.0):
        """Yield raw PCM chunks (bytes, even length) as ElevenLabs generates them."""
        indic = lang in MODEL_LANGS
        body = {"text": text, "model_id": INDIC_MODEL if indic else ENGLISH_MODEL,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "speed": max(0.7, min(1.2, speed))}}
        if indic:
            body["language_code"] = lang
        with self.session.post(f"{API_URL}/text-to-speech/{self.voice_id}/stream", params={"output_format": "pcm_24000"},
                               json=body, stream=True, timeout=(5, 20)) as r:
            if r.status_code != 200:
                raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
            left = b""
            for chunk in r.iter_content(chunk_size=4800):  # 0.1 s
                chunk = left + chunk
                cut = len(chunk) - len(chunk) % 2
                left = chunk[cut:]
                if cut:
                    yield chunk[:cut]


# ---------- by hand, on the Mac ----------
#   python eleven.py clone "Amar" recording.m4a    a recording made anywhere (QuickTime, Voice Memos, a WhatsApp note)
#   python eleven.py remove "Amar"
#   python eleven.py list
if __name__ == "__main__":
    import mimetypes
    import sys

    import sync

    cmd, rest = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "clone" and len(rest) == 2:
        name, path = rest
        if input(f"Does {name} agree to Weave making a copy of their voice with ElevenLabs? [y/N] ").strip().lower() != "y":
            sys.exit("Not made.")
        audio = open(path, "rb").read()
        pid, record = clone(name, audio, os.path.basename(path), mimetypes.guess_type(path)[0] or "audio/mpeg", consent_by=name)
        print(f"Made {name}'s voice: {record['voice_id']}")
        sync.people()  # the other laptops
    elif cmd == "remove" and len(rest) == 1:
        print("Removed." if remove(rest[0]) else f"{rest[0]} has no voice.")
        sync.people()
    elif cmd == "list":
        for pid, p in people.load().items():
            print(f"{p['name']:<20} {'own voice (' + p['voice_id'] + ')' if p.get('voice_id') else 'no voice'}")
    else:
        sys.exit('usage: python eleven.py clone "Name" recording.m4a | remove "Name" | list')

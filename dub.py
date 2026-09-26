# Step 5 of plan.md: speak each English translation with Kokoro (local, on the Mac GPU via mlx-audio)
# on top of the call audio, which AudioLoop lowers while the voice plays.
import os
import queue
import threading
import time

import numpy as np

# Kokoro pronounces unknown words (pulihora, Sankranti) through espeak-ng: `brew install espeak-ng`.
for lib in ("/opt/homebrew/lib/libespeak-ng.1.dylib", "/usr/local/lib/libespeak-ng.1.dylib"):
    if os.path.exists(lib):
        os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", lib)
        break

KOKORO_MODEL = "mlx-community/Kokoro-82M-bf16"
KOKORO_SR = 24000
MAX_BEHIND_S = 3.0  # skip the voice (subtitle only) rather than fall further behind; one English sentence is ~2-3 s


class Dubber:
    def __init__(self, voice_buffer, voice="af_heart", speed=1.1):
        from mlx_audio.tts.utils import load_model

        self.buffer = voice_buffer  # AudioLoop.voice
        self.voice, self.speed = voice, speed
        self.model = load_model(KOKORO_MODEL)
        self._synth("Hello.")  # the first generation takes ~4 s; do it before the call
        self.jobs = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def behind(self):
        """Seconds of English speech queued but not yet played."""
        return self.buffer.pending_seconds() + self.jobs.qsize() * 1.5

    def say(self, text, spoken_at=None, on_start=None):
        """Queue `text` to be spoken. Returns False (and says nothing) if the voice is too far behind."""
        if not text or not text.strip() or text.startswith("("):
            return False
        late = time.monotonic() - spoken_at if spoken_at else 0.0
        if self.behind() + late > MAX_BEHIND_S:
            return False
        self.jobs.put((text, on_start))
        return True

    def _synth(self, text):
        chunks = [np.asarray(r.audio).reshape(-1) for r in
                  self.model.generate(text, voice=self.voice, speed=self.speed, lang_code="a")]
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        # 24 kHz -> 48 kHz for the output device
        return np.interp(np.arange(len(audio) * 2) / 2, np.arange(len(audio)), audio).astype(np.float32)

    def _worker(self):
        while True:
            text, on_start = self.jobs.get()
            try:
                self.buffer.push(self._synth(text), on_start)
            except Exception as e:
                print(f"Voice failed for {text!r}: {type(e).__name__}: {e}", flush=True)

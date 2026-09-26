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
BASE_SPEED, MAX_SPEED = 1.0, 1.3  # natural pace, speeding up smoothly as lines pile up
CATCH_UP_S = 2.0                  # queued speech at which we reach MAX_SPEED
CLAUSE_SPLIT = r"(?<=[,;:.!?])\s+"  # generate and start playing clause by clause


class Dubber:
    def __init__(self, voice_buffer, voice="af_heart"):
        from mlx_audio.tts.utils import load_model

        self.buffer = voice_buffer  # AudioLoop.voice
        self.voice = voice
        self.model = load_model(KOKORO_MODEL)
        list(self._clips("Hello, there.", BASE_SPEED))  # the first generation takes ~4 s; do it before the call
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

    def _clips(self, text, speed):
        """Yield 48 kHz audio clause by clause, so playback can start before the whole line is generated."""
        for r in self.model.generate(text, voice=self.voice, speed=speed, lang_code="a", split_pattern=CLAUSE_SPLIT):
            audio = np.asarray(r.audio).reshape(-1)
            # 24 kHz -> 48 kHz for the output device
            yield np.interp(np.arange(len(audio) * 2) / 2, np.arange(len(audio)), audio).astype(np.float32)

    def _worker(self):
        while True:
            text, on_start = self.jobs.get()
            behind = self.buffer.pending_seconds()
            speed = BASE_SPEED + (MAX_SPEED - BASE_SPEED) * min(1.0, behind / CATCH_UP_S)
            try:
                for clip in self._clips(text, speed):
                    self.buffer.push(clip, on_start)
                    on_start = None  # only the first clause marks "voice started"
            except Exception as e:
                print(f"Voice failed for {text!r}: {type(e).__name__}: {e}", flush=True)

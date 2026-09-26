# Step 5 of plan.md: speak each English translation on top of the call audio, which AudioLoop lowers
# while the voice plays. Everything runs locally on the Mac GPU via mlx-audio.
#
# Voice: Kokoro (a stock voice) until we have ~10 s of the caller's speech, then Pocket TTS cloning the
# caller's voice from that clip, so the English sounds like the person you're talking to. The clip is saved
# (caller_voice.wav, gitignored) and reused on the next call.
import os
import queue
import re
import threading
import time
import wave

import mlx.core as mx
import numpy as np

# MLX keeps freed GPU buffers for reuse; generating one sentence grew this cache to ~2 GB and it never shrank,
# which pushed a 24 GB Mac into swap and made translation take ~10 s. 256 MB is plenty (same speed).
mx.set_cache_limit(256 * 2**20)

# Kokoro pronounces unknown words (pulihora, Sankranti) through espeak-ng: `brew install espeak-ng`.
for lib in ("/opt/homebrew/lib/libespeak-ng.1.dylib", "/usr/local/lib/libespeak-ng.1.dylib"):
    if os.path.exists(lib):
        os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", lib)
        break

KOKORO_MODEL = "mlx-community/Kokoro-82M-bf16"
CLONE_MODEL = "mlx-community/pocket-tts"  # ~0.5 s to first audio, like Kokoro; Chatterbox Turbo took ~3 s
OUT_SR = 48000
MAX_BEHIND_S = 3.0           # skip the voice (subtitle only) rather than fall further behind; one sentence is ~2-3 s
MAX_BEHIND_PRIORITY_S = 5.0  # questions/requests to you are still spoken up to this far behind
BASE_SPEED, MAX_SPEED = 1.0, 1.3  # Kokoro: natural pace, speeding up smoothly as lines pile up
CATCH_UP_S = 2.0                  # queued speech at which we reach MAX_SPEED
CLAUSE_SPLIT = r"(?<=[,;:.!?])\s+"  # generate and start playing clause by clause


def normalize(audio, target_rms=0.08, peak=0.9):
    """The clone copies the recording's volume too, and call audio is quiet; bring each clause to a steady level."""
    rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) else 0.0
    if rms < 1e-4:
        return audio
    gain = min(target_rms / rms, peak / max(1e-6, float(np.abs(audio).max())))
    return (audio * gain).astype(np.float32)


def to_48k(audio, sr):
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    n = int(len(audio) * OUT_SR / sr)
    return np.interp(np.arange(n) * sr / OUT_SR, np.arange(len(audio)), audio).astype(np.float32)


class Dubber:
    def __init__(self, voice_buffer, voice="af_heart", clone=True, voice_sample=None):
        from mlx_audio.tts.utils import load_model

        self.buffer = voice_buffer  # AudioLoop.voice
        self.voice = voice
        self.pocket = load_model(CLONE_MODEL) if clone else None
        self.clone_state = None  # Pocket TTS conditioning for the caller's voice, once we have a sample
        if self.pocket and voice_sample and os.path.exists(voice_sample):
            self._use_sample(voice_sample)
        self.kokoro = None
        if not self.cloning:  # the stock voice is only needed until we have the caller's voice
            self.kokoro = load_model(KOKORO_MODEL)
            list(self._kokoro_clips("Hello, there.", BASE_SPEED))  # the first generation takes ~4 s; do it now
        self.jobs = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    @property
    def cloning(self):
        return self.clone_state is not None

    def behind(self):
        """Seconds of English speech queued but not yet played."""
        return self.buffer.pending_seconds() + self.jobs.qsize() * 1.5

    def say(self, text, spoken_at=None, on_start=None, priority=False):
        """Queue `text` to be spoken. Returns False (and says nothing) if the voice is too far behind."""
        if not text or not text.strip() or text.startswith("("):
            return False
        late = time.monotonic() - spoken_at if spoken_at else 0.0
        if self.behind() + late > (MAX_BEHIND_PRIORITY_S if priority else MAX_BEHIND_S):
            return False
        self.jobs.put(("say", text, on_start))
        return True

    def use_voice_sample(self, path):
        """Switch to the caller's voice (runs on the voice thread, between lines)."""
        if self.pocket:
            self.jobs.put(("sample", path, None))

    def _use_sample(self, path):
        self.clone_state = self.pocket.get_state_for_audio_prompt(path)  # encode the voice once, reuse per line
        # Generating appends each sentence to this state; unless we cut it back to just the voice before every
        # sentence, the model "remembers" earlier sentences and stops almost immediately (0.2 s clips).
        self.voice_frames = self.pocket._get_flow_cache_num_frames(self.clone_state)
        list(self._clone_clips("Okay."))  # warm up

    def _kokoro_clips(self, text, speed):
        for r in self.kokoro.generate(text, voice=self.voice, speed=speed, lang_code="a", split_pattern=CLAUSE_SPLIT):
            yield to_48k(r.audio, 24000)

    def _clone_clips(self, text):
        for clause in (c for c in re.split(CLAUSE_SPLIT, text) if c.strip()):
            self.pocket._slice_flow_cache(self.clone_state, self.voice_frames)
            chunks = [np.asarray(c).reshape(-1) for c in self.pocket.generate_audio_stream(self.clone_state, clause)]
            if chunks:
                yield to_48k(normalize(np.concatenate(chunks)), self.pocket.sample_rate)

    def _worker(self):
        while True:
            kind, text, on_start = self.jobs.get()
            try:
                if kind == "sample":
                    self._use_sample(text)
                    self.kokoro = None  # free the stock voice
                    mx.clear_cache()
                    print("English voice now sounds like the caller.", flush=True)
                    continue
                if self.cloning:
                    clips = self._clone_clips(text)
                else:
                    behind = self.buffer.pending_seconds()
                    clips = self._kokoro_clips(text, BASE_SPEED + (MAX_SPEED - BASE_SPEED) * min(1.0, behind / CATCH_UP_S))
                for clip in clips:
                    self.buffer.push(clip, on_start)
                    on_start = None  # only the first clause marks "voice started"
            except Exception as e:
                print(f"Voice failed for {text!r}: {type(e).__name__}: {e}", flush=True)


class VoiceSampler:
    """Collects the caller's speech from the call audio until there's enough to clone their voice.

    Fed the same 24 kHz 16-bit frames that go to Muse, so Muse's audioProcessedMs (speechStart / speechEnd)
    locate each utterance in it. Only the call audio is recorded (BlackHole carries the other side only).
    """

    SR = 24000
    NEED_S = 10.0        # seconds of speech for a good clone
    MAX_TURN_S = 6.0     # take at most this much from one utterance, for variety
    MIN_TURN_S = 1.0
    KEEP_S = 60.0        # rolling window of call audio

    def __init__(self, path, on_ready):
        self.path, self.on_ready = path, on_ready
        self.frames, self.start_sample = [], 0   # rolling call audio; sample index of frames[0] in this session
        self.turn_start_ms = None
        self.pieces, self.have_s, self.done = [], 0.0, False
        self.lock = threading.Lock()

    def new_session(self):
        with self.lock:
            self.frames, self.start_sample, self.turn_start_ms = [], 0, None

    def add_frame(self, pcm16):
        if self.done:
            return
        with self.lock:
            self.frames.append(pcm16)
            while sum(len(f) for f in self.frames) > self.KEEP_S * self.SR:
                self.start_sample += len(self.frames.pop(0))

    def on_event(self, ev):
        if self.done:
            return
        if ev.get("type") == "speechStart":
            self.turn_start_ms = ev.get("audioProcessedMs")
        elif ev.get("type") == "speechEnd" and self.turn_start_ms is not None:
            self._take(self.turn_start_ms, ev.get("audioProcessedMs"))
            self.turn_start_ms = None

    def _take(self, start_ms, end_ms):
        if end_ms is None or (end_ms - start_ms) / 1000 < self.MIN_TURN_S:
            return
        with self.lock:
            audio = np.concatenate(self.frames) if self.frames else np.zeros(0, np.int16)
            a = max(0, int(start_ms / 1000 * self.SR) - self.start_sample)
            b = min(len(audio), int(end_ms / 1000 * self.SR) - self.start_sample, a + int(self.MAX_TURN_S * self.SR))
        if b - a < self.MIN_TURN_S * self.SR:
            return
        self.pieces.append(audio[a:b])
        self.have_s += (b - a) / self.SR
        if self.have_s >= self.NEED_S:
            gap = np.zeros(int(0.3 * self.SR), np.int16)
            clip = np.concatenate([p for piece in self.pieces for p in (piece, gap)])
            with wave.open(self.path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self.SR)
                w.writeframes(clip.tobytes())
            self.done = True
            self.on_ready(self.path)

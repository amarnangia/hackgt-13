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
MAX_CLONE_SPEED = 1.12            # the cloned voice has no speed control; playing it faster also raises the pitch a
                                  # little, so it stays gentle (1.12 is ~2 semitones, still clearly her)
CLAUSE_SPLIT = r"(?<=[,;:.!?])\s+"  # generate and start playing clause by clause


TARGET_RMS = 0.08  # speaking level of the English voice


def normalize(audio, target_rms=TARGET_RMS, peak=0.9):
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
        # The clone copies the recording's volume (call audio is quiet). Work out the boost once, from a calibration
        # sentence, so each chunk can play as soon as it's generated instead of waiting for the whole phrase to be
        # normalized (that wait held the voice back ~0.2-0.8 s).
        self.clone_gain = 1.0
        calibration = [np.asarray(c).reshape(-1) for c in self._clone_raw("Hello, how are you doing today? I hope you are well.")]
        sample = np.concatenate(calibration)
        rms, peak = float(np.sqrt(np.mean(sample ** 2))), float(np.abs(sample).max())
        if rms > 1e-4:
            self.clone_gain = min(TARGET_RMS / rms, 0.9 / max(peak, 1e-6))

    def _kokoro_clips(self, text, speed):
        for r in self.kokoro.generate(text, voice=self.voice, speed=speed, lang_code="a", split_pattern=CLAUSE_SPLIT):
            yield to_48k(r.audio, 24000)

    def _clone_raw(self, text):
        for clause in (c for c in re.split(CLAUSE_SPLIT, text) if c.strip()):
            self.pocket._slice_flow_cache(self.clone_state, self.voice_frames)  # just her voice, no earlier sentences
            yield from self.pocket.generate_audio_stream(self.clone_state, clause)

    def _clone_clips(self, text, speed=1.0):
        """Her voice, chunk by chunk as it's generated (~4x faster than real time, so playback doesn't run dry).
        speed > 1 plays it a little faster (and slightly higher) to catch up when English lines are queuing."""
        for chunk in self._clone_raw(text):
            chunk = np.clip(np.asarray(chunk, dtype=np.float32).reshape(-1) * self.clone_gain, -1, 1)
            yield to_48k(chunk, self.pocket.sample_rate * speed)

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
                    behind = self.buffer.pending_seconds()
                    clips = self._clone_clips(text, 1.0 + (MAX_CLONE_SPEED - 1.0) * min(1.0, behind / CATCH_UP_S))
                else:
                    behind = self.buffer.pending_seconds()
                    clips = self._kokoro_clips(text, BASE_SPEED + (MAX_SPEED - BASE_SPEED) * min(1.0, behind / CATCH_UP_S))
                for clip in clips:
                    self.buffer.push(clip, on_start)
                    on_start = None  # only the first clause marks "voice started"
            except Exception as e:
                print(f"Voice failed for {text!r}: {type(e).__name__}: {e}", flush=True)


class VoiceSampler:
    """Collects the caller's speech from the call audio to clone their voice, preferring their English.

    The clone copies the voice from any speech, but the English accent mostly from English speech. So: switch
    to the caller's voice after ~10 s of any speech (English utterances first), then once ~8 s of them speaking
    English is collected, relearn from that alone.

    Fed the same 24 kHz 16-bit frames that go to Muse, so Muse's audioProcessedMs (speechStart / speechEnd)
    locate each utterance and speechComplete's transcript says which language it was. Only the call audio is
    recorded (BlackHole carries the other side only).
    """

    SR = 24000
    FIRST_S = 10.0       # any speech: enough for their voice
    ENGLISH_S = 8.0      # their English: enough for their accent too
    MAX_TURN_S = 6.0     # take at most this much from one utterance, for variety
    MIN_TURN_S = 1.0
    KEEP_S = 60.0        # rolling window of call audio

    def __init__(self, path, on_ready):
        self.path, self.on_ready = path, on_ready
        self.frames, self.start_sample = [], 0   # rolling call audio; sample index of frames[0] in this session
        self.turn_start_ms = None
        self.pending = {}                        # turnId -> audio, until speechComplete says what language it was
        self.english, self.native = [], []
        self.first_done = self.done = False
        self.lock = threading.Lock()

    def new_session(self):
        with self.lock:
            self.frames, self.start_sample, self.turn_start_ms, self.pending = [], 0, None, {}

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
        kind = ev.get("type")
        if kind == "speechStart":
            self.turn_start_ms = ev.get("audioProcessedMs")
        elif kind == "speechEnd" and self.turn_start_ms is not None:
            audio = self._cut(self.turn_start_ms, ev.get("audioProcessedMs"))
            if audio is not None:
                self.pending[ev.get("turnId")] = audio
            self.turn_start_ms = None
        elif kind == "speechComplete" and ev.get("turnId") in self.pending:
            from lexicon import indic_share
            audio, text = self.pending.pop(ev["turnId"]), ev.get("transcript", "")
            is_english = indic_share(text) == 0 and len(text.split()) >= 3
            (self.english if is_english else self.native).append(audio)
            self._maybe_ready()

    def _cut(self, start_ms, end_ms):
        if end_ms is None or (end_ms - start_ms) / 1000 < self.MIN_TURN_S:
            return None
        with self.lock:
            audio = np.concatenate(self.frames) if self.frames else np.zeros(0, np.int16)
            a = max(0, int(start_ms / 1000 * self.SR) - self.start_sample)
            b = min(len(audio), int(end_ms / 1000 * self.SR) - self.start_sample, a + int(self.MAX_TURN_S * self.SR))
        return audio[a:b] if b - a >= self.MIN_TURN_S * self.SR else None

    def _maybe_ready(self):
        seconds = lambda pieces: sum(len(p) for p in pieces) / self.SR
        if seconds(self.english) >= self.ENGLISH_S:
            self._save(self.english)
            self.done = True
            print("Learned the caller's English accent.", flush=True)
            self.on_ready(self.path)
        elif not self.first_done and seconds(self.english) + seconds(self.native) >= self.FIRST_S:
            self._save(self.english + self.native)  # English first; keep listening for more of it
            self.first_done = True
            self.on_ready(self.path)

    def _save(self, pieces):
        gap = np.zeros(int(0.3 * self.SR), np.int16)
        clip = np.concatenate([p for piece in pieces for p in (piece, gap)])
        with wave.open(self.path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.SR)
            w.writeframes(clip.tobytes())

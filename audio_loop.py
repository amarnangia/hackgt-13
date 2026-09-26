# Step 1 of plan.md: WhatsApp call audio -> BlackHole -> this script -> headphones.
# Set WhatsApp's speaker (or the Mac's system output) to "BlackHole 2ch", then run:
#   python audio_loop.py                      # plays to the default output
#   python audio_loop.py --out "AirPods"      # any substring of an output device name
# subtitles.py plugs in via `on_audio` (feeds speech-to-text) and `voice` (English dub mixed on top,
# with the call audio lowered while it plays).
import argparse
import subprocess
import sys
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd

SR = 48000
BLOCK = 480  # 10 ms
DUCK_LEVEL = 0.2   # call audio volume while the English voice is speaking
RAMP_BLOCKS = 8    # a full-scale volume change takes 80 ms, so ducking doesn't click
FADE_OUT_S = 0.3   # an interrupted translation fades out over this long
LOUD = 0.01        # output peak above which the speakers count as making sound (walkie-talkie mode)


def find_device(name, kind):
    for i, d in enumerate(sd.query_devices()):
        if name.lower() in d["name"].lower() and d[f"max_{kind}_channels"] > 0:
            return i
    sys.exit(f"No {kind} device matching {name!r}. Devices:\n{sd.query_devices()}")


class VoiceBuffer:
    """Queue of spoken clips (48 kHz mono float32) that the audio callback plays back to back."""

    def __init__(self):
        self.clips = deque()  # [samples, position, on_start callback or None, deadline (monotonic) or None]
        self.fading = False    # the queue is just the tail of an interrupted clip: play it out even while held
        self.lock = threading.Lock()

    def pending_seconds(self):
        with self.lock:
            return sum(len(c[0]) - c[1] for c in self.clips) / SR

    def active(self):
        return bool(self.clips)

    def playing(self):
        """A clip is part-way through (not just queued)."""
        with self.lock:
            return bool(self.clips) and self.clips[0][1] > 0

    def fade_out(self):
        """The listener started talking: fade the current clip out over FADE_OUT_S and drop everything queued.
        Returns True if something was cut."""
        with self.lock:
            if not self.clips:
                return False
            samples, pos = self.clips[0][0], self.clips[0][1]
            tail = samples[pos:pos + int(FADE_OUT_S * SR)] if pos > 0 else samples[:0]
            self.clips.clear()
            if len(tail):
                self.clips.append([tail * np.linspace(1, 0, len(tail), dtype=np.float32), 0, None, None])
                self.fading = True
            return True

    def push(self, samples, on_start=None, deadline=None):
        """`deadline`: if the clip hasn't started by then (e.g. held while the listener talked), it's dropped."""
        with self.lock:
            self.fading = False
            self.clips.append([samples.astype(np.float32), 0, on_start, deadline])

    def pull(self, n):
        out = np.zeros(n, dtype=np.float32)
        filled = 0
        with self.lock:
            while filled < n and self.clips:
                clip = self.clips[0]
                samples, pos, on_start, deadline = clip
                if pos == 0 and deadline is not None and time.monotonic() > deadline:
                    self.clips.popleft()  # too stale to say now; the subtitle already showed it
                    continue
                if pos == 0 and on_start:
                    on_start()  # first sample of this clip is about to play
                    clip[2] = None
                take = min(n - filled, len(samples) - pos)
                out[filled:filled + take] = samples[pos:pos + take]
                filled += take
                clip[1] = pos + take
                if clip[1] >= len(samples):
                    self.clips.popleft()
        return out


class AudioLoop:
    """Plays call audio (or a recording, via `source`) to `out_dev`, with the English voice mixed on top.

    out_dev=None runs on a timer with no sound device at all (for tests).
    """

    def __init__(self, in_dev, out_dev, on_audio=None, source=None, original=1.0, duck=DUCK_LEVEL):
        self.in_dev, self.out_dev = in_dev, out_dev
        self.original = original  # volume of the input between English lines; 0 = only the English voice is heard
        self.duck_level = duck    # ...and while an English line plays (never louder than `original`)
        self.hold = None      # callable: True -> don't start/continue the voice now (the listener is talking)
        self.gate = None      # callable: True -> treat the input as silence (walkie-talkie: our speakers are playing)
        self.on_output = None  # callable(mix, voice): taps what goes out, for tests
        self.last_loud = 0.0   # monotonic time the output last made sound
        self.on_audio = on_audio
        self.source, self.source_pos = source, 0
        self.source_done = threading.Event()  # set when `source` has played to the end
        self.stop = threading.Event()         # set to end run()
        self.voice = VoiceBuffer()
        self.gain = original
        self.level = 0.0

    def set_original(self, level):
        """Change the between-lines volume (e.g. 1.0 while someone speaks the listener's own language)."""
        self.original = level

    def sounding(self, within=0.3):
        """The output made sound in the last `within` seconds."""
        return time.monotonic() - self.last_loud < within

    def _mix(self, mono, frames):
        if self.gate and self.gate():
            mono = np.zeros_like(mono)
        self.level = float(np.abs(mono).max()) if len(mono) else 0.0
        if self.on_audio:
            self.on_audio(mono.copy())
        held = bool(self.hold and self.hold()) and not self.voice.fading  # a fade-out always finishes at once
        voicing = self.voice.active() and not held
        # Move the call volume one step toward its target each block, fading within the block.
        target = min(self.duck_level, self.original) if voicing else self.original
        step = 1.0 / RAMP_BLOCKS
        new_gain = max(target, self.gain - step) if target < self.gain else min(target, self.gain + step)
        ramp = np.linspace(self.gain, new_gain, frames, dtype=np.float32)
        self.gain = new_gain
        voice = self.voice.pull(frames) if voicing else np.zeros(frames, dtype=np.float32)
        mix = np.clip(mono * ramp + voice, -1, 1)
        if len(mix) and float(np.abs(mix).max()) > LOUD:
            self.last_loud = time.monotonic()
        if self.on_output:
            self.on_output(mix, voice)
        return mix

    def _next_source_block(self, frames):
        block = self.source[self.source_pos:self.source_pos + frames]
        self.source_pos += frames
        if len(block) < frames:
            block = np.pad(block, (0, frames - len(block)))
            if self.source_pos >= len(self.source) + SR:  # 1 s of silence after the end
                self.source_done.set()
        return block

    def _duplex_callback(self, indata, outdata, frames, time_info, status):
        outdata[:] = self._mix(indata.mean(axis=1), frames)[:, None]  # same signal on both channels

    def _output_callback(self, outdata, frames, time_info, status):
        outdata[:] = self._mix(self._next_source_block(frames), frames)[:, None]

    def run(self, meter=True):
        if self.source is not None and self.out_dev is None:
            # Silent clock: same timing as a real device, nothing audible.
            start, n = time.monotonic(), 0
            while not self.stop.is_set():
                self._mix(self._next_source_block(BLOCK), BLOCK)
                n += 1
                time.sleep(max(0.0, start + n * BLOCK / SR - time.monotonic()))
            return
        if self.source is not None:
            # Stereo out: a 1-channel stream on a 2-channel device can play from the left side only.
            stream = sd.OutputStream(device=self.out_dev, samplerate=SR, blocksize=BLOCK, channels=2,
                                     dtype="float32", callback=self._output_callback)
        else:
            in_channels = min(2, sd.query_devices(self.in_dev)["max_input_channels"])  # the MacBook mic is mono
            stream = sd.Stream(device=(self.in_dev, self.out_dev), samplerate=SR, blocksize=BLOCK,
                               channels=(in_channels, 2), dtype="float32", callback=self._duplex_callback)
        with stream:
            if meter:
                print("Passing call audio through. Ctrl+C to stop.")
            while not self.stop.is_set():
                sd.sleep(100)
                if meter:
                    bar = "#" * int(min(self.level, 1) * 40)
                    print(f"\rlevel |{bar:<40}|", end="", flush=True)


def check_volume():
    """When BlackHole is the system output, the Mac volume slider scales what goes into it."""
    if "BlackHole" in sd.query_devices(sd.default.device[1])["name"]:
        vol = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                             capture_output=True, text=True).stdout.strip()
        if vol.isdigit() and int(vol) < 100:
            print(f"Warning: Mac volume is {vol}%, which shrinks the call audio going into BlackHole. "
                  "Turn it to 100% (your speakers/headphones keep their own volume).")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", default="BlackHole 2ch")
    p.add_argument("--out", default=None, help="output device name (default: system default, must not be BlackHole)")
    a = p.parse_args()
    in_dev = find_device(a.inp, "input")
    out_dev = find_device(a.out, "output") if a.out else sd.default.device[1]
    if "BlackHole" in sd.query_devices(out_dev)["name"]:
        sys.exit("Output is BlackHole, which would feed back into itself. Pass --out \"MacBook Air Speakers\" or your headphones.")
    check_volume()
    try:
        AudioLoop(in_dev, out_dev).run()
    except KeyboardInterrupt:
        print()

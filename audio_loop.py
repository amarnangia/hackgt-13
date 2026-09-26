# Step 1 of plan.md: WhatsApp call audio -> BlackHole -> this script -> headphones.
# Set WhatsApp's speaker (or the Mac's system output) to "BlackHole 2ch", then run:
#   python audio_loop.py                      # plays to the default output
#   python audio_loop.py --out "AirPods"      # any substring of an output device name
# Later steps plug in via `on_audio` (feeds speech-to-text) and `duck` (lowers the original voice while dubbing).
import argparse
import queue
import subprocess
import sys

import numpy as np
import sounddevice as sd

SR = 48000
BLOCK = 480  # 10 ms


def find_device(name, kind):
    for i, d in enumerate(sd.query_devices()):
        if name.lower() in d["name"].lower() and d[f"max_{kind}_channels"] > 0:
            return i
    sys.exit(f"No {kind} device matching {name!r}. Devices:\n{sd.query_devices()}")


class AudioLoop:
    def __init__(self, in_dev, out_dev, on_audio=None):
        self.in_dev, self.out_dev = in_dev, out_dev
        self.on_audio = on_audio
        self.gain = 1.0    # original call audio volume; set lower to duck under TTS
        self.level = 0.0
        self.tts = queue.Queue()  # float32 mono blocks mixed on top of the call audio

    def duck(self, on, amount=0.2):
        self.gain = amount if on else 1.0

    def _callback(self, indata, outdata, frames, time, status):
        mono = indata.mean(axis=1)
        self.level = float(np.abs(mono).max())
        if self.on_audio:
            self.on_audio(mono.copy())
        mix = mono * self.gain
        try:
            mix = mix + self.tts.get_nowait()[:frames]
        except queue.Empty:
            pass
        outdata[:] = np.clip(mix, -1, 1)[:, None]

    def run(self):
        with sd.Stream(device=(self.in_dev, self.out_dev), samplerate=SR, blocksize=BLOCK,
                       channels=(2, 2), dtype="float32", callback=self._callback):
            print("Passing call audio through. Ctrl+C to stop.")
            while True:
                sd.sleep(100)
                bar = "#" * int(min(self.level, 1) * 40)
                print(f"\rlevel |{bar:<40}|", end="", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", default="BlackHole")
    p.add_argument("--out", default=None, help="output device name (default: system default, must not be BlackHole)")
    a = p.parse_args()
    in_dev = find_device(a.inp, "input")
    out_dev = find_device(a.out, "output") if a.out else sd.default.device[1]
    if "BlackHole" in sd.query_devices(out_dev)["name"]:
        sys.exit("Output is BlackHole, which would feed back into itself. Pass --out \"MacBook Air Speakers\" or your headphones.")
    # When BlackHole is the system output, the Mac volume slider scales what goes into it.
    if "BlackHole" in sd.query_devices(sd.default.device[1])["name"]:
        vol = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                             capture_output=True, text=True).stdout.strip()
        if vol.isdigit() and int(vol) < 100:
            print(f"Warning: Mac volume is {vol}%, which shrinks the call audio going into BlackHole. "
                  "Turn it to 100% (your speakers/headphones keep their own volume).")
    try:
        AudioLoop(in_dev, out_dev).run()
    except KeyboardInterrupt:
        print()

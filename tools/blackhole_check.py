# Check that audio sent to BlackHole reaches Python.
# Usage: python tools/blackhole_check.py [seconds] [--play]
#   --play  also play what BlackHole hears on the Mac's speakers/headphones
import sys, numpy as np, sounddevice as sd

secs = float(next((a for a in sys.argv[1:] if not a.startswith("-")), 10))
play = "--play" in sys.argv

def find(name, kind):
    for i, d in enumerate(sd.query_devices()):
        if name.lower() in d["name"].lower() and d[f"max_{kind}_channels"] > 0:
            return i
    sys.exit(f"no {kind} device matching {name!r}; run: python -c 'import sounddevice as sd; print(sd.query_devices())'")

src = find("BlackHole", "input")
dst = find("Speakers", "output") if play else None  # swap "Speakers" for your headphones' name
peak = 0.0

def cb(indata, outdata, frames, t, status):
    global peak
    level = float(np.sqrt(np.mean(indata**2)))
    peak = max(peak, level)
    print(f"\r{'#' * min(50, int(level * 300)):<50} {level:.4f}", end="", flush=True)
    if outdata is not None:
        outdata[:] = indata

print(f"listening on BlackHole for {secs:.0f}s - play something now")
kw = dict(samplerate=48000, channels=2, callback=cb)
if play:
    stream = sd.Stream(device=(src, dst), **kw)
else:
    stream = sd.InputStream(device=src, callback=lambda i, f, t, s: cb(i, None, f, t, s), samplerate=48000, channels=2)
with stream:
    sd.sleep(int(secs * 1000))
print(f"\npeak level {peak:.4f} -> {'OK, audio is reaching BlackHole' if peak > 0.001 else 'SILENT: check the output device'}")

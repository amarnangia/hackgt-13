# End-to-end check of --two-way on a scripted call between a Telugu speaker (you) and an English speaker (them),
# with interruptions and talking over each other. Builds both sides' audio (Telugu: the translator's MMS voice;
# English: Kokoro), runs subtitles.py on them, records what each person heard and checks:
#   - roles: you are detected as the Telugu speaker
#   - each line is translated towards its listener (your Telugu -> English, their English -> Telugu), and Telugu
#     from them reaches you untranslated at full volume
#   - no translation plays to someone while they're talking; an interruption fades it out
#   - the original voice sits at ~20% under/around translations
#   python tools/check_two_way.py            (about 2 minutes; needs .venv-translate and a Muse key)
#   python tools/check_two_way.py --swap     the same call with *them* as the Telugu speaker: the app starts out
#                                            assuming it's you, so this checks it works out the roles
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "tools", "two_way_run")
SR = 24000

# (side, start second, language, text). "me" is you (Telugu), "them" the English speaker.
SCRIPT = [
    ("me", 0.5, "te", "నేను ఈ రోజు మీ కోసం పులిహోర చేశాను."),
    ("them", 8.0, "en", "Wow, that sounds delicious. Thank you so much."),
    ("me", 16.0, "te", "నిన్న నేను ఆటోలో గుడికి వెళ్ళాను. అక్కడ చాలా మంది ఉన్నారు."),
    ("them", None, "en", "Wait, which temple did you go to?"),  # None: right as your line ends (interrupts it)
    ("them", 30.0, "en", "My exams are next week, so I have been studying a lot every single day."),
    ("me", None, "te", "బాగా చదువుకో, నువ్వు తప్పకుండా పాస్ అవుతావు."),  # interrupts their translation to you
    ("them", 46.0, "te", "నాకు పులిహోర అంటే చాలా ఇష్టం."),  # Telugu from them: you understand it as said
    ("me", 54.0, "te", "సరే, నేను రేపు మళ్ళీ ఫోన్ చేస్తాను."),
    ("them", None, "en", "Okay, talk to you tomorrow, take care and eat well."),  # starts before you finish
]
SWAP = "--swap" in sys.argv
if SWAP:
    SCRIPT = [("them" if side == "me" else "me", *rest) for side, *rest in SCRIPT]
TELUGU = "them" if SWAP else "me"                # the Telugu speaker's side
ENGLISH = "me" if TELUGU == "them" else "them"
NAME = {"me": "you", "them": "them"}
HEARS = {"me": "to_you", "them": "to_them"}      # recordings of what each person heard
INTERRUPT_GAP = {3: 0.9, 5: 1.3, 8: -0.8}  # seconds after the previous line ends that these start


def synth():
    """Speech for each script line: English with Kokoro (main venv), Telugu with the translator's MMS voice."""
    from mlx_audio.tts.utils import load_model
    from subtitles import start_translator
    from translate_server import LocalTranslator

    start_translator("te")
    te = LocalTranslator("te")
    assert te.load_two_way() is None, "English -> Telugu models failed to load"
    kokoro = load_model("mlx-community/Kokoro-82M-bf16")
    clips = []
    for side, _, lang, text in SCRIPT:
        if lang == "te":
            pcm, rate = te.speak(text)
            audio = pcm.astype(np.float32) / 32768
        else:
            audio = np.concatenate([np.asarray(r.audio).reshape(-1) for r in
                                    kokoro.generate(text, voice="am_michael", speed=1.0, lang_code="a")])
            rate = 24000
        loud = np.nonzero(np.abs(audio) > 0.02)[0]  # trim the voices' leading/trailing silence: spans = real speech
        audio = audio[loud[0]:loud[-1] + 1]
        n = int(len(audio) * SR / rate)
        clips.append(np.interp(np.arange(n) * rate / SR, np.arange(len(audio)), audio).astype(np.float32) * 0.6)
    return clips


def build(clips):
    """Place the lines on two tracks; returns (their speech intervals, your speech intervals) in seconds."""
    spans, end = [], 0.0
    for i, ((side, start, _, _), clip) in enumerate(zip(SCRIPT, clips)):
        start = start if start is not None else end + INTERRUPT_GAP[i]
        end = start + len(clip) / SR
        spans.append((side, start, end))
    length = int((max(e for _, _, e in spans) + 12) * SR)
    tracks = {"me": np.zeros(length, np.float32), "them": np.zeros(length, np.float32)}
    for (side, start, _), clip in zip(spans, clips):
        a = int(start * SR)
        tracks[side][a:a + len(clip)] += clip
    os.makedirs(OUT, exist_ok=True)
    for side, audio in tracks.items():
        sf.write(os.path.join(OUT, f"{side}.wav"), audio, SR, subtype="PCM_16")
    return spans


def energy(audio, sr, a, b):
    seg = audio[int(a * sr):int(b * sr)]
    return float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0


def main():
    spans = build(synth())
    for side, a, b in spans:
        print(f"  script: {side:4} {a:5.1f}-{b:5.1f}s")
    log = os.path.join(ROOT, "latency_log.jsonl")
    before = open(log).read() if os.path.exists(log) else None
    open(log, "w").close()
    try:
        run = subprocess.run([sys.executable, "subtitles.py", "--two-way", "--file", os.path.join(OUT, "them.wav"),
                              "--my-file", os.path.join(OUT, "me.wav"), "--out", "none", "--no-story", "--no-open",
                              "--no-prompts", "--record-out", OUT], cwd=ROOT, capture_output=True, text=True,
                             env={**os.environ, "OVERLAY_PORT": "8781"})
        rows = [json.loads(line) for line in open(log)]
    finally:
        if before is not None:
            open(log, "w").write(before)
    output = run.stdout + run.stderr
    open(os.path.join(OUT, "run.log"), "w").write(output)
    print("\n".join(line for line in output.splitlines() if "->" in line or "Roles" in line or "faded" in line
                    or "ignored" in line or "Traceback" in line or "Error" in line))
    checks = []
    check = lambda ok, what: checks.append((ok, what))

    check(run.returncode == 0, "the app ran without errors")
    if SWAP:
        check("Roles decided" in output and "Grandma speaks Telugu" in output,
              "the app works out that they're the Telugu speaker")
    else:
        check("Roles to start: you speak Telugu" in output, "you start as the Telugu speaker")
    check("Roles changed" not in output, "the roles never flip back the wrong way")
    # A line said before the roles were known is translated again once they are: judge each line by its last version.
    final = {}
    for r in rows:
        final[(r.get("side"), r["text"])] = r
    t_rows = [r for (side, _), r in final.items() if side == TELUGU and r["route"] != "english"]
    e_rows = [r for (side, _), r in final.items() if side == ENGLISH]
    check(t_rows and all(r["to"] == "en" for r in t_rows),
          f"the Telugu speaker's Telugu is translated to English ({len(t_rows)} lines)")
    e_en = [r for r in e_rows if r["route"] == "english"]
    check(e_en and all(r["to"] == "te" for r in e_en), f"the English speaker's English is translated to Telugu ({len(e_en)} lines)")
    check(all(any("\u0C00" <= ch <= "\u0C7F" for ch in r["english"]) for r in e_en), "...and the result is Telugu script")
    e_te = [r for r in e_rows if r["route"] == "native"]
    check(e_te and all(r["to"] is None for r in e_te), "Telugu from the English speaker reaches the Telugu speaker untranslated")

    heard = {f"{HEARS[s]}_{k}": sf.read(os.path.join(OUT, f"{HEARS[s]}_{k}.wav")) for s in HEARS for k in ("mix", "voice")}
    src = {side: sf.read(os.path.join(OUT, f"{side}.wav")) for side in ("me", "them")}
    # No translation while the listener talks. Allow 1.1 s from when they start: Muse reports speech ~0.4-0.7 s in,
    # then the fade takes 0.3 s.
    for listener in ("me", "them"):
        audio, sr = heard[f"{HEARS[listener]}_voice"]
        worst = max((energy(audio, sr, a + 1.1, b) for side, a, b in spans if side == listener and b - a > 1.2), default=0)
        check(worst < 0.005, f"no translation plays to {NAME[listener]} while {NAME[listener]} talk (loudest {worst:.4f})")
    check(output.count("faded out the translation") >= 2, f"interruptions faded translations out "
                                                         f"({output.count('faded out the translation')} times)")
    # Volumes: the original at ~20% while it's the other language; the listener's own language at full volume.
    mix, sr = heard[f"{HEARS[ENGLISH]}_mix"]
    a, b = [(a, b) for side, a, b in spans if side == TELUGU][-1]
    ratio = energy(mix, sr, a + 0.2, b) / max(energy(src[TELUGU][0], SR, a + 0.2, b), 1e-9)
    check(0.1 < ratio < 0.3, f"Telugu reaches the English speaker at ~20% under the English (measured {ratio:.0%})")
    mix, sr = heard[f"{HEARS[TELUGU]}_mix"]
    a, b = next((a, b) for (side, a, b), line in zip(spans, SCRIPT) if side == ENGLISH and line[2] == "te")
    ratio = energy(mix, sr, a + 1.2, b) / max(energy(src[ENGLISH][0], SR, a + 1.2, b), 1e-9)
    check(ratio > 0.8, f"Telugu from the English speaker reaches the Telugu speaker at full volume (measured {ratio:.0%})")
    last = next(i for i, line in enumerate(SCRIPT) if line[1] == 54.0)
    held_end = spans[last + 1][2]
    audio, sr = heard[f"{HEARS[ENGLISH]}_voice"]
    check(energy(audio, sr, held_end, held_end + 6) > 0.005,
          "a line held while the listener talked still plays after they stop")

    print()
    for ok, what in checks:
        print(f"{'✓' if ok else '✗'} {what}")
    print(f"{sum(ok for ok, _ in checks)}/{len(checks)} checks passed (recordings in {os.path.relpath(OUT, ROOT)}/)")
    sys.exit(0 if all(ok for ok, _ in checks) else 1)


if __name__ == "__main__":
    main()

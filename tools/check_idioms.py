# How well sayings (సామెతలు) are caught. Idioms are found by exact wording from lexicon.json (27 of them), so this
# checks the two ways that can fail:
#   1. spoken: each listed saying, inside a sentence, spoken by the local Telugu voice (MMS, from translate_server.py)
#      and transcribed by Muse Voice Transcribe as on a call; is it still found in what Muse wrote?
#   2. not listed: common sayings that aren't in lexicon.json; are they found (no), and does the translation give the
#      meaning or a literal reading?
#   python tools/check_idioms.py            # needs translate_server.py running (subtitles.py starts it) and MODEL_API_KEY
# Synthetic speech is clearer than a real grandmother on a phone line, so part 1 is a best case.
import asyncio
import json
import os
import sys

import numpy as np
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lexicon import Lexicon  # noqa: E402
from muse import transcribe  # noqa: E402

SERVER = "http://localhost:8766"
FRAME = 480  # 20 ms at 24 kHz
# Common sayings that aren't in lexicon.json, with what they mean
UNLISTED = [
    ("అడగనిదే అమ్మైనా పెట్టదు", "even your mother won't feed you unless you ask"),
    ("ఆరోగ్యమే మహాభాగ్యం", "health is wealth"),
    ("తినగ తినగ వేము తియ్యనుండు", "practice makes even the bitter sweet"),
    ("కాకి పిల్ల కాకికి ముద్దు", "every parent thinks their child is the best"),
    ("పేరు గొప్ప ఊరు దిబ్బ", "big name, nothing behind it"),
    ("దూరపు కొండలు నునుపు", "the grass is greener on the other side"),
    ("ఏ ఎండకు ఆ గొడుగు", "changing sides to suit the moment"),
    ("అయ్యవారిని చేయబోతే కోతి అయినట్టు", "a plan that turned out the opposite"),
    ("గుడ్డి కన్నా మెల్ల మేలు", "something is better than nothing"),
    ("అన్నీ ఉన్న విస్తరి అణిగిమణిగి ఉంటుంది", "the truly accomplished are humble"),
]
FRAMES = ["మా అమ్మమ్మ ఎప్పుడూ చెప్పేది, {}.", "అందుకే అంటారు {} అని."]


def speak(text):
    r = requests.post(f"{SERVER}/speak", json={"text": text, "lang": "te"}, timeout=60)
    r.raise_for_status()
    rate = int(r.headers["X-Sample-Rate"])
    audio = np.frombuffer(r.content, dtype=np.int16).astype(np.float32)
    n = int(len(audio) * 24000 / rate)
    audio = np.interp(np.arange(n) * rate / 24000, np.arange(len(audio)), audio)
    silence = np.zeros(24000 * 2)  # 2 s after, so Muse ends the utterance
    return np.concatenate([np.zeros(4800), audio, silence]).astype(np.int16).tobytes()


async def heard(pcm):
    """What Muse writes for this audio, fed in real time like a call."""
    q = asyncio.Queue()

    async def feed():
        for i in range(0, len(pcm), FRAME * 2):
            q.put_nowait(pcm[i:i + FRAME * 2])
            await asyncio.sleep(0.02)
        q.put_nowait(None)

    feeder = asyncio.create_task(feed())
    said = []
    async for ev in transcribe(q, "te", "PCM_24KHZ"):
        if ev.get("type") == "speechComplete" and ev.get("transcript"):
            said.append(ev["transcript"])
    await feeder
    return " ".join(said)


async def spoken(lex, idioms):
    sem = asyncio.Semaphore(6)
    cases = [(e, f.format(e["forms"][0])) for e in idioms for f in FRAMES]

    async def one(e, sentence):
        async with sem:
            pcm = await asyncio.to_thread(speak, sentence)
            text = await heard(pcm)
            found = any(h["id"] == e["id"] for h in lex.find(text, "te", roman=True))
            return e, sentence, text, found

    return await asyncio.gather(*(one(e, s) for e, s in cases))


def main():
    lex = Lexicon()
    idioms = [e for e in lex.entries["te"] if e.get("category") == "idiom"]
    typed = sum(any(h["id"] == e["id"] for h in lex.find(e["forms"][0], "te")) for e in idioms)
    print(f"typed exactly as listed: {typed}/{len(idioms)} found")

    results = asyncio.run(spoken(lex, idioms))
    ok = sum(found for *_, found in results)
    print(f"spoken, through Muse, exact matching: {ok}/{len(results)} found ({ok / len(results):.0%}); "
          f"{sum(all(f for x, _, _, f in results if x['id'] == e['id']) for e in idioms)}/{len(idioms)} idioms found both times")
    # sayings.py: fuzzy matching, confirmed by Laya's trained check
    import sayings
    from decide import Decider
    judge = sayings.SayingJudge(Decider(), sayings.SayingFinder(sayings.load_sayings(lex)))
    new = [(e, text, any(x["id"] == e["id"] for x, _ in judge.find(text, "te"))) for e, _, text, _ in results]
    ok = sum(f for *_, f in new)
    print(f"spoken, through Muse, sayings.py:      {ok}/{len(new)} found ({ok / len(new):.0%})"
          f"{'' if judge.head else '  (no trained head yet: fuzzy only)'}")
    for e, text, found in new:
        if not found:
            print(f"  missed {e['id']:18} Muse wrote: {text}")

    print("\nnot in lexicon.json:")
    for saying, meaning in UNLISTED:
        hits = [h["id"] for h in lex.find(saying, "te") if h.get("category") == "idiom"]
        english = requests.post(SERVER, json={"text": saying, "lang": "te"}, timeout=30).json()["english"]
        print(f"  found: {'yes' if hits else 'no ':3}  translated: {english!r:55}  means: {meaning}")


if __name__ == "__main__":
    main()

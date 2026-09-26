# What the overlay gets for each of her lines, and how fast: runs Telugu lines through the real engine (local
# translator, Laya, pictures, Curious?, topic words, "ask her"), without audio, a microphone or the voice, and times
# every message from the moment the line is cut (the speech service's delay isn't included).
#   python tools/check_decisions.py              # the demo call (demo.md) plus lines that test what gets translated
#   python tools/check_decisions.py --verbose    # also print what each message says
# Runs in a temporary folder, so your word progress and logs aren't touched; the local translator must be running
# (subtitles.py starts it; or .venv-translate/bin/python translate_server.py).
import argparse
import json
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# (what she says, what we expect: route, words kept in Telugu is checked by --keep)
LINES = [
    "నాన్నా, బాగున్నావా? అన్నం తిన్నావా?",
    "నిన్న సంక్రాంతికి గవ్వలు, అరిసెలు చేశాను.",
    "ఈ రోజు పులిహోర చేశాను, నీకు చాలా ఇష్టం కదా?",
    "పులిహోర చాలా బాగా వచ్చింది.",
    "మా చిన్నప్పుడు భోగి మంటలు వేసేవాళ్ళం, గంగిరెద్దులు ఇంటికి వచ్చేవి.",
    "నోరు మంచిదైతే ఊరు మంచిది అని మా అమ్మ చెప్పేది.",
    "మీ తాతయ్య ఎన్టీఆర్ సినిమాలు చాలా ఇష్టపడేవారు.",
    "ఎప్పుడు వస్తావు నాన్నా? జాగ్రత్తగా ఉండు, బాగా చదువుకో.",
    # what gets translated: English she says, Telugu in English letters, a mix
    "Okay, very good, very good.",
    "Bangaram, pulihora tinnava?",
    "Your uncle is coming next week, పెద్ద పండగ కదా.",
    # only words they know (--known sare,ninna): shown, not voiced
    "సరే, సరే.",
]
KINDS = ["english", "details", "intent", "topic", "curious", "reply", "picture", "offer"]


class RecordingHub:
    def __init__(self):
        self.clients, self.welcome, self.current, self.on_message = set(), [], {}, None
        self.messages = []

    def broadcast(self, msg):
        self.messages.append((time.monotonic(), msg))


class LineDone:
    """Stands in for the story keeper: the engine calls add_line() when it's done with a line."""
    def __init__(self):
        self.done = threading.Event()

    def span(self, audio_ms):
        return None, None

    def on_event(self, ev):
        pass

    def add_line(self, **line):
        self.done.set()


class OfferLog:
    """Stands in for the "ask her" prompter: records when each question is ready (it shows at her next pause)."""
    def __init__(self, hub):
        self.hub = hub

    def on_event(self, ev):
        pass

    def offer(self, question):
        if question:
            self.hub.messages.append((time.monotonic(), {"type": "offer", **question}))

    def on_line(self, *a):
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--keep-at", type=float, default=0.4, help="as in the demo: a word stays in Telugu from its 2nd mention")
    p.add_argument("--known", default="sare", help="word-list ids to start as known, comma-separated")
    args = p.parse_args()

    import muse
    try:
        os.environ.setdefault("MODEL_API_KEY", muse.api_key())  # read .env before leaving the repo
    except SystemExit:
        print("(no MODEL_API_KEY: lines in English letters get word glosses only)")
    os.chdir(tempfile.mkdtemp(prefix="weave-check-"))  # progress.json, logs: throwaway
    import subtitles
    from curious import Curious
    from decide import Decider
    from pictures import PictureFinder

    hub = RecordingHub()
    cap = subtitles.Captioner("te", "local", args.keep_at, hub=hub)
    if not isinstance(cap.translate, subtitles.LocalTranslator):
        sys.exit("Start the local translator first: .venv-translate/bin/python translate_server.py")
    cap.drafts = None
    for wid in filter(None, args.known.split(",")):
        cap.progress.words[wid] = {"p": 0.9, "t": time.time(), "hl": 7.0}
    cap.decider = Decider()
    cap.pictures = PictureFinder(cap.decider)
    cap.pictures._nouns("warm up the noun finder")
    cap.curious = Curious(cap.decider, cap.progress, cap.progress.keep_at)
    cap.prompter = OfferLog(hub)
    cap.show_topic("greetings")
    cap.translate("నమస్కారం")  # warm up

    rows = []
    for sentence in LINES:
        cap.recorder = LineDone()
        start = len(hub.messages)
        t0 = time.monotonic()
        cap._submit(sentence, None, marks={"spoken": None, "recognized": t0, "cut": t0, "audio_ms": None})
        cap.recorder.done.wait(30)
        time.sleep(0.3)  # anything sent after the line was recorded
        got = hub.messages[start:]
        first = {}
        for t, m in got:
            first.setdefault(m["type"], (t - t0, m))
            if m["type"] == "details" and m.get("intent"):
                first.setdefault("intent", (t - t0, m))  # the "Asked you" / "Request" tag
            if m["type"] == "curious" and any(q["kind"] == "reply" for q in m["questions"]):
                first.setdefault("reply", (t - t0, m))   # how to answer her, in Telugu
        rows.append((sentence, first))
        eng = first.get("english", (0, {}))[1]
        print(f"\n{sentence}\n  -> {eng.get('text')}   [{eng.get('route')}"
              + (f", kept {', '.join(k['telugu'] for k in eng.get('kept', []))}" if eng.get("kept") else "") + "]")
        print("  " + "  ".join(f"{k} {first[k][0] * 1000:4.0f}ms" for k in KINDS if k in first))
        if args.verbose:
            for t, m in got:
                if m["type"] in ("curious", "topic", "picture", "offer", "details"):
                    brief = {k: v for k, v in m.items() if k not in ("image", "description")}
                    print(f"    {(t - t0) * 1000:5.0f}ms {json.dumps(brief, ensure_ascii=False)[:220]}")
    print("\nmedian ms from the line being cut:")
    for k in KINDS:
        vals = sorted(r[1][k][0] * 1000 for r in rows if k in r[1])
        if vals:
            print(f"  {k:8} {vals[len(vals) // 2]:5.0f}  (max {vals[-1]:.0f}, {len(vals)} lines)")
    sys.stdout.flush()
    os._exit(0)  # the translator's and Laya's threads


if __name__ == "__main__":
    main()

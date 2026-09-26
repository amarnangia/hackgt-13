# Which of the words from your calls do you actually know? A short quiz whose answers tune the word-knowledge model
# (tools/fit_progress.py). Asks about words that came up on calls (progress_log.jsonl), then shows what each means.
#   python tools/quiz.py            # up to 20 words
#   python tools/quiz.py -n 40
import argparse
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lexicon import Lexicon  # noqa: E402
from progress import Progress  # noqa: E402

LOG, QUIZ = os.path.join(ROOT, "progress_log.jsonl"), os.path.join(ROOT, "quiz.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20, help="how many words")
    a = ap.parse_args()
    if not os.path.exists(LOG):
        sys.exit("No progress_log.jsonl yet: it fills up during calls (subtitles.py).")
    seen = {json.loads(l)["id"] for l in open(LOG) if l.strip()}
    lexicon = Lexicon()
    progress = Progress(lexicon, "te", path=os.path.join(ROOT, "progress.json"))
    words = [w for w in seen if w in progress.entries]
    random.shuffle(words)
    print(f"{min(a.n, len(words))} words from your calls. Answer honestly: y = I know what it means, n = I don't, s = skip.\n")
    answered = 0
    for wid in words[: a.n]:
        e = progress.entries[wid]
        reply = input(f"  {e['forms'][0].strip(' ,.^')}  ({e['roman'].strip(' ,')})   do you know it? [y/n/s] ").strip().lower()[:1]
        meaning = e.get("translate_as") or e.get("note", "")
        if reply in ("y", "n"):
            with open(QUIZ, "a") as f:
                f.write(json.dumps({"t": round(time.time(), 1), "id": wid, "knows": reply == "y"}) + "\n")
            answered += 1
            if reply == "n":
                progress.observe(wid, "answer")  # you've now seen what it means
        print(f"      = {meaning}\n")
    print(f"Saved {answered} answers to quiz.jsonl. Then: python tools/fit_progress.py")


if __name__ == "__main__":
    main()

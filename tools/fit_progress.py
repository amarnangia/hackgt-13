# Tune the word-knowledge model (progress.py) to how well the grandkid actually knows words: replays the logged
# signals from calls (progress_log.jsonl) up to each quiz answer (quiz.jsonl, from tools/quiz.py) under many settings,
# and keeps the settings whose probabilities best predict the answers (highest log-likelihood).
#   python tools/fit_progress.py           # compare settings
#   python tools/fit_progress.py --save    # use the best ones from now on (progress_settings.json, per person)
import argparse
import itertools
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lexicon import Lexicon  # noqa: E402
from progress import HALF_LIFE_DAYS, Progress  # noqa: E402

GRID = {"prior_scale": [0.5, 0.75, 1.0, 1.5, 2.0], "learn_scale": [0.5, 1.0, 1.5, 2.0],
        "evidence_scale": [0.5, 1.0, 1.5], "half_life": [3.0, 7.0, 14.0, 30.0]}
CURRENT = {"prior_scale": 1.0, "learn_scale": 1.0, "evidence_scale": 1.0, "half_life": HALF_LIFE_DAYS}


def load(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


def predictions(lexicon, events, quiz, settings):
    """P(knows) for each quiz answer, from the events logged before it."""
    out = []
    for when in sorted({q["t"] for q in quiz}):
        model = Progress(lexicon, "te", path=None, **settings).replay([e for e in events if e["t"] < when])
        out += [(model.probability(q["id"], now=when), q["knows"]) for q in quiz if q["t"] == when]
    return out


def old_rule(events, quiz):
    """The rule before the model: known once heard at least once before (LEARN_AFTER = 1)."""
    return [(0.9 if any(e["id"] == q["id"] and e["event"] == "heard" and e["t"] < q["t"] for e in events) else 0.1, q["knows"])
            for q in quiz]


def score(preds):
    eps = 1e-3
    ll = sum(math.log(max(eps, p if y else 1 - p)) for p, y in preds) / len(preds)
    acc = sum((p >= 0.5) == y for p, y in preds) / len(preds)
    brier = sum((p - y) ** 2 for p, y in preds) / len(preds)
    return ll, acc, brier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=os.path.join(ROOT, "progress_log.jsonl"))
    ap.add_argument("--quiz", default=os.path.join(ROOT, "quiz.jsonl"))
    ap.add_argument("--save", action="store_true", help="use the best settings from now on (progress_settings.json)")
    a = ap.parse_args()
    events, quiz = load(a.log), load(a.quiz)
    if len(quiz) < 10:
        sys.exit(f"Only {len(quiz)} quiz answers; take tools/quiz.py (20+ answers) after a few calls, then run this again.")
    lexicon = Lexicon()
    fmt = lambda name, s: f"  {name:28} log-likelihood {s[0]:+.3f}   accuracy {s[1]:.0%}   Brier {s[2]:.3f}"
    print(f"{len(events)} signals, {len(quiz)} quiz answers ({sum(q['knows'] for q in quiz)} known)\n")
    print(fmt("old rule (heard once)", score(old_rule(events, quiz))))
    current = score(predictions(lexicon, events, quiz, CURRENT))
    print(fmt("current settings", current))
    best, best_score = CURRENT, current
    for values in itertools.product(*GRID.values()):
        settings = dict(zip(GRID, values))
        s = score(predictions(lexicon, events, quiz, settings))
        if s[0] > best_score[0]:
            best, best_score = settings, s
    print(fmt("best settings", best_score))
    print("\n  " + ", ".join(f"{k} = {v}" for k, v in best.items()))
    if len(quiz) < 40:
        print(f"\n  (With {len(quiz)} answers this is a rough fit; more quizzes after more calls make it trustworthy.)")
    if a.save:
        json.dump(best, open(os.path.join(ROOT, "progress_settings.json"), "w"), indent=1)
        print("\n  Saved to progress_settings.json: subtitles.py uses them from the next call.")


if __name__ == "__main__":
    main()

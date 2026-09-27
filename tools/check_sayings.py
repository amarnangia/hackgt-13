# How well sayings.py catches sayings, idioms, slang and cultural references:
#   caught       lines that use a saying never trained on (tools/data/sayings_test.jsonl): is it found?
#   literal      lines that only share its words: is it (wrongly) found?
#   everyday     real lines from our calls (latency_log.jsonl, calls/): how often is any saying (wrongly) found?
# for fuzzy matching alone and for fuzzy matching + Laya's trained check.
#   python tools/check_sayings.py [--split val]     # val: the training run's held-out sayings (for picking settings)
import argparse
import glob
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import sayings  # noqa: E402
from lexicon import Lexicon  # noqa: E402

TELUGU = re.compile("[ఀ-౿]")


def everyday():
    """Real lines from our calls, by language."""
    lines = []
    if os.path.exists(os.path.join(ROOT, "latency_log.jsonl")):
        lines += [json.loads(l).get("text", "") for l in open(os.path.join(ROOT, "latency_log.jsonl")) if l.strip()]
    for f in glob.glob(os.path.join(ROOT, "calls", "*", "call.json")):
        lines += [l.get("text") or "" for l in json.load(open(f)).get("lines", [])]
    lines = sorted({l.strip() for l in lines if len(l.split()) >= 3})
    return {"te": [l for l in lines if TELUGU.search(l)], "en": [l for l in lines if not TELUGU.search(l)]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--split", choices=["test", "val"], default="test")
    p.add_argument("--head", default=sayings.HEAD_PATH)
    args = p.parse_args()
    if args.split == "test":
        rows = [json.loads(l) for l in open(os.path.join(ROOT, "tools", "data", "sayings_test.jsonl"))]
    else:  # the same held-out sayings tools/train_sayings.py picks the best epoch on
        rows = [json.loads(l) for l in open(os.path.join(ROOT, "tools", "data", "sayings_train.jsonl"))]
        about = sorted({r["about"] for r in rows})
        random.Random(0).shuffle(about)
        val_ids = set(about[: len(about) // 10])
        rows = [r for r in rows if r["about"] in val_ids]
    uses = [r for r in rows if r["label"] == "yes"]
    literal = [r for r in rows if r["label"] == "no" and r["id"] == r["about"]]
    daily = everyday()

    items = sayings.load_sayings(Lexicon())
    finder = sayings.SayingFinder(items)
    cats = {e["id"]: e.get("category") for entries in items.values() for e in entries}
    judge = None
    if os.path.exists(args.head):
        from decide import Decider
        judge = sayings.SayingJudge(Decider(), finder, head_path=args.head)

    def found(lang, text, with_laya):
        if with_laya and judge:
            return {e["id"] for e, _ in judge.find(text, lang)}
        return {e["id"] for e, _, _ in finder.candidates(text, lang)}

    print(f"{args.split}: {len(uses)} lines using a saying, {len(literal)} literal look-alikes, "
          f"everyday lines: {len(daily['te'])} Telugu, {len(daily['en'])} English")
    for with_laya in ([False, True] if judge else [False]):
        name = "fuzzy + Laya" if with_laya else "fuzzy only"
        for lang in ("te", "en"):
            u = [r for r in uses if r["lang"] == lang]
            li = [r for r in literal if r["lang"] == lang]
            caught = sum(r["about"] in found(lang, r["line"], with_laya) for r in u)
            fooled = sum(r["about"] in found(lang, r["line"], with_laya) for r in li)
            # a cultural reference found in everyday talk ("పులిహోర చేశాను") is right, not a false alarm
            alarms = sum(any(cats.get(i) != "culture" for i in found(lang, t, with_laya)) for t in daily[lang])
            print(f"  {name:13} {lang}: caught {caught}/{len(u)} = {caught / max(len(u), 1):.0%}   "
                  f"literal wrongly caught {fooled}/{len(li)} = {fooled / max(len(li), 1):.0%}   "
                  f"everyday lines with a wrong saying card {alarms}/{len(daily[lang])} = {alarms / max(len(daily[lang]), 1):.0%}")


if __name__ == "__main__":
    main()

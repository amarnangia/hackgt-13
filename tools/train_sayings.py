# Train Laya's decision layers for sayings.py's question ("is this line really using that saying?") on
# tools/data/sayings_train.jsonl (tools/make_saying_data.py). Same recipe as tools/train_reply.py (frozen shared
# encoder, only the retrained layers saved to models/sayings_head.pt, so Laya's other decisions don't change).
# A tenth of the training *sayings* are held out to pick the best epoch; tools/check_sayings.py tests on others.
#   python tools/train_sayings.py [--out /tmp/try.pt] [--lr 3e-4]
import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from sayings import HEAD_PATH, LABELS, QUESTION, state  # noqa: E402
from train_reply import train_head  # noqa: E402


def mined(rows):
    """The wrong candidates the fuzzy matcher actually suggests for each training line, as "no" examples: exactly the
    false alarms Laya has to reject on a call (47% of everyday Telugu lines get one)."""
    from lexicon import Lexicon
    from sayings import SayingFinder, load_sayings, meaning
    finder = SayingFinder(load_sayings(Lexicon()))
    out, seen = [], set()
    for r in rows:
        if (r["line"], r["lang"]) in seen:
            continue
        seen.add((r["line"], r["lang"]))
        wrong = [(e, form) for e, form, _ in finder.candidates(r["line"], r["lang"])
                 if e["id"] != r["about"] or r["label"] == "no" and r["id"] == r["about"]]
        for e, form in wrong[:2]:  # the two likeliest false alarms per line keep training to about an hour
                out.append(dict(r, saying=form, roman=e.get("roman", ""), means=meaning(e), id=e["id"], label="no"))
    print(f"mined {len(out)} wrong candidates from the fuzzy matcher")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train", choices=["scorer", "last", "all"], default="all")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--lr", type=float, default=None)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", default=HEAD_PATH)
    args = p.parse_args()
    rows = [json.loads(line) for line in open(os.path.join(ROOT, "tools", "data", "sayings_train.jsonl"))]
    rows += mined(rows)
    about = sorted({r["about"] for r in rows})
    random.Random(0).shuffle(about)
    val_ids = set(about[: len(about) // 10])
    train = [r for r in rows if r["about"] not in val_ids]
    val = [r for r in rows if r["about"] in val_ids]
    print(f"{len(train)} training examples, {len(val)} validation ({len(val_ids)} held-out sayings)")
    train_head(train, val, QUESTION, LABELS, lambda r: state(r["lang"], r["line"], r["saying"], r["roman"], r["means"]), args)


if __name__ == "__main__":
    main()

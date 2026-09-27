# (An experiment that didn't work: no configuration learned; see sayings.py. Kept to try again, e.g. with an unfrozen
# encoder.) Train Laya's decision layers for sayings.py's question ("is this line really using that saying?") on
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
from sayings import HEAD_PATH, LABELS, QUESTION, match_score, state  # noqa: E402
from train_reply import train_head  # noqa: E402


def mined(rows):
    """The wrong candidates the fuzzy matcher actually suggests for each training line, as "no" examples: exactly the
    false alarms Laya has to reject on a call (47% of everyday Telugu lines get one). Left out: candidates the line
    really contains (score >= 95) and near-copies of the right saying (the same proverb in lexicon.json and
    sayings.json, or one saying's short form): calling those "no" taught Laya contradictions, and it learned nothing."""
    from rapidfuzz import fuzz
    from lexicon import Lexicon
    from sayings import SayingFinder, english_words, load_sayings, meaning, sound
    finder = SayingFinder(load_sayings(Lexicon()))
    right = {r["about"]: r["saying"] for r in rows if r["id"] == r["about"]}
    out, seen = [], set()
    for r in rows:
        if (r["line"], r["lang"]) in seen:
            continue
        seen.add((r["line"], r["lang"]))
        key = sound if r["lang"] == "te" else english_words
        wrong = [(e, form) for e, form, score in finder.candidates(r["line"], r["lang"])
                 if (e["id"] != r["about"] or r["label"] == "no" and r["id"] == r["about"]) and score < 95
                 and (e["id"] == r["about"] or fuzz.ratio(key(form), key(right.get(r["about"], ""))) < 85)]
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
    p.add_argument("--cache", help="keep the encoder's output here, so another run on the same data skips it (~17 min)")
    p.add_argument("--weighted", action="store_true", help="weigh the loss so yes and no count equally overall")
    p.add_argument("--limit", type=int, help="train on this many examples (a quick check)")
    p.add_argument("--lang", default="en", help="en (what sayings.py uses Laya for), te or all")
    args = p.parse_args()
    rows = [json.loads(line) for line in open(os.path.join(ROOT, "tools", "data", "sayings_train.jsonl"))]
    rows += mined(rows)
    for r in rows:  # yes / no -> the question's three options
        r["label"] = "uses_it" if r["label"] in ("yes", "uses_it") else "literal" if r["id"] == r["about"] else "different"
    if args.lang != "all":
        rows = [r for r in rows if r["lang"] == args.lang]
    about = sorted({r["about"] for r in rows})
    random.Random(0).shuffle(about)
    val_ids = set(about[: len(about) // 10])
    train = [r for r in rows if r["about"] not in val_ids]
    val = [r for r in rows if r["about"] in val_ids]
    print(f"{len(train)} training examples ({sum(r['label'] == 'uses_it' for r in train)} uses_it), {len(val)} validation "
          f"({len(val_ids)} held-out sayings)")
    if args.limit:
        random.Random(2).shuffle(train)
        random.Random(3).shuffle(val)
        train, val = train[:args.limit], val[:args.limit // 5]
    train_head(train, val, QUESTION, LABELS, lambda r: state(r["lang"], r["line"], r["saying"], r["roman"], r["means"],
                                                               match_score(r["lang"], r["saying"], r["line"])), args)


if __name__ == "__main__":
    main()

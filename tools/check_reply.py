# How well reply.py tells whether the grandkid understood a kept Telugu word, on hand-written examples
# (tools/data/reply_test.jsonl) whose words are not in the training data.
#   python tools/check_reply.py            # rules, Laya as shipped, Laya with the trained head, and the combination
#   python tools/check_reply.py --wrong    # also list every mistake of the combination (what the app uses)
import argparse
import json
import os
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from reply import HEAD_PATH, LABELS, MIN_CONFIDENCE, ReplyJudge, load_head, rule  # noqa: E402


def report(name, gold, pred, seconds=None):
    right = sum(g == p for g, p in zip(gold, pred))
    # Mistakes that matter most: calling "didn't understand" understood keeps a word they don't know in Telugu.
    costly = sum(g == "not_understood" and p == "understood" for g, p in zip(gold, pred))
    per = "  ".join(f"{lab} {sum(g == p == lab for g, p in zip(gold, pred))}/{sum(g == lab for g in gold)}" for lab in LABELS)
    speed = f"  {seconds * 1000:.0f} ms/reply" if seconds else ""
    print(f"{name:34} {right}/{len(gold)} = {right / len(gold):.0%}   [{per}]   costly: {costly}{speed}")
    return right / len(gold)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--wrong", action="store_true")
    args = p.parse_args()
    rows = [json.loads(line) for line in open(os.path.join(ROOT, "tools", "data", "reply_test.jsonl"))]
    gold = [r["label"] for r in rows]
    from decide import Decider
    judge = ReplyJudge(Decider(), head_path=None)

    by_rule = [rule(r["word"], r["reply"], r["means"]) for r in rows]
    covered = [(g, p) for g, p in zip(gold, by_rule) if p]
    print(f"{'rules (the cases they cover)':34} {sum(g == p for g, p in covered)}/{len(covered)} correct, "
          f"covering {len(covered)}/{len(rows)} replies")

    t = time.monotonic()
    shipped = [judge.laya(r["line"], r["word"], r["means"], r["reply"])[0] for r in rows]
    report("Laya as shipped", gold, shipped, (time.monotonic() - t) / len(rows))
    report("rules, then Laya as shipped", gold, [br or s for br, s in zip(by_rule, shipped)])

    if os.path.exists(HEAD_PATH):
        judge.head = load_head(judge.agent, HEAD_PATH)
        t = time.monotonic()
        answers = [judge.laya(r["line"], r["word"], r["means"], r["reply"]) for r in rows]
        trained = [label for label, _ in answers]
        report("Laya, trained head", gold, trained, (time.monotonic() - t) / len(rows))
        report("rules, then trained head", gold, [br or tr for br, tr in zip(by_rule, trained)])
        # The app: rules, then Laya only when it's sure; otherwise no evidence ("no_signal")
        combined = [br or (label if conf >= MIN_CONFIDENCE else "no_signal") for br, (label, conf) in zip(by_rule, answers)]
        evidence = [(g, c) for g, c in zip(gold, combined) if c != "no_signal"]
        right = sum(g == c for g, c in evidence)
        print(f"{'the app (Laya only when >= ' + str(MIN_CONFIDENCE) + ')':34} evidence from {len(evidence)}/{len(rows)} replies, "
              f"{right}/{len(evidence)} = {right / len(evidence):.0%} of it right; costly: "
              f"{sum(g == 'not_understood' and c == 'understood' for g, c in zip(gold, combined))}")
        print("confusions (gold -> predicted):", dict(Counter((g, c) for g, c in zip(gold, combined) if g != c)))
        if args.wrong:
            for r, c in zip(rows, combined):
                if c != r["label"]:
                    print(f"  want {r['label']:15} got {c:15} | {r['word']}: {r['reply']}")
    else:
        print("(no trained head yet: python tools/train_reply.py)")


if __name__ == "__main__":
    main()

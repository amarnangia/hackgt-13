# Training examples for the "did they understand?" check (reply.py): a line from grandma with one Telugu word kept
# in it, the grandkid's reply as speech recognition writes it, and whether the reply shows they understood the word.
# Muse Spark writes them from word-list words; words in tools/data/reply_test.jsonl are left out, so the test
# measures words the model never trained on.
#   python tools/make_reply_data.py [--per-word 9]     -> tools/data/reply_train.jsonl
#   python tools/make_reply_data.py --out tools/data/reply_train_2.jsonl --seed 2   # another batch, other sentences
import argparse
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from muse import spark_json  # noqa: E402

LABELS = ("understood", "not_understood", "no_signal")
SYSTEM = (
    "You write training data for a speech app. A grandparent on a phone call says a sentence in English that keeps one "
    "Telugu word untranslated. The grandchild (raised in the US, beginner Telugu) replies out loud; the reply is written "
    "the way live speech recognition gives it: lowercase, little punctuation, fillers like um, like, oh. Label each reply:\n"
    "- understood: the reply only makes sense if they know what the Telugu word means (refers to the thing, uses the "
    "English for it, asks a follow-up that fits its meaning, reacts in a way that fits).\n"
    "- not_understood: they ask what it means or what was said, sound confused, mishear it, or reply as if it meant "
    "something else (a plausible but wrong guess).\n"
    "- no_signal: the reply says nothing about whether they understood the word: backchannels (okay, mhm, nice, wow, "
    "yes grandma), generic replies that fit any sentence, changing the subject, talking about the call itself, or "
    "talking to someone else in the room.\n"
    "Make them varied and realistic, including hard cases: short understood replies, polite no_signal replies that "
    "sound engaged but don't show the meaning, and wrong guesses that sound confident."
)


def batch(entry, per_word):
    word, means = entry["roman"].rstrip(","), entry["translate_as"]
    user = (f"Telugu word: {word} (means: {means}; {entry.get('note', '')}).\n"
            f"Write {per_word} examples, {per_word // 3} per label, each with a different grandparent sentence using "
            f"'{word}'. JSON: {{\"examples\": [{{\"line\": ..., \"reply\": ..., \"label\": ...}}]}}")
    out = spark_json(SYSTEM, user, model="muse-spark-1.3", effort="low", timeout=90) or {}
    rows = []
    for ex in out.get("examples", []):
        if ex.get("label") in LABELS and ex.get("line") and ex.get("reply") and word.lower() in ex["line"].lower():
            rows.append({"line": ex["line"], "word": word, "means": means, "reply": ex["reply"], "label": ex["label"]})
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--per-word", type=int, default=9)
    p.add_argument("--out", default=os.path.join("tools", "data", "reply_train.jsonl"))
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args()
    test = {json.loads(line)["word"].lower() for line in open(os.path.join(HERE_DATA, "reply_test.jsonl"))}
    entries = [e for e in json.load(open(os.path.join(ROOT, "lexicon.json"), encoding="utf-8"))["te"]
               if e.get("roman") and e.get("translate_as") and e.get("category") != "idiom"
               and e["roman"].rstrip(",").lower() not in test]
    random.Random(args.seed).shuffle(entries)
    with ThreadPoolExecutor(8) as pool:
        rows = [r for rs in pool.map(lambda e: batch(e, args.per_word), entries) for r in rs]
    path = os.path.join(ROOT, args.out)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    counts = {lab: sum(r["label"] == lab for r in rows) for lab in LABELS}
    print(f"{len(rows)} examples from {len(entries)} words -> {os.path.relpath(path, ROOT)}  {counts}")


HERE_DATA = os.path.join(ROOT, "tools", "data")

if __name__ == "__main__":
    main()

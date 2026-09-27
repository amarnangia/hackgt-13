# Training and test examples for Laya's "is this line really using that saying?" check (sayings.py).
# For each saying in sayings.json, Muse Spark writes lines that use it (full or short form) and lines that share its
# words literally ("the dog's tail got hurt" for "a dog's tail stays crooked"). Each becomes (line, candidate saying,
# yes/no), plus lines using a *different* saying paired with this one. Telugu lines also get speech-recognition-style
# misspellings (long/short vowels, similar letters, merged or split words), since that's what Muse writes.
# Sayings are split by id: 85% train, 15% test (never trained on). lexicon.json's idioms, and anything that sounds
# like them, are left out entirely so tools/check_idioms.py stays a fair spoken test.
#   python tools/make_saying_data.py      -> tools/data/sayings_train.jsonl, tools/data/sayings_test.jsonl
import json
import os
import random
import re
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lexicon import Lexicon  # noqa: E402
from muse import spark_json  # noqa: E402
from sayings import SAYINGS_PATH, english_words, sound  # noqa: E402

DATA = os.path.join(ROOT, "tools", "data")
TEST_SHARE = 0.15

SIMILAR = [("ా", ""), ("ీ", "ి"), ("ూ", "ు"), ("ే", "ె"), ("ో", "ొ"), ("త", "ట"), ("ద", "డ"), ("న", "ణ"), ("ల", "ళ"),
           ("శ", "స"), ("ష", "స"), ("క", "గ"), ("ప", "బ"), ("చ", "జ"), ("ర", "ఱ")]


def misspell(text, rng):
    """Speech-recognition-style spelling changes to Telugu text (1-3 of them)."""
    s = text
    for _ in range(rng.randint(1, 3)):
        op = rng.random()
        if op < 0.45:
            a, b = rng.choice(SIMILAR)
            a, b = (a, b) if rng.random() < 0.5 else (b, a)
            spots = [m.start() for m in re.finditer(re.escape(a), s)] if a else []
            if spots:
                i = rng.choice(spots)
                s = s[:i] + b + s[i + len(a):]
        elif op < 0.65:
            spaces = [m.start() for m in re.finditer(" ", s)]
            if spaces:
                i = rng.choice(spaces)
                s = s[:i] + s[i + 1:]  # two words run together
        elif op < 0.8:
            words = s.split(" ")
            i = rng.randrange(len(words))
            if len(words[i]) > 3:
                words[i] = words[i][:-1]  # last letter or vowel sign lost
            s = " ".join(words)
        else:
            s = re.sub(r"(.)్\1", r"\1", s, count=1) if rng.random() < 0.5 else s  # a doubled letter comes out single
    return s


def ask(items, lang):
    who = ("a Telugu grandmother talking to her grandchild on a video call, in Telugu script" if lang == "te"
           else "a grandchild raised in the US talking to their grandmother, in casual spoken English")
    listing = "\n".join(f"{i}. {e['forms'][0]} (means: {e['translate_as']})" for i, e in enumerate(items))
    system = (f"You write test sentences for a speech app. The speaker is {who}. Sentences are short and natural, "
              "as spoken (not written).")
    user = (f"{listing}\nFor each item: 'uses': 3 sentences that use it as a saying/expression/reference (vary the "
            "wording around it; for long proverbs one may use just its well-known first half), and 'literal': 2 "
            "sentences that share some of its words but do NOT use it (literal meaning, different topic).\n"
            'JSON: {"items": [{"i": index, "uses": [...], "literal": [...]}]}')
    out = spark_json(system, user, model="muse-spark-1.3", effort="low", timeout=150) or {}
    rows = {}
    for x in out.get("items", []):
        if isinstance(x.get("i"), int) and 0 <= x["i"] < len(items):
            rows[items[x["i"]]["id"]] = (x.get("uses") or [], x.get("literal") or [])
    return rows


def main():
    data = json.load(open(SAYINGS_PATH, encoding="utf-8"))
    lex = Lexicon()
    listed = [sound(f) for e in lex.entries["te"] if e.get("category") == "idiom" for f in e["forms"]]
    from rapidfuzz import fuzz
    rng = random.Random(7)
    train, test = [], []
    for lang in ("te", "en"):
        items = data.get(lang, [])
        if lang == "te":  # keep the hand-made idioms (and look-alikes) out of training and this test
            items = [e for e in items if not any(fuzz.ratio(sound(e["forms"][0]), s) >= 80 for s in listed)]
        batches = [items[i:i + 6] for i in range(0, len(items), 6)]
        with ThreadPoolExecutor(8) as pool:
            written = {}
            for part in pool.map(lambda b: ask(b, lang), batches):
                written.update(part)
        key = (lambda t: sound(t)) if lang == "te" else english_words
        by_id = {e["id"]: e for e in items}
        ids = [i for i in written if i in by_id]
        for sid in ids:
            e = by_id[sid]
            is_test = zlib.crc32(sid.encode()) % 100 < TEST_SHARE * 100
            uses, literal = written[sid]
            others = [o for o in ids if o != sid]
            # the look-alike: another saying that sounds most like this one (the hardest wrong candidate)
            near = max(rng.sample(others, min(40, len(others))), key=lambda o: fuzz.ratio(key(by_id[o]["forms"][0]), key(e["forms"][0])))
            rows = []
            for u in uses:
                rows.append((u, e, "yes"))
                rows.append((u, by_id[near], "no"))
                if lang == "te":
                    rows.append((misspell(u, rng), e, "yes"))
            for l in literal:
                rows.append((l, e, "no"))
            for line, cand, label in rows:
                (test if is_test else train).append({"lang": lang, "line": line, "saying": cand["forms"][0],
                                                     "roman": cand.get("roman", ""), "means": cand["translate_as"],
                                                     "id": cand["id"], "about": sid, "label": label})
        print(f"{lang}: {len(ids)} sayings with examples")
    os.makedirs(DATA, exist_ok=True)
    for name, rows in (("sayings_train.jsonl", train), ("sayings_test.jsonl", test)):
        with open(os.path.join(DATA, name), "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(train)} training, {len(test)} test examples "
          f"(yes {sum(r['label'] == 'yes' for r in train)}, no {sum(r['label'] == 'no' for r in train)} in training)")


if __name__ == "__main__":
    main()

# Builds sayings.json: Telugu sayings (సామెతలు), idiomatic expressions (జాతీయాలు) and cultural references, and English
# idioms, slang and American cultural references, each with its meaning, so Weave can explain them on a call
# (sayings.py finds them, even misspelled by speech recognition). Muse Spark writes them theme by theme, then a
# second pass checks each Telugu one is a real, well-known saying spelled right (made-up proverbs are dropped).
#   python tools/make_sayings.py              # -> sayings.json (takes a few minutes)
#   python tools/make_sayings.py --only en    # just one language
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from muse import spark_json  # noqa: E402

OUT = os.path.join(ROOT, "sayings.json")

TE_THEMES = ["food and cooking", "family and relatives", "money and debt", "animals", "farming and villages",
             "work and effort", "pride and arrogance", "foolishness", "cleverness and cunning", "patience and time",
             "marriage and in-laws", "children and upbringing", "friendship and enemies", "greed", "health and the body",
             "gods, temples and fate", "speech and gossip", "rich and poor", "help and gratitude", "laziness",
             "education and knowledge", "home and household", "nature, rain and seasons", "trouble and misfortune",
             "hypocrisy", "courage and fear", "age and elders", "neighbours and the village", "luck", "anger"]
TE_KINDS = {
    "saying": ("సామెతలు (Telugu proverbs) that grandparents really say", 15),
    "expression": ("జాతీయాలు (Telugu idiomatic expressions, e.g. చెవిలో పువ్వు పెట్టడం = to fool someone) people use in "
                   "everyday talk", 10),
}
TE_CULTURE = ["festivals and their customs", "wedding rituals", "temple and puja words", "Telugu foods and dishes",
              "snacks, pickles and sweets", "clothing and jewellery", "village life and farming", "stories from the "
              "Ramayana and Mahabharata that people refer to", "famous Telugu films, actors and dialogues people quote",
              "places in Andhra Pradesh and Telangana", "games children play", "blessings and greetings elders say",
              "household customs and superstitions", "folk arts, music and dance", "school and exam life in India",
              "trains, buses and travel in India", "cricket and sports", "Sankranti", "Diwali and Dasara",
              "Ugadi and Bathukamma"]
EN_THEMES = ["work and school", "money", "food", "animals", "the body", "weather", "time", "success and failure",
             "secrets and honesty", "anger and emotions", "friendship", "sports", "luck", "trouble", "effort",
             "decisions", "talking and gossip", "family", "travel", "health"]
EN_SLANG = ["Gen Z slang", "texting and internet slang", "school and college slang", "compliments and hype",
            "reactions (e.g. I'm dead, it's giving)", "gaming and streaming slang"]
EN_CULTURE = ["American holidays and their customs", "high school life (prom, homecoming, SATs)", "college life",
              "American foods and restaurants", "American sports", "TV shows, movies and memes", "shopping and "
              "Black Friday", "US places and landmarks", "American family customs", "jobs and internships",
              "pop music and celebrities", "cars and driving", "US money and tipping", "summer camp and road trips"]


def ask(system, user):
    return spark_json(system, user, model="muse-spark-1.3", effort="low", timeout=120) or {}


def telugu(kind, theme, n, avoid):
    what, _ = TE_KINDS.get(kind, ("Telugu cultural references (things, customs, people, events)", 0))
    system = ("You are a Telugu language and culture expert writing a glossary for a grandchild raised in the US who "
              "is learning Telugu on video calls with their grandmother in Andhra Pradesh/Telangana. Only include real, "
              "widely known items, spelled as Telugu speakers write them. Never invent.")
    user = (f"List {n} {what} about: {theme}. Skip these: {', '.join(avoid[:60])}.\n"
            "For each: telugu (Telugu script, the full common form), short (list of shorter forms people actually say, "
            "e.g. just the first half of a proverb; may be empty), roman (simple romanized spelling), literal (word-for-word "
            "English), meaning (what it means, short), note (one sentence: when people say it or why it matters).\n"
            'JSON: {"items": [{"telugu": ..., "short": [...], "roman": ..., "literal": ..., "meaning": ..., "note": ...}]}')
    return ask(system, user).get("items", [])


def verify_telugu(items):
    """Keep what a second look says is real and well known; take its spelling fixes."""
    system = ("You check a Telugu glossary for mistakes. For each item say if it is a real, commonly known Telugu "
              "saying/expression/reference (not invented, not a translation of an English idiom), fix its Telugu "
              "spelling if wrong, and fix the meaning if wrong.")
    listing = "\n".join(f"{i}. {x['telugu']} = {x['meaning']}" for i, x in enumerate(items))
    out = ask(system, f"{listing}\nJSON: {{\"checks\": [{{\"i\": index, \"real\": true/false, \"telugu\": fixed spelling, "
                      f"\"meaning\": fixed meaning}}]}}").get("checks", [])
    kept = []
    for c in out:
        i = c.get("i")
        if isinstance(i, int) and 0 <= i < len(items) and c.get("real") is True:
            x = dict(items[i])
            x["telugu"] = c.get("telugu") or x["telugu"]
            x["meaning"] = c.get("meaning") or x["meaning"]
            kept.append(x)
    return kept


def english(kind, theme, n, avoid):
    what = {"idiom": "English idioms and figures of speech", "slang": "English slang terms",
            "culture": "American cultural references"}[kind]
    system = ("You write a glossary for a Telugu grandmother in India who speaks little English, on video calls with a "
              "grandchild raised in the US. Only include real, commonly used items.")
    user = (f"List {n} {what} about: {theme}. Skip these: {', '.join(avoid[:60])}.\n"
            "For each: phrase (the usual form), variants (other forms as people say them: tenses, pronouns, e.g. "
            "'spilled the beans', 'spill the tea'), meaning (plain English, short), meaning_te (the meaning in simple "
            "Telugu script), note (one sentence of context).\n"
            'JSON: {"items": [{"phrase": ..., "variants": [...], "meaning": ..., "meaning_te": ..., "note": ...}]}')
    return ask(system, user).get("items", [])


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40]


def build_te(pool):
    jobs = [(k, t, n) for k, (_, n) in TE_KINDS.items() for t in TE_THEMES] + [("culture", t, 12) for t in TE_CULTURE]
    raw = [x for batch in pool.map(lambda j: [dict(it, kind=j[0]) for it in telugu(*j, [])], jobs) for x in batch
           if x.get("telugu") and x.get("meaning")]
    chunks = [raw[i:i + 20] for i in range(0, len(raw), 20)]
    kept = [x for batch in pool.map(verify_telugu, chunks) for x in batch]
    out, seen = [], set()
    for x in kept:
        key = re.sub(r"\s+", "", x["telugu"])
        if key in seen:
            continue
        seen.add(key)
        forms = [x["telugu"]] + [s for s in x.get("short", []) if s and len(s) >= 4 and s != x["telugu"]]
        out.append({"id": "say_" + slug(x.get("roman") or key), "forms": forms, "roman": x.get("roman", ""),
                    "literal": x.get("literal", ""), "translate_as": x["meaning"], "note": x.get("note", ""),
                    "category": "idiom" if x["kind"] in ("saying", "expression") else "culture", "kind": x["kind"]})
    print(f"Telugu: {len(raw)} written, {len(kept)} passed the check, {len(out)} after removing duplicates")
    return out


def build_en(pool):
    jobs = [("idiom", t, 15) for t in EN_THEMES] + [("slang", t, 20) for t in EN_SLANG] + [("culture", t, 15) for t in EN_CULTURE]
    raw = [x for batch in pool.map(lambda j: [dict(it, kind=j[0]) for it in english(*j, [])], jobs) for x in batch
           if x.get("phrase") and x.get("meaning")]
    out, seen = [], set()
    for x in raw:
        key = x["phrase"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        forms = [x["phrase"]] + [v for v in x.get("variants", []) if v and v.lower() != key]
        out.append({"id": "say_" + slug(key), "forms": forms, "translate_as": x["meaning"], "meaning_te": x.get("meaning_te", ""),
                    "note": x.get("note", ""), "category": x["kind"]})
    print(f"English: {len(raw)} written, {len(out)} after removing duplicates")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", choices=["te", "en"])
    args = p.parse_args()
    data = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    data["_about"] = ("Sayings, idioms, slang and cultural references for sayings.py, written by Muse Spark "
                      "(tools/make_sayings.py) and checked by a second pass. lexicon.json stays the hand-made list.")
    with ThreadPoolExecutor(8) as pool:
        if args.only != "en":
            data["te"] = build_te(pool)
        if args.only != "te":
            data["en"] = build_en(pool)
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"-> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()

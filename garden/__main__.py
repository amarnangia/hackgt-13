"""python -m garden            serve the real garden (garden/garden.db) at http://localhost:8770
python -m garden --demo     serve a demo garden: two weeks of fake calls using the words in lexicon.json,
                            plus a live fake call that keeps growing it
"""
import argparse, json, random, threading, time
from pathlib import Path
from .store import Garden
from .server import serve

HERE = Path(__file__).resolve().parent
COMMON = {"food": 3, "family": 6, "idiom": 2, "place": 3, "festival": 2, "vehicle": 3, "clothing": 2}  # how often each kind comes up


def demo_phrases(lang="te"):
    """(phrase, english, category, note, roman, weight) from the team's lexicon.json (read only)."""
    lex = json.load(open(HERE.parent / "lexicon.json", encoding="utf-8"))
    out = []
    for e in lex[lang]:
        phrase = e["forms"][0].strip(" ,.")
        english = e.get("translate_as") or e.get("note", "")
        weight = COMMON.get(e["category"], 1) + (4 if e["id"] in ("annam_tinnava", "ammamma", "pulihora", "dosa", "auto", "temple") else 0)
        out.append((phrase, english.strip(" ,"), e["category"], e.get("note"), e["id"].replace("_", " "), weight))
    return out


def seed_demo(g, phrases, days=14):
    rng = random.Random(7)
    pool = [p for p in phrases for _ in range(p[5])]
    rng.shuffle(pool)
    now = time.time()
    for d in range(days, -1, -1):
        if d > 5 and rng.random() < 0.3:
            continue  # skipped a day (but keep a streak going into today)
        start = now - d * 86400 - rng.randint(1, 5) * 3600
        with g._conn() as c:
            c.execute("INSERT INTO calls (started, ended) VALUES (?, ?)", (start, start + rng.randint(8, 30) * 60))
        for i in range(rng.randint(32, 48)):
            phrase, english, cat, note, roman, _ = rng.choice(pool[: max(40, len(pool) * (days - d + 4) // days)])
            g.heard(phrase, english, cat, note, roman, ts=start + i * 60)
            if rng.random() < 0.02:
                g.asked(phrase, ts=start + i * 60 + 5)


def live_call(g, phrases, every=4.0):
    rng = random.Random()
    pool = [p for p in phrases for _ in range(p[5])]
    with g.call():
        while True:
            phrase, english, cat, note, roman, _ = rng.choice(pool)
            g.heard(phrase, english, cat, note, roman)
            time.sleep(every)


def main():
    ap = argparse.ArgumentParser(prog="python -m garden")
    ap.add_argument("--demo", action="store_true", help="fake history + a live fake call, in garden/garden_demo.db")
    ap.add_argument("--still", action="store_true", help="with --demo: no live call, just the history")
    ap.add_argument("--port", type=int, default=8770)
    a = ap.parse_args()
    if a.demo:
        db = HERE / "garden_demo.db"
        db.unlink(missing_ok=True)
        g, phrases = Garden(db), demo_phrases()
        seed_demo(g, phrases)
        if not a.still:
            threading.Thread(target=live_call, args=(g, phrases), daemon=True).start()
    else:
        g = Garden()
    serve(g, a.port)


if __name__ == "__main__":
    main()

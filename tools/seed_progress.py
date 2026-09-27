# Start from a known state for testing and demos, instead of the many calls it takes to learn words for real:
# some words already known (kept in Telugu), some being learned, some just met. Your real progress is backed up
# first and put back with --restore.
#   python tools/seed_progress.py            # back up progress.json, then set the words below
#   python tools/seed_progress.py --restore  # put your real progress back
#   python tools/seed_progress.py --show     # how likely you know each of these words right now
#   python tools/seed_progress.py --demo     # the demo: only "ee roju" is known (kept in Telugu); every other word is
#                                            # still being learned (translated), and becomes known with more hearings
import argparse
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from lexicon import Lexicon  # noqa: E402
from progress import KEEP_AT, Progress  # noqa: E402

STAGES = {
    # kept in Telugu (at or above --keep-at, 0.7 by default). Swapped in by the word list, so they reliably come back
    "known": (0.9, ["pulihora", "pappu", "perugu", "paalu", "ammamma", "amma", "sare", "avunu"]),
    # being learned: translated at the default; kept too with --keep-at 0.5
    "learning": (0.55, ["pachadi", "gavvalu", "mamidi", "badi", "neellu", "akka"]),
    # just met: translated, with a picture or card
    "meeting": (0.1, ["ariselu", "bhogi", "bangaram", "illu", "annayya"]),
}
FILES = ["progress.json", "progress_log.jsonl"]
BACKUP = os.path.join(ROOT, ".progress_backup")


def show(progress):
    for stage, (_, ids) in STAGES.items():
        words = ", ".join(f"{progress.entries[i]['roman'].rstrip(',')} {progress.probability(i):.2f}" for i in ids)
        print(f"  {stage:9} {words}")
    print(f"  (kept in Telugu at {KEEP_AT} and up; run subtitles.py with --keep-at 0.5 to keep the learning words too)")


DEMO_KNOWN = ["ee_roju"]
DEMO_LEARNING_P = 0.3  # below KEEP_AT: translated. Each spaced hearing (progress.LEARN) moves it up; ~5 make it known


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--restore", action="store_true")
    p.add_argument("--show", action="store_true")
    p.add_argument("--demo", action="store_true", help='only "ee roju" known; everything else still being learned')
    args = p.parse_args()
    os.chdir(ROOT)
    if args.show:
        return show(Progress(Lexicon(), "te"))
    if args.restore:
        if not os.path.isdir(BACKUP):
            sys.exit("No backup to restore (.progress_backup/ is missing).")
        for f in FILES:
            if os.path.exists(os.path.join(BACKUP, f)):
                shutil.copy(os.path.join(BACKUP, f), f)
        shutil.rmtree(BACKUP)
        print("Your real progress is back.")
        return show(Progress(Lexicon(), "te"))
    if os.path.isdir(BACKUP):
        print("(already seeded once; keeping the original backup)")
    else:
        os.makedirs(BACKUP)
        for f in FILES:
            if os.path.exists(f):
                shutil.copy(f, os.path.join(BACKUP, f))
    progress = Progress(Lexicon(), "te")
    now = time.time()
    stages = STAGES
    if args.demo:  # every word (family words too) starts as "learning", except the one the demo shows staying in Telugu
        rest = [i for i in progress.entries if i not in DEMO_KNOWN]
        stages = {"known": (0.95, DEMO_KNOWN), "learning": (DEMO_LEARNING_P, rest)}
    for stage, (prob, ids) in stages.items():
        for i in ids:
            assert i in progress.entries, f"{i} isn't in lexicon.json"
            progress.words[i] = {"p": prob, "t": now, "hl": 30.0}  # a long half-life: no fading during the test
            progress.heard[i] = max(progress.heard.get(i, 0) if not args.demo else 0, {"known": 8, "learning": 3, "meeting": 1}[stage])
    progress._save()
    print("Seeded (your real progress is in .progress_backup/; undo with --restore):")
    show(progress)


if __name__ == "__main__":
    main()

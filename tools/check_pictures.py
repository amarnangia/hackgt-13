# Check which item Laya picks a picture for on known lines.  python tools/check_pictures.py
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from decide import Decider  # noqa: E402
from pictures import PictureFinder  # noqa: E402

# (English line, acceptable picks: library ids / "web:<noun>" / None for no picture)
CASES = [
    ("Today I made tamarind rice for you.", {"pulihora"}),
    ("Yesterday I went in an auto-rickshaw to the temple.", {"auto", "temple"}),
    ("How are your studies going?", {None}),
    ("I want to see a new movie.", {None}),
    ("Grandma made mango pickle.", {"avakaya"}),
    ("We flew kites and drew rangoli for Sankranti.", {"rangoli", "kite", "sankranti"}),
    ("I bought a silk saree for your sister's wedding.", {"silk_saree", "wedding"}),
    ("Did you eat pizza again today?", {None}),
    ("Your uncle will bring laddus.", {"laddu"}),
    ("It's very hot here, the rains haven't come yet.", {None, "monsoon"}),
    ("I'm very hungry.", {None}),
    ("We had paneer curry and naan.", {"paneer_curry", "naan"}),
    ("Your grandfather went to the paddy field.", {"paddy_field"}),
    ("Send me a photo on WhatsApp.", {None}),
    ("We went to the Charminar yesterday.", {"charminar"}),
    ("I made payasam for the puja.", {"payasam", "puja"}),
    ("Call me after school.", {None}),
    ("Your aunt wore bangles and a bindi.", {"bangles", "bindi"}),
    ("We are going to Tirupati next month.", {"tirupati"}),
    ("Eat some curd rice before you sleep.", {"curd_rice"}),
    ("Your cousin is getting married in December.", {None, "wedding"}),
    ("We bought sugarcane juice at the market.", {"sugarcane"}),
    ("Thatayya is wearing a new pancha.", {"dhoti"}),
    ("Did you have a burger for lunch?", {None}),
    ("Your mother called me last night.", {None}),
]

d = Decider()
finder = PictureFinder(d)
ok, times = 0, []
for english, want in CASES:
    finder.shown.clear()
    cands = [c[0] for c in finder.candidates(english, [])]
    t = time.monotonic()
    got = finder.pick(english, [])
    times.append(time.monotonic() - t)
    good = got in want
    ok += good
    print(f"{'✓' if good else '✗'} {english:52} -> {got!s:16} (from {cands})")
print(f"\n{ok}/{len(CASES)} correct; Laya {sum(times) / len(times) * 1000:.0f} ms per line on average")

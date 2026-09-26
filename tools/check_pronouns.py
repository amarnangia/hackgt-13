# Check that తను ("he or she") becomes the right English pronoun. Each case is a short conversation; the last
# line's English should use the expected pronoun. Runs the lines through the local translator if it's up.
#   python tools/check_pronouns.py
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pronouns import PronounResolver  # noqa: E402

CASES = [  # (conversation, pronoun the last line should use; "she+he" = both people are in the line)
    (["తను ఈ రోజు ఆఫీసుకి వెళ్ళింది."], "she"),
    (["తను ఈ రోజు ఆఫీసుకి వెళ్ళాడు."], "he"),
    (["తను నాకు ఫోన్ చేసింది."], "she"),
    (["నా స్నేహితురాలికి చాలా మంచి ఉద్యోగం వచ్చింది,", "తను డబ్బంతా తీసేసుకుంటుంది."], "she"),
    (["అమ్మ వంట చేస్తోంది, తనకి సహాయం చేయి."], "her"),
    (["మా అక్కకి పెళ్లి అయింది.", "తనకి జ్వరం వచ్చింది."], "she"),
    (["మా తమ్ముడు ఇంటికి వచ్చాడు.", "తనకి జ్వరం వచ్చింది."], "he"),
    (["నా అన్నయ్య తన భార్యతో వచ్చాడు."], "his"),
    (["మా అక్క తన ఫోన్ పోగొట్టుకుంది."], "her"),
    (["నాన్న అడిగాడు, తను ఎలా ఉంది అని."], "she+he"),  # "he asked how she was": the verb in తను's clause wins
    (["my sister got a new job.", "తనకి చాలా సంతోషంగా ఉంది."], "she"),
    (["నాన్న, నా స్నేహితురాలు వచ్చింది.", "తనని అడుగు."], "her"),  # నాన్న, = grandma calling you, not a he
]


def translator():
    try:
        import requests
        requests.post("http://localhost:8766", json={"text": "", "lang": "te"}, timeout=2)
        return lambda s: requests.post("http://localhost:8766", json={"text": s, "lang": "te"}, timeout=10).json()["english"]
    except Exception:
        print("(local translator not running: checking the rewritten Telugu only)\n")
        return None


translate = translator()
SHE, HE = r"\b(she|her|hers|herself)\b", r"\b(he|him|his|himself)\b"
ok = 0
for lines, want in CASES:
    resolve = PronounResolver("te")
    rewritten = [resolve(line) for line in lines]
    female = want.split("+")[0] in ("she", "her")
    if translate:
        text = translate(rewritten[-1])
        right, wrong = (SHE, HE) if female else (HE, SHE)
        match = bool(re.search(right, text, re.I)) and ("+" in want or not re.search(wrong, text, re.I))
    else:
        text = rewritten[-1]
        match = ("ఆమె" if female else "అతన") in text and ("అతన" if female else "ఆమె") not in text
    ok += match
    print(f"{'✓' if match else '✗'} want {want:4} | {' / '.join(lines)}  ->  {text}")
print(f"{ok}/{len(CASES)} pronouns right")
sys.exit(0 if ok == len(CASES) else 1)

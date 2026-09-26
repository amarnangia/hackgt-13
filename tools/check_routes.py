# Compare how the last run routed each line against a sample's expected routes.
#   rm -f latency_log.jsonl
#   python subtitles.py --file samples/telugu_english_mix.wav --out none
#   python tools/check_routes.py samples/telugu_english_mix.json
# Muse sometimes splits one spoken line into two pieces, so each expected line is matched to the run of
# consecutive logged pieces whose text is most similar to it.
import difflib
import json
import sys

expected = json.load(open(sys.argv[1]))
rows = [json.loads(line) for line in open("latency_log.jsonl")]
norm = lambda t: "".join(ch for ch in t.lower() if ch.isalnum())
sim = lambda a, b: difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()

ok, j = 0, 0
for want in expected:
    best, best_k = 0.0, j
    for k in range(j + 1, min(j + 4, len(rows)) + 1):
        score = sim(want["text"], " ".join(r["text"] for r in rows[j:k]))
        if score > best:
            best, best_k = score, k
    pieces = rows[j:best_k]
    routes = {r.get("route") for r in pieces}
    match = best >= 0.5 and routes == {want["route"]}
    ok += match
    english = " / ".join(r["english"] for r in pieces)
    print(f"{'✓' if match else '✗'} expected {want['route']:8} got {'+'.join(sorted(routes)) or 'nothing':8} "
          f"(text match {best:.0%}) | {want['text']}  ->  {english}")
    j = best_k
print(f"{ok}/{len(expected)} lines routed as expected")
sys.exit(0 if ok == len(expected) else 1)

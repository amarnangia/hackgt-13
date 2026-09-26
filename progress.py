# Which Telugu words the listener knows, so translations can keep them in Telugu ("translate less over time").
#
# Each word has a probability that the listener knows it, updated by what happens on calls. This is a simplified
# Bayesian Knowledge Tracing (the model tutoring software uses) with forgetting:
#   - Learning: every time the word comes up with its meaning (heard with a card, a picture, an answer), there's a
#     chance they learn it:  p = p + (1 - p) * LEARN[event]
#   - Evidence: what they do tells us whether they know it (Bayes' rule with how likely each action is if they do
#     vs don't know the word): asking "What does ___ mean?" or tapping a kept word pushes p down hard; seeing it
#     kept in Telugu and not tapping it pushes p up a little; saying it themselves pushes p up a lot.
#   - Forgetting: between calls p fades back toward the word's starting guess, with a half-life that doubles each
#     time they show they still know it (spaced repetition) and halves when they don't.
# A word is kept in Telugu once p >= KEEP_AT. Saved per person in progress.json (gitignored).
import json
import math
import os
import re
import threading
import time

KEEP_AT = 0.7  # keep a word in Telugu once we're this sure they know it (--keep-at; lower it for a quick demo)
UNDERSTOOD_S = 20  # shown in Telugu and not tapped for this long: they understood it

# Starting guess, before any evidence, by kind of word (start_known words: family words everyone knows)
PRIOR = {"start_known": 0.95, "family": 0.35, "festival": 0.25, "phrase": 0.25, "food": 0.2, "place": 0.2, "clothing": 0.2,
         "vehicle": 0.2, "word": 0.15, "culture": 0.1, "idiom": 0.02}
DEFAULT_PRIOR = 0.15
# Chance that one event teaches the word
LEARN = {
    "heard": 0.2,      # came up on the call, with its meaning on screen (translation, card or the English next to it)
    "picture": 0.15,   # its picture popped up
    "answer": 0.3,     # they asked what it means and read the answer
    "practiced": 0.1,  # tapped "hear it" in the vocab panel
    "said": 0.2,       # said it themselves
}
# How likely each action is if they know the word, and if they don't: (P(action | knows), P(action | doesn't))
EVIDENCE = {
    "understood": (0.9, 0.5),   # kept in Telugu and not tapped (they might just not have bothered: weak evidence)
    "asked": (0.1, 0.7),        # asked "What does ___ mean?"
    "forgot": (0.03, 0.8),      # tapped a kept word: "I don't know this"
    "said": (0.9, 0.05),        # said it themselves on the call
}
HALF_LIFE_DAYS, MIN_HALF_LIFE_DAYS, MAX_HALF_LIFE_DAYS = 7.0, 1.0, 60.0  # most families call about weekly


class Progress:
    def __init__(self, lexicon, lang, path="progress.json", keep_at=KEEP_AT):
        self.path, self.keep_at, self.lang = path, keep_at, lang
        self.entries = {e["id"]: e for e in lexicon.entries.get(lang, []) if "roman" in e}
        self.lock = threading.Lock()
        saved = json.load(open(path)) if os.path.exists(path) else {}
        self.heard = saved.get("heard", {})  # times each word came up (for the story page and Weave)
        self.words = saved.get("words", {})  # id -> {"p": probability known, "t": when, "hl": half-life in days}
        self.pending = {}                    # kept in Telugu at this time; "understood" unless tapped soon
        for wid, n in self.heard.items():    # progress.json from before this model: replay the hearings
            if wid not in self.words and wid in self.entries:
                for _ in range(n):
                    self._learn(wid, "heard", save=False)
        for wid in saved.get("forgotten", []):
            if wid in self.entries:
                self._evidence(wid, "forgot")

    # ---------- the model ----------
    def prior(self, entry_id):
        e = self.entries.get(entry_id, {})
        return PRIOR["start_known"] if e.get("start_known") else PRIOR.get(e.get("category"), DEFAULT_PRIOR)

    def probability(self, entry_id, now=None):
        """How likely they know it right now, forgetting included."""
        if entry_id not in self.entries:
            return 0.0
        w, prior = self.words.get(entry_id), self.prior(entry_id)
        if not w:
            return prior
        if w["p"] <= prior:
            return w["p"]
        days = ((now or time.time()) - w["t"]) / 86400
        return prior + (w["p"] - prior) * math.pow(0.5, days / w["hl"])

    def _state(self, entry_id):
        p = self.probability(entry_id)
        w = self.words.setdefault(entry_id, {"p": p, "t": time.time(), "hl": HALF_LIFE_DAYS})
        w["p"], w["t"] = p, time.time()
        return w

    def _learn(self, entry_id, event, save=True):
        w = self._state(entry_id)
        w["p"] = w["p"] + (1 - w["p"]) * LEARN[event]
        if save:
            self._save()

    def _evidence(self, entry_id, event):
        w = self._state(entry_id)
        if_known, if_not = EVIDENCE[event]
        w["p"] = w["p"] * if_known / (w["p"] * if_known + (1 - w["p"]) * if_not)
        if if_known > if_not and w["p"] >= self.keep_at:  # showed they still know it: remember it longer
            w["hl"] = min(MAX_HALF_LIFE_DAYS, w["hl"] * 2)
        elif if_known < if_not:
            w["hl"] = max(MIN_HALF_LIFE_DAYS, w["hl"] / 2)

    def observe(self, entry_id, event):
        """Record something the listener did or saw: an EVIDENCE event, a LEARN event, or both ("said")."""
        if entry_id not in self.entries:
            return
        with self.lock:
            if event in EVIDENCE:
                self._evidence(entry_id, event)
            if event in LEARN:
                self._learn(entry_id, event, save=False)
            self._save()

    def known(self, entry_id):
        return self.probability(entry_id) >= self.keep_at

    # ---------- what the call does ----------
    def keep_known_words(self, english, hits):
        """Swap the fixed English of each known word back to its Telugu, e.g. "tamarind rice" -> "pulihora".

        Works because lexicon.json fixed that English before translating. Returns the new sentence and
        the kept words as [{id, telugu, english}] for the overlay.
        """
        kept = []
        for entry in hits:
            roman = entry.get("roman")
            if not roman or not self.known(entry["id"]):
                continue
            # The fixed English from the substitution, or for words left to the translator, the English it may use.
            candidates = entry.get("match_english") or [entry.get("translate_as", "")]
            match = None
            for gloss in sorted((g.rstrip(",") for g in candidates if g), key=len, reverse=True):
                match = re.search(rf"(?<![A-Za-z]){re.escape(gloss)}(?![A-Za-z])", english, re.IGNORECASE)
                if match:
                    break
            if not match:
                continue  # the translator rephrased it; leave the sentence as is
            telugu = roman.rstrip(",")
            if match.group(0)[:1].isupper():
                telugu = telugu[:1].upper() + telugu[1:]
            start = match.start()
            if entry["id"].endswith("_vocative") and english[:start].lower().endswith("my "):
                start -= 3  # "my dear" -> "Nanna", not "my Nanna"
            english = english[:start] + telugu + english[match.end():]
            kept.append({"id": entry["id"], "telugu": telugu, "english": match.group(0)})
        return english, kept

    def heard_words(self, hits, kept=()):
        """A line with these words was shown; `kept` are the ids shown in Telugu (not tapped yet)."""
        with self.lock:
            self.settle()
            now = time.monotonic()
            for entry in hits:
                wid = entry["id"]
                if wid not in self.entries:
                    continue
                self.heard[wid] = self.heard.get(wid, 0) + 1
                self._learn(wid, "heard", save=False)
                if wid in kept:
                    self.pending.setdefault(wid, now)
            self._save()

    def settle(self, everything=False):
        """Kept words nobody tapped within UNDERSTOOD_S were understood (at most once per showing)."""
        now = time.monotonic()
        for wid, shown in list(self.pending.items()):
            if everything or now - shown >= UNDERSTOOD_S:
                del self.pending[wid]
                self._evidence(wid, "understood")

    def forget(self, entry_id):
        """They tapped a kept word: they don't know it (yet). It's translated again until they learn it."""
        with self.lock:
            self.pending.pop(entry_id, None)
            if entry_id in self.entries:
                self._evidence(entry_id, "forgot")
                self._save()

    def finish(self):
        with self.lock:
            self.settle(everything=True)
            self._save()

    def snapshot(self):
        """{id: probability} for every word with any evidence (Weave, the story page)."""
        return {wid: round(self.probability(wid), 3) for wid in self.words}

    def _save(self):
        json.dump({"heard": self.heard, "words": self.words}, open(self.path, "w"), indent=1)

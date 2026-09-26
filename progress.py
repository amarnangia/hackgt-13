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
#
# The numbers below are sensible guesses. Every signal is also logged (progress_log.jsonl, gitignored), so
# tools/quiz.py (which words do you actually know?) and tools/fit_progress.py (which settings predict that best?) can
# tune them; Progress(..., prior_scale=, learn_scale=, evidence_scale=, half_life=) runs the model with other settings.
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
    # Their reply to a line that kept it in Telugu, judged by reply.py (rules + Laya's trained head; ~88% of these
    # conclusions were right on held-out test replies, the rest of replies give no evidence):
    "replied": (0.8, 0.25),     # the reply only makes sense if they know it ("save me some mangoes" after "mamidi")
    "confused": (0.1, 0.75),    # they asked, sounded lost, or answered as if it meant something else
}
HALF_LIFE_DAYS, MIN_HALF_LIFE_DAYS, MAX_HALF_LIFE_DAYS = 7.0, 1.0, 60.0  # most families call about weekly


class Progress:
    def __init__(self, lexicon, lang, path="progress.json", keep_at=KEEP_AT,
                 prior_scale=1.0, learn_scale=1.0, evidence_scale=1.0, half_life=HALF_LIFE_DAYS):
        """path=None: nothing is read, saved or logged (tools/fit_progress.py replaying a history). Settings saved by
        tools/fit_progress.py --save (progress_settings.json next to progress.json) are used instead of the defaults."""
        settings = os.path.join(os.path.dirname(os.path.abspath(path)), "progress_settings.json") if path else None
        if settings and os.path.exists(settings):
            fitted = json.load(open(settings))
            prior_scale, learn_scale = fitted.get("prior_scale", prior_scale), fitted.get("learn_scale", learn_scale)
            evidence_scale, half_life = fitted.get("evidence_scale", evidence_scale), fitted.get("half_life", half_life)
        self.path, self.keep_at, self.lang = path, keep_at, lang
        self.log_path = os.path.splitext(path)[0] + "_log.jsonl" if path else None
        self.entries = {e["id"]: e for e in lexicon.entries.get(lang, []) if "roman" in e}
        self.lock = threading.Lock()
        self.clock = time.time  # replaced when replaying a logged history
        # the settings (scales of 1 = the numbers above)
        self.priors = {k: min(0.99, v * prior_scale) for k, v in PRIOR.items()}
        self.default_prior = min(0.99, DEFAULT_PRIOR * prior_scale)
        self.learn = {k: min(0.95, v * learn_scale) for k, v in LEARN.items()}
        self.evidence = {k: tuple(min(0.99, max(0.01, 0.5 + (x - 0.5) * evidence_scale)) for x in v) for k, v in EVIDENCE.items()}
        self.half_life = half_life
        saved = json.load(open(path)) if path and os.path.exists(path) else {}
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
        return self.priors["start_known"] if e.get("start_known") else self.priors.get(e.get("category"), self.default_prior)

    def probability(self, entry_id, now=None):
        """How likely they know it right now, forgetting included."""
        if entry_id not in self.entries:
            return 0.0
        w, prior = self.words.get(entry_id), self.prior(entry_id)
        if not w:
            return prior
        if w["p"] <= prior:
            return w["p"]
        days = ((now or self.clock()) - w["t"]) / 86400
        return prior + (w["p"] - prior) * math.pow(0.5, days / w["hl"])

    def _state(self, entry_id):
        p = self.probability(entry_id)
        w = self.words.setdefault(entry_id, {"p": p, "t": self.clock(), "hl": self.half_life})
        w["p"], w["t"] = p, self.clock()
        return w

    def _learn(self, entry_id, event, save=True):
        w = self._state(entry_id)
        w["p"] = w["p"] + (1 - w["p"]) * self.learn[event]
        if save:
            self._save()

    def _evidence(self, entry_id, event):
        w = self._state(entry_id)
        if_known, if_not = self.evidence[event]
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
            if event in ("replied", "confused", "said"):
                self.pending.pop(entry_id, None)  # stronger evidence than "didn't tap it" for this showing
            self._apply(entry_id, event)
            self._log(entry_id, event)
            self._save()

    def _apply(self, entry_id, event):
        if event in EVIDENCE:
            self._evidence(entry_id, event)
        if event in LEARN:
            self._learn(entry_id, event, save=False)

    def replay(self, events):
        """Run a logged history ([{"t", "id", "event"}], oldest first) through this model, at the logged times."""
        for e in events:
            if e["id"] in self.entries:
                self.clock = lambda t=e["t"]: t
                self._apply(e["id"], e["event"])
                if e["event"] == "heard":
                    self.heard[e["id"]] = self.heard.get(e["id"], 0) + 1
        self.clock = time.time
        return self

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
                self._log(wid, "heard")
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
                self._log(wid, "understood")

    def forget(self, entry_id):
        """They tapped a kept word: they don't know it (yet). It's translated again until they learn it."""
        with self.lock:
            self.pending.pop(entry_id, None)
            if entry_id in self.entries:
                self._evidence(entry_id, "forgot")
                self._log(entry_id, "forgot")
                self._save()

    def finish(self):
        with self.lock:
            self.settle(everything=True)
            self._save()

    def snapshot(self):
        """{id: probability} for every word with any evidence (Weave, the story page)."""
        return {wid: round(self.probability(wid), 3) for wid in self.words}

    def _log(self, entry_id, event):
        if self.log_path:
            with open(self.log_path, "a") as f:
                f.write(json.dumps({"t": round(self.clock(), 1), "id": entry_id, "event": event}) + "\n")

    def _save(self):
        if self.path:
            json.dump({"heard": self.heard, "words": self.words}, open(self.path, "w"), indent=1)

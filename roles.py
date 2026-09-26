# --two-way: who is the Telugu speaker and who is the English speaker? One of each is on the call. We guess
# (you speak Telugu until the call says otherwise) and then go by who actually speaks more Telugu, so each person
# hears everything in their own language. `--telugu-speaker me|them` skips the guessing.
import re
import threading
from collections import deque

from lexicon import INDIC_LETTERS

WORD = re.compile(rf"[{INDIC_LETTERS}]+|[A-Za-z']+")
WINDOW = 40        # judge each side by its last this-many words, so a wrong early call can still be fixed
MIN_WORDS = 15     # words from a side before its share counts
EARLY_WORDS, EARLY_GAP = 6, 0.5  # ...but a few words each that clearly differ (one Telugu, one English) decide sooner
DECIDE_GAP = 0.25  # first decision: one side's Telugu share must beat the other's by this much
FLIP_GAP = 0.4     # changing a decision later needs clearer evidence
CLEAR_TELUGU, CLEAR_ENGLISH = 0.6, 0.1  # with only one side heard so far, a share this clear decides it


class Roles:
    def __init__(self, fixed=None, default="me", on_change=None):
        """fixed: "me" or "them" (the Telugu speaker, never changes); else start from `default` and listen."""
        self.telugu = fixed or default
        self.fixed = fixed is not None
        self.decided = self.fixed
        self.on_change = on_change  # called with (telugu_side, reason) when the roles are decided or flip
        self.words = {"me": deque(maxlen=WINDOW), "them": deque(maxlen=WINDOW)}  # True per Telugu word
        self.lock = threading.Lock()

    def lang_of(self, side):
        return "te" if side == self.telugu else "en"

    def listener_lang(self, side):
        """The language the person *hearing* `side` understands."""
        return self.lang_of("them" if side == "me" else "me")

    def share(self, side):
        words = self.words[side]
        return sum(words) / len(words) if words else 0.0

    def heard(self, side, text):
        """Count a finished line from `side` ("me" or "them")."""
        if self.fixed:
            return
        with self.lock:
            self.words[side].extend(bool(re.match(rf"[{INDIC_LETTERS}]", w)) for w in WORD.findall(text))
            verdict = self._verdict()
            if verdict and verdict[0] != self.telugu or verdict and not self.decided:
                first = not self.decided
                self.telugu, self.decided = verdict[0], True
                change = (self.telugu, ("decided: " if first else "changed: ") + verdict[1])
            else:
                change = None
        if change and self.on_change:
            self.on_change(*change)

    def _verdict(self):
        """(telugu side, why) if the evidence is clear enough, else None."""
        n = {s: len(self.words[s]) for s in self.words}
        share = {s: self.share(s) for s in self.words}
        pct = lambda s: f"{share[s]:.0%} Telugu from {'you' if s == 'me' else 'them'}"
        if not self.decided and n["me"] >= EARLY_WORDS and n["them"] >= EARLY_WORDS:
            diff = share["me"] - share["them"]
            if abs(diff) >= EARLY_GAP:
                return ("me" if diff > 0 else "them"), f"{pct('me')}, {pct('them')}"
        if n["me"] >= MIN_WORDS and n["them"] >= MIN_WORDS:
            gap = DECIDE_GAP if not self.decided else FLIP_GAP
            diff = share["me"] - share["them"]
            if abs(diff) >= gap:
                return ("me" if diff > 0 else "them"), f"{pct('me')}, {pct('them')}"
            return None
        if self.decided:
            return None  # only change a decision once both sides have spoken enough
        for side, other in (("me", "them"), ("them", "me")):
            if n[side] >= MIN_WORDS and n[other] < MIN_WORDS:
                if share[side] >= CLEAR_TELUGU:
                    return side, pct(side)
                if share[side] <= CLEAR_ENGLISH:
                    return other, pct(side)
        return None

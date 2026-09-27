# Finds sayings, idioms, slang and cultural references in what was said, even when speech recognition spells them a
# little differently ("కోటి విద్యలు కోటి కొరకే" for "కోటి విద్యలు కూటి కొరకే"). Exact matching (lexicon.find) caught
# only half of the listed sayings once they were spoken and transcribed (tools/check_idioms.py).
#   1. candidates: fuzzy match on a sound-alike romanized form (Telugu) or lowercase words (English), so small
#      spelling differences, merged or split words and a dropped letter still match;
#   2. Laya confirms each candidate with its own trained decision head (tools/train_sayings.py): is this line really
#      using that saying, or just sharing some words with it ("the dog's tail got hurt" isn't "a dog's tail stays
#      crooked")? Laya reads romanized Telugu (its tokenizer turns Telugu script into bytes).
# The sayings come from lexicon.json (hand-made) and sayings.json (tools/make_sayings.py).
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SAYINGS_PATH = os.path.join(HERE, "sayings.json")

# ---------- Telugu script -> Latin letters ----------
VOWELS = {"అ": "a", "ఆ": "aa", "ఇ": "i", "ఈ": "ii", "ఉ": "u", "ఊ": "uu", "ఋ": "ru", "ఎ": "e", "ఏ": "ee", "ఐ": "ai",
          "ఒ": "o", "ఓ": "oo", "ఔ": "au"}
SIGNS = {"ా": "aa", "ి": "i", "ీ": "ii", "ు": "u", "ూ": "uu", "ృ": "ru", "ె": "e", "ే": "ee", "ై": "ai", "ొ": "o",
         "ో": "oo", "ౌ": "au"}
CONSONANTS = {"క": "k", "ఖ": "kh", "గ": "g", "ఘ": "gh", "ఙ": "n", "చ": "ch", "ఛ": "chh", "జ": "j", "ఝ": "jh", "ఞ": "n",
              "ట": "t", "ఠ": "th", "డ": "d", "ఢ": "dh", "ణ": "n", "త": "t", "థ": "th", "ద": "d", "ధ": "dh", "న": "n",
              "ప": "p", "ఫ": "ph", "బ": "b", "భ": "bh", "మ": "m", "య": "y", "ర": "r", "ఱ": "r", "ల": "l", "ళ": "l",
              "వ": "v", "శ": "sh", "ష": "sh", "స": "s", "హ": "h"}
VIRAMA, ANUSVARA, VISARGA = "్", "ం", "ః"


def romanize(text):
    """Telugu script in simple Latin letters ("కుక్క తోక వంకర" -> "kukka tooka vankara"); other text unchanged."""
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch in CONSONANTS:
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if nxt == VIRAMA:
                out.append(CONSONANTS[ch])
                i += 2
                continue
            out.append(CONSONANTS[ch] + SIGNS.get(nxt, "a"))
            i += 2 if nxt in SIGNS else 1
            continue
        out.append(VOWELS.get(ch) or {ANUSVARA: "m", VISARGA: "h"}.get(ch) or ("" if ch in SIGNS or ch == VIRAMA else ch))
        i += 1
    return "".join(out)


def sound(text):
    """What a phrase sounds like, loosely: romanized, lowercase, no spaces, aspirates/long vowels/doubled letters
    folded, so speech-recognition spellings of the same words line up."""
    s = romanize(text).lower()
    s = re.sub(r"m(?=[kgcjtdnsrlyvh])", "n", s)  # ం before most consonants sounds like n: "vamkara" = "vankara"
    s = re.sub(r"[^a-z]", "", s)
    for a, b in (("chh", "c"), ("ch", "c"), ("kh", "k"), ("gh", "g"), ("jh", "j"), ("th", "t"), ("dh", "d"), ("ph", "p"),
                 ("bh", "b"), ("sh", "s"), ("w", "v"), ("aa", "a"), ("ii", "i"), ("ee", "e"), ("uu", "u"), ("oo", "o"),
                 ("z", "j"), ("q", "k"), ("f", "p")):
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)  # kukka -> kuka


def meaning(e):
    """What it means: its translation, else its note (lexicon.json's slang has only a note)."""
    return e.get("translate_as") or e.get("note", "")


def english_words(text):
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


# ---------- finding candidates ----------
MIN_SOUND = 7        # shorter forms (single words) must match exactly (lexicon.find already does that)
TE_SCORE = 76        # fuzzy score (0-100) for a Telugu candidate: loose on purpose (83% of held-out sayings
                     # are among the top 5 candidates, vs 72% at 84); Laya's check removes the false alarms
EN_SCORE = 90


def load_sayings(lexicon=None):
    """Every saying/idiom/slang/cultural entry: lexicon.json's idioms and slang, plus sayings.json."""
    items = {"te": [], "en": []}
    if lexicon is not None:
        for lang in ("te", "en"):
            items[lang] += [dict(e, source="lexicon") for e in lexicon.entries.get(lang, [])
                            if e.get("category") in ("idiom", "slang", "phrase")]
    if os.path.exists(SAYINGS_PATH):
        extra = json.load(open(SAYINGS_PATH, encoding="utf-8"))
        for lang in ("te", "en"):
            have = {e["id"] for e in items[lang]}
            items[lang] += [dict(e, source="sayings") for e in extra.get(lang, []) if e["id"] not in have]
    return items


class SayingFinder:
    """candidates(text, lang) -> [(entry, form, score)], best first."""

    def __init__(self, items):
        self.forms = {"te": [], "en": []}
        for lang, entries in items.items():
            for e in entries:
                for f in e.get("forms", []):
                    key = sound(f) if lang == "te" else english_words(f)
                    if len(key) >= (MIN_SOUND if lang == "te" else 5):
                        self.forms[lang].append((key, f, e))

    def candidates(self, text, lang, limit=5):
        from rapidfuzz import fuzz
        line = sound(text) if lang == "te" else english_words(text)
        cutoff = TE_SCORE if lang == "te" else EN_SCORE
        best = {}
        for key, form, e in self.forms[lang]:
            if len(key) > len(line) + 3:
                continue
            score = fuzz.partial_ratio(key, line, score_cutoff=cutoff)
            if score and score > best.get(e["id"], (0,))[0]:
                best[e["id"]] = (score, e, form)
        ranked = sorted(best.values(), key=lambda x: -x[0])[:limit]
        return [(e, form, score) for score, e, form in ranked]


# ---------- Laya: is the line really using it? ----------
HEAD_PATH = os.path.join(HERE, "models", "sayings_head.pt")
LABELS = ("yes", "no")
QUESTION = {
    "type": "choice",
    "instructions": "Is the speaker using this saying, expression or reference, not just some of the same words?",
    "criteria": {
        "yes": "the line uses it (maybe misspelled by speech recognition, or only its well-known first part)",
        "no": "the line only shares some words with it, uses them literally, or says something else",
    },
}
MIN_CONFIDENCE = 0.5  # tools/check_sayings.py picks it
NO_HEAD_SCORE = 95    # without the trained check, loose fuzzy matches gave a false alarm on 47% of everyday Telugu lines


def state(lang, line, saying, roman, means):
    """What Laya reads: Telugu romanized (its tokenizer turns Telugu script into bytes)."""
    if lang == "te":
        return {"speaker said": romanize(line), "saying": roman or romanize(saying), "it means": means}
    return {"speaker said": line, "saying": saying, "it means": means}


class SayingJudge:
    """find(text, lang) -> [(entry, confidence)]: fuzzy candidates confirmed by Laya's trained head. Shares
    decide.Decider's Laya and lock; without a trained head, the fuzzy candidates as they are."""

    def __init__(self, decider, finder, head_path=HEAD_PATH):
        from reply import load_head
        self.agent, self.lock, self.torch = decider.agent, decider.lock, decider.torch
        self.finder = finder
        self.q = self.agent._to_internal(QUESTION)
        self.head = load_head(self.agent, head_path) if head_path and os.path.exists(head_path) else None

    def probs(self, lang, text, cands):
        from reply import head_probs
        states = [state(lang, text, form, e.get("roman", ""), meaning(e)) for e, form, _ in cands]
        with self.lock:
            p = head_probs(self.agent, self.head, states, self.q)
            if self.torch.backends.mps.is_available():
                self.torch.mps.empty_cache()
        return [float(x[0]) for x in p]  # P(yes)

    def find(self, text, lang):
        cands = self.finder.candidates(text, lang)
        if not cands or self.head is None:  # no trained check (models/sayings_head.pt): only near-exact matches
            return [(e, score / 100) for e, _, score in cands if score >= NO_HEAD_SCORE]
        return [(e, p) for (e, _, _), p in zip(cands, self.probs(lang, text, cands)) if p >= MIN_CONFIDENCE]

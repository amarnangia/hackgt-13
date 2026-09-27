# Finds sayings, idioms, slang and cultural references in what was said, even when speech recognition spells them a
# little differently ("కోటి విద్యలు కోటి కొరకే" for "కోటి విద్యలు కూటి కొరకే"). Exact matching (lexicon.find) caught
# only half of the listed sayings once they were spoken and transcribed (tools/check_idioms.py).
#   1. matching: sayings of several words by a fuzzy match on a sound-alike romanized form (Telugu) or lowercase words
#      (English), so small spelling differences, merged or split words and a dropped letter still match; short ones
#      (a word or two: slang, a dish, a festival) exactly, as whole words (Telugu may add an ending: సంక్రాంతి-కి);
#   2. no model check: we tried to have Laya confirm each match ("is this line really using that saying?",
#      tools/train_sayings.py) and it never learned: its frozen encoder doesn't represent Telugu spelling (a linear probe
#      on it: 57%), and on English the trained head stayed at chance as yes/no and as three options (Laya as shipped:
#      worse than chance). The match itself is right far more often (tools/check_sayings.py, check_idioms.py).
#      SayingJudge still uses a trained head if models/sayings_head.pt ever exists (English only).
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
# Forms of fewer words must appear exactly, as whole words; longer ones may be misspelled. Telugu words are long, so
# two are enough to tell a phrase apart ("చెవిలో పువ్వు"); in English "that's lit" fuzzily matched "that's it".
FUZZY_WORDS = {"te": 2, "en": 3}
TE_SCORE = 84        # fuzzy score (0-100) for a Telugu saying of 2+ words (tools/check_sayings.py, picked on validation:
                     # 71% of held-out sayings caught, 3% of everyday lines with a wrong card; at 80: 79% and 4%)
EN_SCORE = 88


# Said all the time without meaning anything special; the generated slang list had them
TOO_COMMON = {"i don't know", "idk", "oh my god", "oh my gosh", "omg", "never mind", "keep it", "okay", "ok", "for real",
              "no way", "what's up", "thank you", "my bad", "you know", "i mean", "like", "literally", "honestly", "same",
              "yeah", "cool", "nice", "wow", "bro", "dude", "guys", "hello", "hi", "bye", "sorry", "please", "yes", "no"}


def load_sayings(lexicon=None):
    """Every saying/idiom/slang/cultural entry: lexicon.json's idioms and slang, plus sayings.json."""
    items = {"te": [], "en": []}
    if lexicon is not None:
        for lang in ("te", "en"):
            # (not its everyday phrases, "చిన్నప్పుడు", "take care": lexicon.find already gives those their cards)
            items[lang] += [dict(e, source="lexicon") for e in lexicon.entries.get(lang, [])
                            if e.get("category") in ("idiom", "slang")]
    if os.path.exists(SAYINGS_PATH):
        extra = json.load(open(SAYINGS_PATH, encoding="utf-8"))
        for lang in ("te", "en"):
            have = {e["id"] for e in items[lang]}
            key = sound if lang == "te" else english_words
            said = {key(f) for e in items[lang] for f in e["forms"]}  # the same saying already in lexicon.json
            items[lang] += [dict(e, source="sayings") for e in extra.get(lang, [])
                            if e["id"] not in have and not any(english_words(f) in TOO_COMMON for f in e["forms"])
                            and not any(key(f) in said for f in e["forms"])]
    return items


class SayingFinder:
    """candidates(text, lang) -> [(entry, form, score)], best first."""

    def __init__(self, items):
        self.forms = {"te": [], "en": []}
        for lang, entries in items.items():
            for e in entries:
                for f in e.get("forms", []):
                    key = sound(f) if lang == "te" else english_words(f)
                    spaced = " ".join(sound(w) for w in f.split()) if lang == "te" else key
                    if len(key) >= (MIN_SOUND if lang == "te" else 5):
                        self.forms[lang].append((key, spaced, f, e))

    def candidates(self, text, lang, limit=5):
        from rapidfuzz import fuzz
        line = sound(text) if lang == "te" else english_words(text)
        words = f" {english_words(text)} " if lang == "en" else " " + " ".join(sound(w) for w in text.split()) + " "
        cutoff = TE_SCORE if lang == "te" else EN_SCORE
        best = {}
        for key, spaced, form, e in self.forms[lang]:
            if len(key) > len(line) + 3:
                continue
            if len(form.split()) < FUZZY_WORDS[lang]:  # short: whole words, exactly ("slaying" isn't "saying"); in Telugu
                # the last word may carry an ending (సంక్రాంతి-కి, ఆటో-లో)
                exact = f" {spaced} " in words if lang == "en" else f" {spaced}" in words
                score = 100 if exact else 0
            else:
                score = fuzz.partial_ratio(key, line, score_cutoff=cutoff)
            if score and score > best.get(e["id"], (0,))[0]:
                best[e["id"]] = (score, e, form)
        ranked = sorted(best.values(), key=lambda x: -x[0])[:limit]
        return [(e, form, score) for score, e, form in ranked]


# ---------- Laya: is the line really using it? ----------
HEAD_PATH = os.path.join(HERE, "models", "sayings_head.pt")
LABELS = ("uses_it", "literal", "different")
# Three concrete options, like reply.py's question: as a bare yes/no, Laya's head never learned (stayed at a coin flip).
QUESTION = {
    "type": "choice",
    "instructions": "The speaker's line matched a saying, idiom, slang word or cultural reference. How is it used?",
    "criteria": {
        "uses_it": "they use it with its special meaning (an idiom meant as an idiom, slang as slang, the thing itself)",
        "literal": "the same words, but meant literally, not as the saying",
        "different": "a different thing: the words only look or sound similar",
    },
}
MIN_CONFIDENCE = 0.5  # tools/check_sayings.py picks it


def match_score(lang, form, text):
    """How closely `text` contains `form` (0-100), as the fuzzy matcher sees it."""
    from rapidfuzz import fuzz
    key = sound if lang == "te" else english_words
    return fuzz.partial_ratio(key(form), key(text))


def state(lang, line, saying, roman, means, score):
    """What Laya reads: Telugu romanized (its tokenizer turns Telugu script into bytes), and how closely the line
    sounds like the saying (Laya can't compare spellings letter by letter itself: without this it didn't learn)."""
    if lang == "te":
        line, saying = romanize(line), roman or romanize(saying)
    return {"speaker said": line, "saying": saying, "sounds like it": f"{round(score)} out of 100", "it means": means}


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
        states = [state(lang, text, form, e.get("roman", ""), meaning(e), score) for e, form, score in cands]
        with self.lock:
            p = head_probs(self.agent, self.head, states, self.q)
            if self.torch.backends.mps.is_available():
                self.torch.mps.empty_cache()
        return [float(x[0]) for x in p]  # P(uses_it)

    def find(self, text, lang):
        cands = self.finder.candidates(text, lang)
        # Laya checks English only: whether an idiom is meant ("break a leg!") or literal ("I broke my leg"). Its frozen
        # encoder can't compare Telugu spellings (trained on that, it stayed at a coin flip), so Telugu goes by the match.
        if not cands or self.head is None or lang != "en":
            return [(e, score / 100) for e, _, score in cands]
        return [(e, p) for (e, _, _), p in zip(cands, self.probs(lang, text, cands)) if p >= MIN_CONFIDENCE]

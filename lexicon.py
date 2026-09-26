# The hard-coded words and phrases in lexicon.json: glossary substitution before translation, and
# lookups for image / explanation cards. Pure Python so both virtualenvs can import it.
import json
import os
import re

INDIC_LETTERS = "ऀ-෿"  # Devanagari through Sinhala: covers Hindi, Telugu, Tamil, Kannada, ...
ENGLISH_ROMANS = {"auto", "bus", "carriage", "cinema", "tiffin", "ammo"}  # romanized words that are English words too


class Lexicon:
    def __init__(self, path=os.path.join(os.path.dirname(__file__), "lexicon.json")):
        data = json.load(open(path, encoding="utf-8"))
        self.entries = {lang: items for lang, items in data.items() if not lang.startswith("_")}
        # Her Telugu as the speech service sometimes writes it, in English letters ("Bangaram, pulihora tinnava?")
        self._roman = {lang: sorted(((re.compile(rf"(?<![A-Za-z]){re.escape(r)}(?![A-Za-z])", re.IGNORECASE), e)
                                     for e in items for r in [(e.get("roman") or "").strip(" ,?^").lower()]
                                     if len(r) >= 3 and r not in ENGLISH_ROMANS), key=lambda pe: -len(pe[0].pattern))
                       for lang, items in self.entries.items() if lang != "en"}
        self._patterns = {}
        for lang, items in self.entries.items():
            forms = sorted(((f, e) for e in items for f in e["forms"]), key=lambda fe: -len(fe[0]))
            # Whole-word matches only, so సంత (market) doesn't fire inside సంతోషం (happiness).
            letters = INDIC_LETTERS if lang != "en" else "A-Za-z"
            # A form starting with "^" only matches at the start of what was said (e.g. నాన్న calling the listener).
            self._patterns[lang] = [
                (re.compile((r"^\s*" if f.startswith("^") else rf"(?<![{letters}])")
                            + rf"{re.escape(f.lstrip('^'))}(?![{letters}])", re.IGNORECASE), f, e) for f, e in forms
            ]

    def find(self, text, lang, roman=False):
        """Entries mentioned in `text`, in order of first appearance, each once. roman=True also finds words written
        in English letters (by their `roman` spelling)."""
        # Longest forms first; a word inside a longer phrase already found is part of that phrase, not a mention of its
        # own: "annam" (rice) in "annam tinnava?" (did you eat?) isn't about rice.
        hits, taken = {}, []
        patterns = [(p, e) for p, _, e in self._patterns.get(lang, [])] + (self._roman.get(lang, []) if roman else [])
        for pattern, entry in sorted(patterns, key=lambda pe: -len(pe[0].pattern)) if roman else patterns:
            if entry["id"] in hits:
                continue
            for m in pattern.finditer(text):
                if not any(s <= m.start() and m.end() <= e for s, e in taken):
                    hits[entry["id"]] = (m.start(), entry)
                    taken.append(m.span())
                    break
        return [e for _, e in sorted(hits.values(), key=lambda h: h[0])]

    def leftover(self, text, lang, entries):
        """`text` without the words of these entries (in either script): what's left to understand."""
        ids = {e["id"] for e in entries}
        for pattern, _, entry in self._patterns.get(lang, []):
            if entry["id"] in ids:
                text = pattern.sub(" ", text)
        for pattern, entry in self._roman.get(lang, []):
            if entry["id"] in ids:
                text = pattern.sub(" ", text)
        return text

    def substitute(self, text, lang):
        """Replace known words with their fixed English so the translator can't get them wrong."""
        for pattern, form, entry in self._patterns.get(lang, []):
            # Inflected forms carry their own grammar: ఆటోలో is "in an auto-rickshaw", not just "auto-rickshaw".
            if entry.get("substitute") is False:
                continue  # the translator already knows this word; substituting it garbled sentences
            english = entry.get("translate_forms", {}).get(form, entry.get("translate_as"))
            if english:
                text = pattern.sub(english, text)
        return text


def indic_share(text):
    """Fraction of words written in an Indian script (Muse writes English words in Latin letters)."""
    words = re.findall(rf"[{INDIC_LETTERS}A-Za-z]+", text)
    if not words:
        return 0.0
    return sum(bool(re.match(rf"[{INDIC_LETTERS}]", w)) for w in words) / len(words)

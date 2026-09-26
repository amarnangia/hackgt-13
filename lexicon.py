# The hard-coded words and phrases in lexicon.json: glossary substitution before translation, and
# lookups for image / explanation cards. Pure Python so both virtualenvs can import it.
import json
import os
import re

INDIC_LETTERS = "ऀ-෿"  # Devanagari through Sinhala: covers Hindi, Telugu, Tamil, Kannada, ...


class Lexicon:
    def __init__(self, path=os.path.join(os.path.dirname(__file__), "lexicon.json")):
        data = json.load(open(path, encoding="utf-8"))
        self.entries = {lang: items for lang, items in data.items() if not lang.startswith("_")}
        self._patterns = {}
        for lang, items in self.entries.items():
            forms = sorted(((f, e) for e in items for f in e["forms"]), key=lambda fe: -len(fe[0]))
            # Whole-word matches only, so సంత (market) doesn't fire inside సంతోషం (happiness).
            letters = INDIC_LETTERS if lang != "en" else "A-Za-z"
            self._patterns[lang] = [
                (re.compile(rf"(?<![{letters}]){re.escape(f)}(?![{letters}])", re.IGNORECASE), f, e) for f, e in forms
            ]

    def find(self, text, lang):
        """Entries mentioned in `text`, in order of first appearance, each once."""
        hits = {}
        for pattern, _, entry in self._patterns.get(lang, []):
            m = pattern.search(text)
            if m and entry["id"] not in hits:
                hits[entry["id"]] = (m.start(), entry)
        return [e for _, e in sorted(hits.values(), key=lambda h: h[0])]

    def substitute(self, text, lang):
        """Replace known words with their fixed English so the translator can't get them wrong."""
        for pattern, form, entry in self._patterns.get(lang, []):
            # Inflected forms carry their own grammar: ఆటోలో is "in an auto-rickshaw", not just "auto-rickshaw".
            english = entry.get("translate_forms", {}).get(form, entry.get("translate_as"))
            if english:
                text = pattern.sub(english, text)
        return text

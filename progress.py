# Which Telugu words the listener knows, so translations can keep them in Telugu ("translate less over time").
# A word becomes known after it has come up LEARN_AFTER times; clicking it in the overlay makes it unknown
# again. Saved per person in progress.json (gitignored).
import json
import os
import re
import threading

LEARN_AFTER = 1  # keep a word in Telugu from its second hearing


class Progress:
    def __init__(self, lexicon, lang, path="progress.json", learn_after=LEARN_AFTER):
        self.path, self.learn_after, self.lang = path, learn_after, lang
        self.entries = {e["id"]: e for e in lexicon.entries.get(lang, []) if "roman" in e}
        self.lock = threading.Lock()
        saved = json.load(open(path)) if os.path.exists(path) else {}
        self.heard = saved.get("heard", {})
        self.forgotten = set(saved.get("forgotten", []))  # clicked in the overlay; stays translated

    def known(self, entry_id):
        entry = self.entries.get(entry_id)
        if not entry:
            return False
        if entry_id in self.forgotten:  # clicked "I don't know this": relearn it from zero
            return self.heard.get(entry_id, 0) >= self.learn_after
        return entry.get("start_known", False) or self.heard.get(entry_id, 0) >= self.learn_after

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

    def heard_words(self, hits):
        """Count one more hearing of each word in this line."""
        with self.lock:
            for entry in hits:
                if entry["id"] in self.entries:
                    self.heard[entry["id"]] = self.heard.get(entry["id"], 0) + 1
            self._save()

    def forget(self, entry_id):
        with self.lock:
            self.forgotten.add(entry_id)
            self.heard[entry_id] = 0
            self._save()

    def _save(self):
        json.dump({"heard": self.heard, "forgotten": sorted(self.forgotten)}, open(self.path, "w"), indent=1)

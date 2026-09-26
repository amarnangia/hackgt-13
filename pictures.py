# Picture pop-ups: when a line mentions something the grandkid may not know (pulihora, a pattu saree, muggulu),
# show a picture of it. Candidates come from the picture library (images/library.json, built by
# tools/build_images.py) matched in the Telugu (via lexicon.json) or the English, plus other nouns in the English
# line, which are looked up on Wikipedia live and cached. Laya picks which one, if any, needs a picture.
import json
import os
import re
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "images", "cache")
HEADERS = {"User-Agent": "hackgt-call-translator/0.1 (https://github.com/amarnangia/hackgt-13)"}
REPEAT_AFTER_S = 300  # don't show the same picture again within 5 minutes
GENERIC = {"village_market", "rice", "curry", "wedding", "puja", "monsoon", "thali", "chai", "temple", "paddy_field"}
WHAT_IS_IT = {
    "indian_food": "an Indian dish, snack, sweet or ingredient",
    "indian_place": "a place, town, building or landmark in India",
    "indian_thing": "Indian clothing, jewelry, an object, a dance, music or a festival",
    "person": "a person's name or a family member",
    "everyday": "an everyday thing found anywhere in the world",
}

PICK = {
    "type": "choice",
    "instructions": "A grandchild raised in America is listening to their grandmother from India. "
                    "Which of these things would they need to see a picture of to understand?",
}


class PictureFinder:
    def __init__(self, decider=None):
        data = json.load(open(os.path.join(HERE, "images", "library.json"), encoding="utf-8"))
        self.items = data["items"]
        self.by_lexicon = {lid: iid for iid, it in self.items.items() for lid in it.get("lexicon_ids", [])}
        # Our own one-line notes read better than Wikipedia's first sentence ("Adhirasam, attarasalu,, kajjaya...")
        lexicon = json.load(open(os.path.join(HERE, "lexicon.json"), encoding="utf-8"))
        notes = {e["id"]: e.get("note") for lang, entries in lexicon.items() if not lang.startswith("_") for e in entries}
        # the first linked word's note: Bhogi's picture explains Bhogi, not Bhogi fruits (its second word)
        self.notes = {iid: next(notes[lid] for lid in it["lexicon_ids"] if notes.get(lid))
                      for iid, it in self.items.items() if any(notes.get(lid) for lid in it.get("lexicon_ids", []))}
        aliases = sorted(((a.lower(), iid) for iid, it in self.items.items() for a in it.get("aliases", [])),
                         key=lambda x: -len(x[0]))
        self.alias_patterns = [(re.compile(rf"(?<![A-Za-z]){re.escape(a)}(?![A-Za-z])", re.IGNORECASE), iid)
                               for a, iid in aliases]
        self.decider = decider  # decide.Decider (Laya); without it, the first library match wins
        self.shown = {}         # item id -> when it was last shown
        self.web_cache = self._load_web_cache()
        self.nlp = None

    # ---------- candidates ----------
    def candidates(self, english, lexicon_hits):
        """[(key, label, description)] for things mentioned in the line; key is a library id or 'web:<noun>'."""
        found, seen = [], set()

        def add(iid):
            if iid not in seen:
                seen.add(iid)
                it = self.items[iid]
                found.append((iid, it["name"], it.get("description", "")))

        for entry in lexicon_hits:  # exact: what grandma said in Telugu
            if entry["id"] in self.by_lexicon:
                add(self.by_lexicon[entry["id"]])
        covered = english
        for pattern, iid in self.alias_patterns:  # what the translation mentions
            m = pattern.search(covered)
            if m:
                add(iid)
                covered = covered[:m.start()] + " " * len(m.group(0)) + covered[m.end():]
        for noun in self._nouns(covered):  # anything else: look it up on the web if Laya picks it
            key = "web:" + noun.lower()
            if key not in seen:
                seen.add(key)
                found.append((key, noun, ""))
        return found

    def _nouns(self, text):
        if self.nlp is None:
            import spacy
            self.nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
        skip = {"i", "you", "we", "they", "he", "she", "it", "me", "us", "them", "something", "anything", "everything",
                "someone", "everyone", "time", "day", "today", "tomorrow", "yesterday", "week", "month", "year", "thing",
                "things", "people", "way", "lot", "dear", "nanna", "photo", "photos", "whatsapp", "phone", "call"}
        doc = self.nlp(text)
        nouns = []
        for chunk in doc.noun_chunks:
            words = [t for t in chunk if t.pos_ in ("NOUN", "PROPN", "ADJ") and t.text.lower() not in skip]
            if words and words[-1].pos_ in ("NOUN", "PROPN"):
                nouns.append(" ".join(t.text for t in words))
        # spaCy doesn't know Telugu words and tags them as adjectives or verbs (ulavacharu, pootharekulu); any word
        # that isn't English at all is a candidate too.
        in_nouns = {w.lower() for n in nouns for w in n.split()}
        for t in doc:
            w = t.text
            if w.isalpha() and len(w) >= 4 and w.lower() not in skip and w.lower() not in in_nouns \
                    and not self._ordinary_english(w):
                nouns.append(w)
        return nouns

    # ---------- choosing ----------
    def pick(self, english, lexicon_hits, known=lambda lexicon_id: False):
        """The library id or web noun to show a picture of, or None.

        Tested on 25 lines, Laya alone got 14/25: good at choosing between several things, but it often said
        "no picture" for a lone pulihora or Charminar and picked everyday words (sister, lunch). So:
          - Indian library items are picture-worthy by construction (unless the grandkid knows the word);
            American ones never pop up.
          - Web lookups only for words that aren't ordinary English (not in the system dictionary).
          - One eligible thing: show it. Several: Laya picks. Only web words: Laya decides if any need a picture.
        """
        now = time.monotonic()
        known_items = {self.by_lexicon[e["id"]] for e in lexicon_hits if e["id"] in self.by_lexicon and known(e["id"])}
        fresh = lambda key: now - self.shown.get(key, -1e9) > REPEAT_AFTER_S
        library, web = [], []
        for key, label, desc in self.candidates(english, lexicon_hits):
            if not fresh(key):
                continue
            if key.startswith("web:"):
                if not self._ordinary_english(key[4:]):
                    web.append((key, label, desc))
            elif self.items[key].get("region") != "us" and key not in known_items:
                library.append((key, label, desc))
        specific = [c for c in library if c[0] not in GENERIC]  # gongura over "market" when both come up
        library = specific or library
        if len(library) == 1:
            key = library[0][0]
        elif library:
            key = self._ask_laya(english, library)
        else:
            # Words not in the library: Laya classifies each; only Indian foods, places and things get a picture.
            # (Asking "does this need a picture?" directly worked poorly; its category answers are reliable.)
            worth = [c for c in web[:3] if self._indian_thing(english, c)]
            key = worth[0][0] if len(worth) == 1 else self._ask_laya(english, worth) if worth else None
        if key:
            self.shown[key] = now
        return key

    def _ask_laya(self, english, cands):
        """Several candidates: Laya picks the one the grandkid most needs to see."""
        if self.decider is None:
            return cands[0][0]
        criteria = {f"option{i}": (f"{label}: {desc[:80]}" if desc else label) for i, (key, label, desc) in enumerate(cands)}
        answer = self.decider.choose(english, {**PICK, "criteria": criteria})
        return cands[int(answer[len("option"):])][0]

    def _indian_thing(self, english, cand):
        """Look the word up (we need its picture anyway), then let Laya classify it using the Wikipedia summary.
        Without the summary Laya called boorelu and ulavacharu "everyday things": it has never seen them."""
        if self.decider is None:
            return False
        card = self.card(cand[0])
        if not card or not card.get("description"):
            return False  # nothing on Wikipedia, so no picture to show anyway
        answer = self.decider.choose(english, {"type": "choice", "instructions": f'In this sentence, what is "{cand[1]}"?',
                                               "criteria": WHAT_IS_IT}, word=cand[1], wikipedia=card["description"])
        return answer in ("indian_food", "indian_place", "indian_thing")

    def _ordinary_english(self, phrase):
        if not hasattr(self, "_dictionary"):
            try:
                self._dictionary = {w.strip().lower() for w in open("/usr/share/dict/words")}
            except OSError:
                self._dictionary = set()
        words = re.findall(r"[A-Za-z]+", phrase.lower())
        return bool(words) and all(w in self._dictionary or w.rstrip("s") in self._dictionary for w in words)

    # ---------- showing ----------
    def card(self, key):
        """{name, description, image} for a library id, or for a web noun (may fetch from Wikipedia)."""
        if not key.startswith("web:"):
            it = self.items[key]
            return {"id": key, "name": it["name"], "description": self.notes.get(key) or it.get("description", ""), "image": it["image"],
                    "category": it.get("category", ""), "kind": it.get("kind", it.get("category", "")),
                    "lexicon_ids": it.get("lexicon_ids", [])}
        noun = key[4:]
        if noun not in self.web_cache:
            self.web_cache[noun] = self._fetch_web(noun)
            self._save_web_cache()
        hit = self.web_cache[noun]
        return {"id": key, **hit} if hit else None

    def _fetch_web(self, noun):
        import requests

        try:
            r = requests.get("https://en.wikipedia.org/w/rest.php/v1/search/page", headers=HEADERS, timeout=5,
                             params={"q": noun, "limit": 3})
            # Only a page *about* the word: "Sanvi" (a name) otherwise matched a 2011 Telugu film, and "boorelu"
            # the generic "Dumpling" page.
            words = noun.lower().split()
            pages = [pg for pg in r.json().get("pages", []) if all(w in pg["title"].lower() for w in words)]
            if not pages:
                return None
            title = pages[0]["title"]
            s = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")),
                             headers=HEADERS, timeout=5).json()
            thumb = (s.get("thumbnail") or {}).get("source")
            if not thumb:
                return None
            os.makedirs(CACHE_DIR, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "_", noun.lower()).strip("_")
            path = os.path.join(CACHE_DIR, slug + ".jpg")
            with open(path, "wb") as f:
                f.write(requests.get(thumb, headers=HEADERS, timeout=8).content)
            desc = re.match(r"(.+?[.!?])(\s|$)", s.get("extract", "") or "")
            return {"name": noun.title(), "description": desc.group(1) if desc else "", "image": f"images/cache/{slug}.jpg",
                    "category": "web", "credit": s.get("content_urls", {}).get("desktop", {}).get("page", "")}
        except Exception:
            return None

    def _load_web_cache(self):
        path = os.path.join(CACHE_DIR, "cache.json")
        return json.load(open(path)) if os.path.exists(path) else {}

    def _save_web_cache(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        json.dump(self.web_cache, open(os.path.join(CACHE_DIR, "cache.json"), "w"), indent=1)

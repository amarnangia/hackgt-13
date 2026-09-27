# Picture pop-ups: when a line mentions something the grandkid may not know (pulihora, a pattu saree, muggulu),
# show a picture of it. Candidates come from the picture library (images/library.json, built by
# tools/build_images.py) matched in the Telugu (via lexicon.json) or the English, plus other nouns in the English
# line, which are looked up on Wikipedia and cached. Laya picks which one, if any, needs a picture.
#
# Nothing here waits on the network during a call: a word that isn't in the cache yet is looked up in the background
# and gets its picture the next time it comes up. tools/prefetch_pictures.py fills the cache ahead of time with
# hundreds of Indian foods, festivals, places and people.
import json
import queue
import os
import re
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "images", "cache")
HEADERS = {"User-Agent": "hackgt-call-translator/0.1 (https://github.com/amarnangia/hackgt-13)"}
REPEAT_AFTER_S = float("inf")  # each picture once per call (one PictureFinder per call): the first time it comes up, never again
SKIP_KNOWN = False  # pictures show for words they already know too (the captions still keep those in Telugu): on every
                    # call, the first mention of pulihora gets its picture, even once they've learned it
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
PICK_FOR_HER = {
    "type": "choice",
    "instructions": "A grandmother in India is listening to her grandchild who lives in America. "
                    "Which of these things would she need to see a picture of to understand?",
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
        self.shown_her = {}     # the same, for pictures of American things shown for her (--two-way)
        self.web_cache = self._load_web_cache()
        self.cache_lock = threading.Lock()
        self.to_fetch = queue.Queue()  # words to look up in the background (never while a line waits)
        self.fetching = set()
        threading.Thread(target=self._fetcher, daemon=True).start()
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
          - Indian library items are picture-worthy by construction (known words too: SKIP_KNOWN);
            American ones never pop up.
          - Web lookups only for words that aren't ordinary English (not in the system dictionary).
          - One eligible thing: show it. Several: Laya picks. Only web words: Laya decides if any need a picture.
        """
        now = time.monotonic()
        known_items = {self.by_lexicon[e["id"]] for e in lexicon_hits if e["id"] in self.by_lexicon and known(e["id"])} if SKIP_KNOWN else set()
        fresh = lambda key: key not in self.shown or now - self.shown[key] > REPEAT_AFTER_S
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

    def pick_from_words(self, lexicon_hits, known=lambda lexicon_id: False):
        """Before the English is back: the picture for her words, when they name exactly one library thing the grandkid
        doesn't know (gavvalu, Bhogi, NTR). Several (or none): None, and pick() decides with the English."""
        now = time.monotonic()
        items = []
        for e in lexicon_hits:
            iid = self.by_lexicon.get(e["id"])
            if (iid and iid not in items and not (SKIP_KNOWN and known(e["id"])) and self.items[iid].get("region") != "us"
                    and (iid not in self.shown or now - self.shown[iid] > REPEAT_AFTER_S)):
                items.append(iid)
        specific = [i for i in items if i not in GENERIC]
        items = specific or items
        if len(items) != 1:
            return None
        self.shown[items[0]] = now
        return items[0]

    def pick_for_her(self, english):
        """The other way (--two-way): the American thing in what the grandkid said that she may never have seen
        (Thanksgiving, s'mores, prom, a school bus), or None. American library items she'd know already have a Telugu
        word in our list (mango, rice), so they don't count; other names come from the cache of American things
        (tools/prefetch_pictures.py), never a live look-up. One: show it; several: Laya picks."""
        now = time.monotonic()
        fresh = lambda key: key not in self.shown_her or now - self.shown_her[key] > REPEAT_AFTER_S
        cands, covered = [], english
        for pattern, iid in self.alias_patterns:
            it = self.items[iid]
            m = pattern.search(covered)
            if m and it.get("region") == "us" and not it.get("lexicon_ids") and fresh(iid) and iid not in {c[0] for c in cands}:
                cands.append((iid, it["name"], it.get("description", "")))
                covered = covered[:m.start()] + " " * len(m.group(0)) + covered[m.end():]
        for noun in self._nouns(covered):
            name = self._cached_noun(noun, american=True)
            hit = self.web_cache.get(name) if name else None
            if hit and hit.get("american") and fresh("web:" + name) and "web:" + name not in {c[0] for c in cands}:
                cands.append(("web:" + name, hit["name"], hit.get("description", "")))
        if not cands:
            return None
        key = cands[0][0] if len(cands) == 1 else self._ask_laya(english, cands[:4], PICK_FOR_HER)
        self.shown_her[key] = now
        return key

    def _ask_laya(self, english, cands, question=PICK):
        """Several candidates: Laya picks the one the listener most needs to see."""
        if self.decider is None:
            return cands[0][0]
        criteria = {f"option{i}": (f"{label}: {desc[:80]}" if desc else label) for i, (key, label, desc) in enumerate(cands)}
        answer = self.decider.choose(english, {**question, "criteria": criteria})
        return cands[int(answer[len("option"):])][0]

    def _indian_thing(self, english, cand):
        """Look the word up (we need its picture anyway), then let Laya classify it using the Wikipedia summary.
        Without the summary Laya called boorelu and ulavacharu "everyday things": it has never seen them."""
        if self.decider is None:
            return False
        card = self.card(cand[0])  # only what's cached; anything new is looked up in the background for next time
        if not card or not card.get("description"):
            return False  # nothing on Wikipedia (or not looked up yet), so no picture to show now
        hit = self.web_cache.get(card["noun"])
        if hit.get("indian") is None:  # asked once per word, then remembered (prefetched ones come already answered)
            answer = self.decider.choose(english, {"type": "choice", "instructions": f'In this sentence, what is "{cand[1]}"?',
                                                   "criteria": WHAT_IS_IT}, word=cand[1], wikipedia=card["description"])
            hit["indian"] = answer in ("indian_food", "indian_place", "indian_thing")
            self._save_web_cache()
        return hit["indian"]

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
        """{name, description, image} for a library id, or for a web noun from the cache (a noun that isn't cached is
        queued for a background look-up, and this returns None)."""
        if not key.startswith("web:"):
            it = self.items[key]
            return {"id": key, "name": it["name"], "description": self.notes.get(key) or it.get("description", ""), "image": it["image"],
                    "category": it.get("category", ""), "kind": it.get("kind", it.get("category", "")),
                    "lexicon_ids": it.get("lexicon_ids", [])}
        noun = self._cached_noun(key[4:])
        if noun is None:
            self._queue(key[4:])
            return None
        hit = self.web_cache[noun]
        return {"id": key, "noun": noun, **{k: v for k, v in hit.items() if k != "indian"}} if hit else None

    def _cached_noun(self, noun, american=False):
        """The cache key for a noun: itself, or for "bhogi bonfires" a word in it that's cached ("bhogi"). American
        names are often plain English words ("pumpkin pie", "s'mores"), so american=True doesn't skip those."""
        noun = noun.lower()
        if noun in self.web_cache:
            return noun
        for w in noun.split():
            if len(w) >= 4 and self.web_cache.get(w) and (american or not self._ordinary_english(w)):
                return w
        return None

    def _queue(self, noun):
        noun = noun.lower()
        with self.cache_lock:
            if noun in self.fetching:
                return
            self.fetching.add(noun)
        self.to_fetch.put(noun)

    def _fetcher(self):
        while True:
            noun = self.to_fetch.get()
            hit = self._fetch_web(noun)
            with self.cache_lock:
                self.web_cache[noun] = hit
                self.fetching.discard(noun)
            self._save_web_cache()

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
        return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}

    def _save_web_cache(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        with self.cache_lock:
            data = json.dumps(self.web_cache, indent=1, ensure_ascii=False)
        tmp = os.path.join(CACHE_DIR, "cache.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, os.path.join(CACHE_DIR, "cache.json"))

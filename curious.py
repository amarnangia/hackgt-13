# The overlay's "Curious?" questions (build-plan step 4): after each of her lines, up to two questions the grandkid
# might want to ask the app, each a sentence stem with a blank filled from what she said, sent as a "curious"
# message with its answer when we already have one (the overlay asks the LLM for the rest, see Captioner.answer).
#
#   What does "___" mean?          proverbs, phrases, slang
#   What is ___? / Who is ___?     foods, festivals, things; relatives
#   Where is ___?                  places she mentioned
#   Why do people say "___"?       blessings and customs
#   How do I say "___" in Telugu?  a reply, when she asked you something
#
# Laya decides the two things rules can't: which of several things in a line is most worth asking about (a
# grandchild raised in America), and, when she asks you something, which kind of question it is, so the right
# reply can be offered in respectful Telugu. Words the grandkid probably knows (progress.py) get no question.
import re

from decide import is_question

MAX_PER_LINE = 2
# Which of her words most need a question, before any model: the word whose picture just popped up, then things and
# sayings that only make sense with an explanation, then everyday phrases, family words and plain words.
EXPLAIN_FIRST = {"idiom", "culture", "festival", "food", "place", "clothing", "vehicle"}

RANK = {"type": "choice", "instructions": "A grandchild raised in America is listening to their grandmother from India. "
                                          "Which of these would they most want explained?"}

# Replies to her questions, in the respectful form: (what she's asking, the reply in English, Telugu, how to say it)
REPLIES = {
    "ate": ("asking if they have eaten", "Yes, I ate. Did you eat?", "అవును, తిన్నాను. మీరు తిన్నారా?", "Avunu, tinnanu. Meeru tinnara?"),
    "wellbeing": ("asking how they are or if they are well", "I'm well. How are you?", "నేను బాగున్నాను. మీరు ఎలా ఉన్నారు?",
                  "Nenu bagunnanu. Meeru ela unnaru?"),
    "studies": ("asking about school, studies or exams", "Studies are going well.", "చదువు బాగా జరుగుతోంది.", "Chaduvu baaga jarugutondi."),
    "coming": ("asking when they will come or visit", "I'll come soon.", "త్వరలో వస్తాను.", "Tvaralo vastanu."),
    "doing": ("asking what they are doing", "Nothing much, just talking to you.", "ఏమీ లేదు, మీతో మాట్లాడుతున్నాను.",
              "Emi ledu, meeto matladutunnanu."),
    "health": ("asking about their health, sleep or if they are sick", "I'm healthy, don't worry.", "నేను బాగానే ఉన్నాను, కంగారు పడకండి.",
               "Nenu baagane unnanu, kangaru padakandi."),
    "hear": ("asking if they can hear", "Yes, I can hear you.", "అవును, వినిపిస్తోంది.", "Avunu, vinipistondi."),
    "like": ("asking if they like something", "Yes, I like it a lot.", "అవును, నాకు చాలా ఇష్టం.", "Avunu, naaku chala ishtam."),
    "okay": ("telling them to do something, like take care or study well", "Okay, I will.", "సరే, అలాగే.", "Sare, alage."),
}
# Clear cases by keyword; Laya decides the rest, and only when it's fairly sure (unsure, it said "how are you" to
# "Did you see the photos?", at ~0.2 confidence; its right answers were 0.8-0.96)
REPLY_KEYWORDS = [(k, re.compile(rf"\b({p})\b", re.IGNORECASE)) for k, p in (
    ("hear", r"hear me|hear you|can you hear"),
    ("ate", r"eat|eaten|ate|lunch|dinner|breakfast"),
    ("studies", r"exams?|stud(y|ying|ies)|school|college|class"),
    ("health", r"sleep(ing)?|sick|fever|cold|health|medicine|hurt"),
    ("coming", r"come|coming|visit"),
    ("doing", r"what are you doing"),
    ("okay", r"take care|study well|call me|send me|be careful"),
    ("like", r"do you like|did you like|you like"),
)]
REPLY_MIN_CONFIDENCE = 0.5
REPLY_KIND = {"type": "choice", "instructions": "The grandmother said this to her grandchild. What is she doing?",
              "criteria": {**{k: v[0] for k, v in REPLIES.items()}, "other": "something else"}}


def worth_asking(entry):
    """Everyday words the translator already handles (kura, illu) aren't worth a question, and a word needs a way to
    say it (roman), except proverbs, which are asked about as a whole."""
    if not entry.get("note") or entry["id"].endswith("_vocative"):
        return False
    if entry.get("category") == "idiom":
        return True
    return bool(entry.get("roman")) and (entry.get("substitute") is not False or entry.get("category") in ("phrase", "culture"))


def stem(entry, picture_kind=None):
    """The question for a word-list entry, by what kind of word it is."""
    name = (entry.get("roman") or entry["forms"][0]).strip(" ,^")
    category = entry.get("category")
    if category in ("idiom", "phrase", "slang", "word"):
        return f"What does “{name if entry.get('roman') else entry['forms'][0].strip(' ,.^')}” mean?"
    if category == "family":
        return f"Who is “{name}”?"
    if category == "culture" and entry.get("topic") in ("feelings", "greetings"):
        return f"Why do people say “{name}”?"
    if category == "place" and entry.get("topic") == "travel":
        return f"Where is {name}?"
    if picture_kind == "person":
        return f"Who is {name}?"
    return f"What is {name}?"


class Curious:
    def __init__(self, decider, progress, keep_at):
        self.decider, self.progress, self.keep_at = decider, progress, keep_at
        self.asked = set()  # one question per word per call

    def for_line(self, english, hits, picture=None, intent=None, known_before=None):
        """[{id, text, word, kind, answer?}] for this line, most worth asking first. `known_before`: the words they
        knew before this line (hearing it just now counts toward learning it, but they didn't know it then)."""
        out = []
        reply = self.reply(english, intent)
        if reply:
            out.append(reply)
        pic = self.about_picture(picture, hits)
        if pic:
            out.append(pic)
        out += self.words(hits, known_before, english, MAX_PER_LINE - len(out), picture) or []
        return out[:MAX_PER_LINE]

    def candidates(self, hits, known_before=None):
        """Things she mentioned worth a question that they probably don't know yet (and weren't asked about)."""
        known = known_before if known_before is not None else {h["id"] for h in hits if self.progress.probability(h["id"]) >= self.keep_at}
        return [h for h in hits if worth_asking(h) and h["id"] not in self.asked and h["id"] not in known]

    def tier(self, h, picture=None):
        return 0 if h["id"] in (picture or {}).get("lexicon_ids", []) else 1 if h.get("category") in EXPLAIN_FIRST else 2

    def words_early(self, hits, known_before=None, limit=MAX_PER_LINE, picture=None):
        """Questions about the words she used, from her Telugu alone, so they go out before the English is back (no
        model call). Returns (questions, slots left for Laya): when more words tie for the last slots than there are
        slots, Laya picks those once the English is here (words(..., english))."""
        cands = sorted(self.candidates(hits, known_before), key=lambda h: (self.tier(h, picture), self.progress.probability(h["id"])))
        if limit <= 0 or not cands:
            return [], 0
        if len(cands) <= limit or self.decider is None or self.tier(cands[limit - 1], picture) < self.tier(cands[limit], picture):
            return self._questions(cands[:limit], picture), 0
        decided = [h for h in cands[:limit] if self.tier(h, picture) < self.tier(cands[limit - 1], picture)]
        return self._questions(decided, picture), limit - len(decided)

    def words(self, hits, known_before=None, english=None, limit=MAX_PER_LINE, picture=None):
        """Questions about the words she used, most worth asking first (Laya breaks ties, given the English)."""
        cands = self.candidates(hits, known_before)
        if limit <= 0 or not cands:
            return []
        return self._questions(self.rank(english, cands, need=limit, picture=picture)[:limit], picture)

    def _questions(self, entries, picture=None):
        pic_words = set((picture or {}).get("lexicon_ids", []))
        out = []
        for h in entries:
            self.asked.add(h["id"])
            kind = "person" if h["id"] in pic_words and (picture or {}).get("kind") == "person" else None
            out.append({"id": h["id"], "word": h["id"], "text": stem(h, kind), "kind": h.get("category"),
                        "answer": {"text": h["note"], "telugu": h["forms"][0].strip(" ,.^"), "roman": (h.get("roman") or "").strip(" ,")}})
        return out

    def about_picture(self, picture, hits):
        """"What is ___?" for a picture of something that isn't one of her words (those get their own question)."""
        if not picture or set(picture.get("lexicon_ids", [])) & {h["id"] for h in hits} or f"pic:{picture['id']}" in self.asked:
            return None
        self.asked.add(f"pic:{picture['id']}")
        return {"id": f"pic:{picture['id']}", "text": f"What is {picture['name'].split(' (')[0]}?", "word": None, "kind": "thing",
                "answer": {"text": picture.get("description", ""), "roman": picture["name"]}}

    def rank(self, english, cands, need=MAX_PER_LINE, picture=None):
        """Most worth asking first: by tier, then least known; Laya picks the best when more than `need` tie."""
        cands = sorted(cands, key=lambda h: (self.tier(h, picture), self.progress.probability(h["id"])))
        if len(cands) <= need or self.decider is None or english is None \
                or self.tier(cands[need - 1], picture) < self.tier(cands[need], picture):
            return cands
        cut = self.tier(cands[need - 1], picture)
        head, ties = [h for h in cands if self.tier(h, picture) < cut], [h for h in cands if self.tier(h, picture) == cut]
        options = {f"option{i}": f"{(h.get('roman') or h['forms'][0]).strip(' ,^')}: {h['note'][:80]}" for i, h in enumerate(ties[:4])}
        best = ties[int(self.decider.choose(english, {**RANK, "criteria": options})[len("option"):])]
        return head + [best] + [h for h in ties if h is not best]

    def reply(self, english, intent):
        """When she asks the grandkid something: how to answer her in Telugu (Laya picks which kind of question).
        `intent` may be a function, called only if the line isn't a plain question and has no reply keyword."""
        kind = next((k for k, pattern in REPLY_KEYWORDS if pattern.search(english)), None)
        if not is_question(english) and not (kind == "okay" and callable(intent)):
            if callable(intent):
                intent = intent()
            if intent not in ("question", "request"):
                return None
        if kind is None:
            if self.decider is None:
                return None
            kind, confidence = self.decider.choose(english, REPLY_KIND, confidence=True)
            if confidence < REPLY_MIN_CONFIDENCE:
                return None
        if kind not in REPLIES or f"reply:{kind}" in self.asked:
            return None
        self.asked.add(f"reply:{kind}")
        _, en, te, roman = REPLIES[kind]
        return {"id": f"reply:{kind}", "word": None, "kind": "reply", "text": f"How do I say “{en}” in Telugu?",
                "answer": {"text": f"Say it back to her: “{en}”", "telugu": te, "roman": roman}}

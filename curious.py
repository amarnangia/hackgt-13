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
        known = known_before if known_before is not None else {h["id"] for h in hits if self.progress.probability(h["id"]) >= self.keep_at}
        out = []
        reply = self.reply(english, intent)
        if reply:
            out.append(reply)
        # Things she mentioned that they probably don't know yet
        cands = [h for h in hits if worth_asking(h) and h["id"] not in self.asked and h["id"] not in known]
        pic_words = set((picture or {}).get("lexicon_ids", []))
        if picture and not pic_words & {h["id"] for h in hits} and f"pic:{picture['id']}" not in self.asked:
            out.append({"id": f"pic:{picture['id']}", "text": f"What is {picture['name'].split(' (')[0]}?", "word": None, "kind": "thing",
                        "answer": {"text": picture.get("description", ""), "roman": picture["name"]}})
        for h in self.rank(english, cands)[:MAX_PER_LINE - len(out)]:
            self.asked.add(h["id"])
            kind = "person" if h["id"] in pic_words and (picture or {}).get("kind") == "person" else None
            out.append({"id": h["id"], "word": h["id"], "text": stem(h, kind), "kind": h.get("category"),
                        "answer": {"text": h["note"], "telugu": h["forms"][0].strip(" ,.^"), "roman": (h.get("roman") or "").strip(" ,")}})
        return out[:MAX_PER_LINE]

    def rank(self, english, cands):
        """Most worth asking first: Laya picks when there's a choice; least known first otherwise."""
        cands = sorted(cands, key=lambda h: self.progress.probability(h["id"]))
        if len(cands) <= 1 or self.decider is None:
            return cands
        options = {f"option{i}": f"{(h.get('roman') or h['forms'][0]).strip(' ,^')}: {h['note'][:80]}" for i, h in enumerate(cands[:4])}
        best = cands[int(self.decider.choose(english, {**RANK, "criteria": options})[len("option"):])]
        return [best] + [h for h in cands if h is not best]

    def reply(self, english, intent):
        """When she asks the grandkid something: how to answer her in Telugu (Laya picks which kind of question)."""
        if not (intent in ("question", "request") or is_question(english)):
            return None
        kind = next((k for k, pattern in REPLY_KEYWORDS if pattern.search(english)), None)
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

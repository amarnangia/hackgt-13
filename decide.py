# Laya's per-line decisions (~0.1 s, local): should the English voice speak this line, and what kind of
# thing does it mention? Exact card details come from lexicon.json; Laya covers what the list doesn't.
import re
import threading
import time

# Phrasings tested on 18 real call lines: "question / request / statement?" as a choice got 17/18;
# the same idea as a yes/no ("does this need the listener's attention?") got 9/14.
QUESTIONS = {
    "intent": {"type": "choice", "instructions": "Is this sentence a question, a request, or a statement?", "criteria": {
        "question": "a question, even without a question mark",
        "request": "a request or instruction to the listener",
        "statement": "a statement of fact or news"}},
    "category": {"type": "choice", "instructions": "What kind of thing is mentioned?", "criteria": {
        "food": "a dish, snack, sweet or drink", "vehicle": "rickshaw, scooter, bus, train",
        "place": "temple, market, city, village", "clothing": "saree, kurta, dupatta",
        "festival": "Diwali, Holi, Sankranti, puja, wedding", "none": "nothing concrete"}},
    # What the conversation is about, for the overlay's topic words (tools/eval_laya.py measures it)
    "topic": {"type": "choice", "instructions": "What is this sentence mostly about?", "criteria": {
        "greetings": "saying hello, goodbye, asking how someone is, checking the call can be heard",
        "food": "food, cooking, eating, meals, sweets, recipes",
        "family": "relatives and family members and their news",
        "festivals": "festivals, temple, prayer, weddings, ceremonies, traditions",
        "health": "health, pain, illness, doctor, medicine, sleep",
        "school": "school, studies, exams, college, jobs, work",
        "travel": "trips, travel, trains, buses, flights, cities and famous places",
        "home": "the house, the village, farm, fields, animals, trees, chores",
        "weather": "weather, rain, heat, cold, snow, seasons",
        "feelings": "feelings, missing someone, love, worry, pride, blessings",
        "plans": "plans, visits, coming home, calling again, sending something"}},
}
CATEGORY_MIN_CONFIDENCE = 0.8
QUESTION_WORDS = {"what", "when", "where", "who", "whom", "whose", "why", "how", "which", "did", "do", "does", "are", "is",
                  "was", "were", "will", "would", "can", "could", "have", "has", "had", "shall", "should", "may", "won't",
                  "didn't", "don't", "doesn't", "aren't", "isn't", "haven't", "hasn't", "can't", "what's", "how's", "where's",
                  "who's", "when's"}


PRONOUNS = {"i", "you", "we", "they", "he", "she", "it"}
WH_WORDS = {"what", "when", "where", "who", "whom", "whose", "why", "how", "which"}
AUXILIARIES = {"is", "are", "was", "were", "am", "will", "would", "do", "does", "did", "can", "could", "should", "shall",
               "have", "has", "had", "may", "might", "time", "about", "else", "much", "many", "long", "far", "old"}


def is_question(english):
    words = re.findall(r"[a-z']+", english.lower())
    # skip a leading address or filler: "Sweetheart, are you...", "Sare dear, what did you..."
    while words and words[0] in {"sweetheart", "dear", "sare", "okay", "ok", "so", "and", "hello", "hi", "nanna", "kanna",
                                  "bangaram", "ammamma", "grandma", "well", "oh", "ayyo", "hey", "yes", "no", "tell", "me"}:
        words = words[1:]
    if english.rstrip().endswith("?"):
        return True
    if not words:
        return False
    if words[0] in WH_WORDS:  # "When is your exam" is a question, "When I was a child..." is a story
        return len(words) > 1 and words[1] in AUXILIARIES
    # "Don't be sad" is a request and "May God keep you happy" a blessing; "Don't you like it?" and "May I come?" ask
    if words[0] in ("don't", "may") and (len(words) < 2 or words[1] not in PRONOUNS):
        return False
    return words[0] in QUESTION_WORDS


# The conversation's topic, for the overlay's topic words. Laya alone got 70% on our test lines (tools/eval_laya.py):
# it called most questions "greetings" and mixed up home, weather and travel. So, like the other decisions here, the
# plain cases are rules: the topics of the word-list words she said (lexicon.json "topic"), then clear English
# keywords, and Laya decides the rest.
TOPIC_KEYWORDS = {  # checked in this order: the more specific topics first
    "health": r"pain|hurt(s|ing)?|fever|cough|medicine|tablets?|doctor|hospital|sugar|bp|sick|headache|knee|slept|sleep",
    "school": r"school|exams?|marks|stud(y|ies|ying)|college|class(es)?|teacher|job|office|work(ing)?",
    "weather": r"rain(s|ing|ed)?|monsoon|hot|heat|cold|snow(ing)?|winter|degrees|sweater|weather|sunny",
    "festivals": r"temple|puja|pooja|festival|wedding|sankranti|diwali|ugadi|bhogi|dasara|holi|rangoli|ceremony|prayers?",
    "food": r"eat(en|ing)?|ate|food|cook(ed|ing)?|rice|curry|pickle|sweets?|lunch|dinner|breakfast|recipe|spicy|tasty|hungry",
    "travel": r"trip|travel(led|ing)?|train|bus|flight|airport|plane|journey",
    "plans": r"when will you come|come (home|for|back)|visit(ing)?|next (week|month|year)|holidays|call me|send me|planning",
    "home": r"village|farm|fields?|paddy|buffalo|cows?|calf|terrace|garden|trees?|cleaning",
    "feelings": r"miss(ed)? you|worried|worry|lonely|proud|sad|happy|bless|love you",
    "family": r"uncle|aunt|cousin|grand(father|mother|pa|ma)|mother|father|mom|dad|brother|sister|son|daughter|relatives|family",
    "greetings": r"hello|namaste|bye|can you hear|how are you|doing well",
}
TOPIC_PATTERNS = [(t, re.compile(rf"\b({p})\b", re.IGNORECASE)) for t, p in TOPIC_KEYWORDS.items()]


def topic_of(english, hits, laya_topic=None):
    """(topic, how it was decided): from her words' topics, else English keywords, else Laya's guess."""
    votes = {}
    for h in hits:
        if h.get("topic"):
            votes[h["topic"]] = votes.get(h["topic"], 0) + 1
    if votes:
        return max(votes, key=votes.get), "words"
    for topic, pattern in TOPIC_PATTERNS:
        if pattern.search(english):
            return topic, "keywords"
    return laya_topic, "laya"


class Decider:
    def __init__(self, device="mps"):
        import laya

        import torch

        self.torch = torch
        self.agent = laya.load("convaiinnovations/laya", device=device)
        self.lock = threading.Lock()  # one model on one GPU; translation runs on several threads
        self("Hello, how are you?")   # warm up

    def choose(self, english, question, confidence=False, **context):
        """Ask Laya one choice question about an English line (plus any extra context); returns the criteria key,
        or (key, confidence) with confidence=True."""
        with self.lock:
            answer = self.agent.predict({"english": english, **context}, {"q": question})["answers"]["q"]
            self.torch.mps.empty_cache()
        return (answer["choice"], answer["confidence"]) if confidence else answer["choice"]

    def __call__(self, english):
        start = time.monotonic()
        with self.lock:
            answers = self.agent.predict({"english": english}, QUESTIONS)["answers"]
            self.torch.mps.empty_cache()  # don't let torch hold on to GPU memory between lines
        category = answers["category"]["choice"]
        # Questions by rule: Laya called plain story lines questions ("There was a big mango tree in front of our
        # house."). Muse sometimes drops the "?", so a leading question word counts too. Laya is still good at
        # requests ("send me a photo", "call me after your exam").
        if is_question(english):
            intent = "question"
        else:
            intent = "request" if answers["intent"]["choice"] == "request" else "statement"
        return {
            "intent": intent,
            "needs_attention": intent in ("question", "request"),
            "category": category if answers["category"]["confidence"] >= CATEGORY_MIN_CONFIDENCE else "none",
            "topic": answers["topic"]["choice"], "topic_confidence": answers["topic"]["confidence"],
            "seconds": time.monotonic() - start,
        }

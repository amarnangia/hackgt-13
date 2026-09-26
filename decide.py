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
}
CATEGORY_MIN_CONFIDENCE = 0.8
QUESTION_WORDS = {"what", "when", "where", "who", "whom", "whose", "why", "how", "which", "did", "do", "does", "are", "is",
                  "was", "were", "will", "would", "can", "could", "have", "has", "had", "shall", "should", "may", "won't",
                  "didn't", "don't", "doesn't", "aren't", "isn't", "haven't", "hasn't", "can't", "what's", "how's", "where's",
                  "who's", "when's"}


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
    return words[0] in QUESTION_WORDS


class Decider:
    def __init__(self, device="mps"):
        import laya

        import torch

        self.torch = torch
        self.agent = laya.load("convaiinnovations/laya", device=device)
        self.lock = threading.Lock()  # one model on one GPU; translation runs on several threads
        self("Hello, how are you?")   # warm up

    def choose(self, english, question, **context):
        """Ask Laya one choice question about an English line (plus any extra context); returns the criteria key."""
        with self.lock:
            answer = self.agent.predict({"english": english, **context}, {"q": question})["answers"]["q"]["choice"]
            self.torch.mps.empty_cache()
        return answer

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
            "seconds": time.monotonic() - start,
        }

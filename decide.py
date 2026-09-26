# Laya's per-line decisions (~0.1 s, local): should the English voice speak this line, and what kind of
# thing does it mention? Exact card details come from lexicon.json; Laya covers what the list doesn't.
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


class Decider:
    def __init__(self, device="mps"):
        import laya

        self.agent = laya.load("convaiinnovations/laya", device=device)
        self.lock = threading.Lock()  # one model on one GPU; translation runs on several threads
        self("Hello, how are you?")   # warm up

    def __call__(self, english):
        start = time.monotonic()
        with self.lock:
            answers = self.agent.predict({"english": english}, QUESTIONS)["answers"]
        intent = answers["intent"]["choice"]
        category = answers["category"]["choice"]
        return {
            "intent": intent,
            # "?" catches questions Laya misses; Laya catches requests and questions without a "?"
            "needs_attention": intent in ("question", "request") or english.rstrip().endswith("?"),
            "category": category if answers["category"]["confidence"] >= CATEGORY_MIN_CONFIDENCE else "none",
            "seconds": time.monotonic() - start,
        }

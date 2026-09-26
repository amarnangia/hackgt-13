# Live "ask her" prompts: when grandma shares something (a memory, news, something she made) and pauses, suggest one
# short follow-up question the grandkid can ask *in Telugu* (with pronunciation), so they take part instead of just
# listening.
#
# When: at least MIN_LINES shareable lines since the last prompt, a pause of PAUSE_S after she stops, at most one
# prompt every COOLDOWN_S (--prompt-every), and never right after she asked the grandkid something (then they should
# answer). A line is shareable if it's a statement (Laya + the question rule in decide.py sort out questions and
# requests like "take care, study well") with at least MIN_WORDS words and not just affection or a blessing.
# Asking Laya directly "is this worth a follow-up?" failed: it said no to "Today I made pulihora for you" and
# "Uncle is coming next week" (10/18), so the rule is plain.
# What: Muse Spark writes the question from her last few shareable lines (~1.5 s), unless she just mentioned something
# with a picture or card: then topics.py's question about it ("How do you make pulihora?"), ready instantly.
import os
import re
import threading
import time

PAUSE_S = 1.2      # quiet this long after Muse says she stopped (Muse already waits ~0.5 s of silence for that)
COOLDOWN_S = 25    # at most one prompt this often (--prompt-every); short enough for a live demo
MIN_LINES = 1      # one shareable line is enough
MIN_WORDS = 5
WINDOW_S = 90
TOPIC_FRESH_S = 60  # a topic she mentioned longer ago than this has passed
AFFECTION = re.compile(r"\b(love you|miss you|bless|god|take care|good night|bye)\b", re.IGNORECASE)
DEBUG = bool(os.environ.get("PROMPT_DEBUG"))  # PROMPT_DEBUG=1 prints why a prompt did or didn't fire


def shareable(english, intent):
    return intent == "statement" and len(english.split()) >= MIN_WORDS and not AFFECTION.search(english)


class StoryPrompter:
    def __init__(self, decider, caller, on_prompt, cooldown_s=COOLDOWN_S):
        self.decider, self.caller, self.on_prompt = decider, caller, on_prompt
        self.cooldown_s = cooldown_s
        self.lines = []            # shareable (time, telugu, english) since the last prompt
        self.last_intent = None    # of her most recent line, shareable or not
        self.speaking = False
        self.last_speech_end = time.monotonic()
        self.last_prompt = -1e9
        self.topic = None          # (time, question) from topics.py, waiting for her next pause
        self.topics_asked = set()  # never the same topic twice in a call
        self.lock = threading.Lock()
        threading.Thread(target=self._watch, daemon=True).start()

    def on_event(self, ev):
        kind = ev.get("type")
        if kind == "speechStart" or (kind == "transcript" and ev.get("transcript")):
            self.speaking = True
        elif kind == "speechEnd":
            self.speaking = False
            self.last_speech_end = time.monotonic()

    def on_line(self, telugu, english, intent, route):
        if english.startswith("("):
            return
        with self.lock:
            self.last_intent = intent
            if shareable(english, intent):
                self.lines.append((time.monotonic(), telugu, english))

    def offer(self, question):
        """Something she mentioned (topics.py): ask about it at the next pause instead of a Muse Spark question."""
        if question and question["key"] not in self.topics_asked:
            with self.lock:
                self.topic = (time.monotonic(), question)

    def _watch(self):
        last_reason = None
        while True:
            time.sleep(0.25)
            now = time.monotonic()
            with self.lock:
                recent = [l for l in self.lines if now - l[0] < WINDOW_S]
                topic = self.topic[1] if self.topic and now - self.topic[0] < TOPIC_FRESH_S else None
            reason = ("she's talking" if self.speaking else
                      "waiting for a pause" if now - self.last_speech_end < PAUSE_S else
                      "cooldown" if now - self.last_prompt < self.cooldown_s else
                      "nothing shareable yet" if len(recent) < MIN_LINES and not topic else
                      "she just asked something" if self.last_intent in ("question", "request") else None)
            if DEBUG and reason != last_reason:
                print(f"  (prompt check: {reason or 'writing a question'})", flush=True)
            last_reason = reason
            if reason:
                continue
            self.last_prompt = now
            with self.lock:
                self.lines, self.topic = [], None
            if topic:
                self.topics_asked.add(topic["key"])
                self.on_prompt(topic)
            else:
                threading.Thread(target=self._suggest, args=(recent[-5:],), daemon=True).start()

    def _suggest(self, recent):
        from muse import spark_json

        said = "\n".join(f"{telugu}  =  {english}" for _, telugu, english in recent)
        q = spark_json(
            f"You help a grandchild raised in the US (beginner Telugu) keep a conversation going with their Telugu-speaking "
            f"grandparent ({self.caller}). The grandparent just said the lines below and paused. Suggest ONE short, warm, "
            "curious follow-up question about what they said, that the grandchild can ask in simple spoken Telugu (at most 8 "
            'words). Keys: "telugu" (Telugu script), "roman" (pronunciation in English letters), "english" (meaning).',
            said, model="muse-spark-1.1", effort="minimal", timeout=8)
        if q and q.get("telugu") and q.get("roman"):
            self.on_prompt({"telugu": q["telugu"], "roman": q["roman"], "english": q.get("english", "")})

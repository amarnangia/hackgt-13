# Live "ask her" prompts: a short question the grandkid can ask *in Telugu* (with pronunciation) to keep the
# conversation going, so they take part instead of just listening. Any natural gap counts, whatever language was
# spoken and whoever spoke (--two-way also hears the grandkid):
#   - follow-up: someone shared something (a memory, news, something they made) and paused -> a question about it;
#   - lull: nobody has said anything for LULL_S -> something to keep it going, from what the call has been about,
#     or a warm conversation starter if nothing has been said yet;
#   - topic: something with a picture or card was just mentioned -> topics.py's question about it, ready instantly.
# Never while someone is talking, at most one prompt every COOLDOWN_S (--prompt-every), never the same one twice,
# and not right after someone asked a question (give them a moment to answer; a lull after that is fine).
# A line is shareable if it's a statement (Laya + the question rule in decide.py sort out questions and requests like
# "take care, study well") with at least MIN_WORDS words and not just affection or a blessing. Asking Laya directly
# "is this worth a follow-up?" failed: it said no to "Today I made pulihora for you" and "Uncle is coming next week"
# (10/18), so the rule is plain. Muse Spark writes the follow-up and lull questions (~1.5-2.5 s) from the last few
# lines, about the newest specific thing; a hand-written starter only when nothing has been said yet.
import os
import re
import threading
import time
from collections import deque

PAUSE_S = 1.2      # quiet this long after Muse says she stopped (Muse already waits ~0.5 s of silence for that)
LULL_S = 5.0       # nobody has said anything this long: offer something to keep it going
COOLDOWN_S = 25    # at most one prompt this often (--prompt-every); short enough for a live demo
MIN_LINES = 1      # one shareable line is enough
MIN_WORDS = 5
WINDOW_S = 90
TOPIC_FRESH_S = 60  # a topic she mentioned longer ago than this has passed
CONTEXT_S = 240     # what the call has been about, for lull questions
# When Muse Spark can't write one: warm starters, in the respectful form (meeru) a grandkid uses with an elder
STARTERS = [
    {"telugu": "ఈ రోజు ఏం వండారు?", "roman": "Ee roju em vandaaru?", "english": "What did you cook today?"},
    {"telugu": "మీ ఆరోగ్యం ఎలా ఉంది?", "roman": "Mee aarogyam ela undi?", "english": "How is your health?"},
    {"telugu": "మీ చిన్నప్పటి కథ ఒకటి చెప్పండి", "roman": "Mee chinnappati katha okati cheppandi", "english": "Tell me a story from when you were little"},
    {"telugu": "ఊర్లో ఏం విశేషాలు?", "roman": "Oorlo em visheshalu?", "english": "What's new back home?"},
    {"telugu": "తాతయ్య ఎలా ఉన్నారు?", "roman": "Thatayya ela unnaru?", "english": "How is Thatayya?"},
    {"telugu": "మీకు ఇష్టమైన వంట ఏది?", "roman": "Meeku ishtamaina vanta edi?", "english": "What's your favourite dish to cook?"},
    {"telugu": "ఈ మధ్య ఏం సినిమా చూశారు?", "roman": "Ee madhya em cinema choosaru?", "english": "Seen any movie lately?"},
    {"telugu": "నేను వచ్చినప్పుడు ఏం చేద్దాం?", "roman": "Nenu vachinappudu em cheddam?", "english": "What should we do when I visit?"},
]
AFFECTION = re.compile(r"\b(love you|miss you|bless|god|take care|good night|bye)\b", re.IGNORECASE)
DEBUG = bool(os.environ.get("PROMPT_DEBUG"))  # PROMPT_DEBUG=1 prints why a prompt did or didn't fire


def shareable(english, intent):
    return intent == "statement" and len(english.split()) >= MIN_WORDS and not AFFECTION.search(english)


class StoryPrompter:
    def __init__(self, decider, caller, on_prompt, cooldown_s=COOLDOWN_S):
        self.decider, self.caller, self.on_prompt = decider, caller, on_prompt
        self.cooldown_s = cooldown_s
        self.lines = []            # shareable (time, who, telugu, english) since the last prompt
        self.history = deque(maxlen=12)  # every line (time, who, english), for what the call has been about
        self.last_intent = None    # of the most recent line, shareable or not
        self.speaking = {}         # who -> talking right now ("them", and "me" with --two-way)
        self.last_speech_end = time.monotonic()
        self.last_prompt = -1e9
        self.spoke_since_prompt = True  # a lull gets one prompt; another only after someone has spoken again
        self.topic = None          # (time, question) from topics.py, waiting for the next pause
        self.topics_asked = set()  # never the same topic twice in a call
        self.asked = set()         # prompts already shown (their pronunciation), never twice
        self.lock = threading.Lock()
        threading.Thread(target=self._watch, daemon=True).start()

    def shown(self, prompt):
        """A prompt was shown some other way (the next-call starter): count it for the cooldown and repeats."""
        self.last_prompt, self.spoke_since_prompt = time.monotonic(), False
        self.asked.add(prompt.get("roman", "").lower())

    def on_event(self, ev, who="them"):
        kind = ev.get("type")
        if kind == "speechStart" or (kind == "transcript" and ev.get("transcript")):
            self.speaking[who] = True
        elif kind == "speechEnd":
            self.speaking[who] = False
            self.last_speech_end = time.monotonic()
            self.spoke_since_prompt = True

    def on_line(self, telugu, english, intent, route, who="them"):
        if english.startswith("("):
            return
        with self.lock:
            self.last_intent = intent
            self.history.append((time.monotonic(), who, english))
            if shareable(english, intent):
                self.lines.append((time.monotonic(), who, telugu, english))

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
                context = [(who, english) for t, who, english in self.history if now - t < CONTEXT_S]
            quiet = now - self.last_speech_end
            lull = quiet >= LULL_S and self.spoke_since_prompt
            kind = "topic" if topic else "follow-up" if len(recent) >= MIN_LINES else "lull" if lull else None
            reason = ("someone's talking" if any(self.speaking.values()) else
                      "waiting for a pause" if quiet < PAUSE_S else
                      "cooldown" if now - self.last_prompt < self.cooldown_s else
                      "a question is waiting for an answer" if self.last_intent in ("question", "request") and quiet < LULL_S
                      else "nothing to follow up yet" if not kind else None)
            if DEBUG and reason != last_reason:
                print(f"  (prompt check: {reason or 'writing a ' + kind + ' question'})", flush=True)
            last_reason = reason
            if reason:
                continue
            self.last_prompt, self.spoke_since_prompt = now, False
            with self.lock:
                self.lines, self.topic = [], None
            if kind == "topic":
                self.topics_asked.add(topic["key"])
                self._show(topic)
            else:
                threading.Thread(target=self._suggest, args=(kind, recent[-5:], context), daemon=True).start()

    def _show(self, prompt):
        self.asked.add(prompt["roman"].lower())
        self.on_prompt(prompt)

    def _suggest(self, kind, recent, context):
        from muse import spark_json

        name = lambda who: "Grandchild" if who == "me" else self.caller
        # Both kinds read what was actually said, newest last: the question should be about the specific thing just
        # mentioned ("I want to go to the mall" -> "What will you buy at the mall?"), not a generic "did you eat?".
        # The first version said "else a new topic" for lulls and Muse took that every time; low effort instead of
        # minimal, and examples on other topics than the ones it was tested on.
        said = "\n".join(f"{name(who)}: {english}" for who, english in context[-6:])
        if not said:
            fresh = [s for s in STARTERS if s["roman"].lower() not in self.asked]
            if fresh:
                self._show({**fresh[0], "kind": kind})
            return
        avoid = ", ".join(sorted(self.asked)) or "none"
        q = spark_json(
            "You help a grandchild raised in the US (beginner Telugu) keep a phone call going with their Telugu-speaking "
            f"grandparent ({self.caller}). There is a pause now. Suggest ONE short question the grandchild can ask next, in "
            "simple spoken Telugu (at most 8 words), respectful form (meeru).\n"
            "Most important: ask about the SPECIFIC thing in the LAST line (the newest line is at the bottom). React to what "
            "was actually said, the way a curious grandchild would.\n"
            f'Good: "{self.caller}: Thatayya planted tomatoes in the backyard" -> "Tomatolu eppudu kostaru?" (When will you '
            f'pick the tomatoes?). "{self.caller}: My knee has been hurting" -> "Doctor daggariki vellara?" (Did you go to '
            'the doctor?). "Grandchild: I got a new job" -> "Meeru santoshistara?" (Are you happy for me?).\n'
            'Bad (generic, ignores what was said): "Did you eat?", "What did you do today?", "How are you?".\n'
            f"Don't repeat these: {avoid}. "
            'Keys: "telugu" (Telugu script), "roman" (pronunciation in English letters), "english" (meaning).',
            f"The call so far (newest last):\n{said}", model="muse-spark-1.1", effort="low", timeout=8)
        if q and q.get("telugu") and q.get("roman") and q["roman"].lower() not in self.asked:
            self._show({"telugu": q["telugu"], "roman": q["roman"], "english": q.get("english", ""), "kind": kind})
        # No fallback here: a generic question during a conversation is worse than none.

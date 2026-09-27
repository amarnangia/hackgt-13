# The overlay's word list follows the conversation, whatever it's about. vocab.json only has 11 fixed topics and the
# rules that picked one needed 2 votes in 3 lines, so a real conversation (exams, then a sister visiting, then a flood)
# never moved it, and there was nothing to show for shopping or movies at all. Here Muse Spark reads the last few lines
# (either side, any language) and either says the subject hasn't changed (filler, small talk, talk about the call) or
# names the new one with 5 Telugu words and phrases for it. It runs in the background after new lines, at most every
# MIN_GAP_S, so the call never waits; her own word-list words (pulihora -> food) still switch the list instantly.
import threading
import time
from collections import deque

MIN_GAP_S = 10   # at most one check this often
LINES = 6        # how much of the conversation it reads
MIN_WORDS = 3    # a line shorter than this ("okay", "wait") doesn't trigger a check


class LiveVocab:
    def __init__(self, caller, on_topic, current=None):
        """on_topic(subject, words) shows a new list; `current` is the subject shown now (for "has it changed?")."""
        self.caller, self.on_topic = caller, on_topic
        self.current = current
        self.lines = deque(maxlen=LINES)  # (who, english)
        self.new = False
        self.last_check = 0.0
        self.lock = threading.Lock()
        threading.Thread(target=self._watch, daemon=True).start()

    def shown(self, subject):
        """The list was switched some other way (her word-list words): that's the subject now."""
        self.current = subject

    def on_line(self, english, who="them"):
        if not english or english.startswith("("):
            return
        with self.lock:
            self.lines.append((who, english))
            if len(english.split()) >= MIN_WORDS:
                self.new = True

    def _watch(self):
        while True:
            time.sleep(1)
            if not self.new or time.monotonic() - self.last_check < MIN_GAP_S:
                continue
            with self.lock:
                lines, self.new = list(self.lines), False
            self.last_check = time.monotonic()
            try:
                self._check(lines)
            except Exception as e:  # the list is a helper; never let it stop the call
                print(f"(live words failed: {type(e).__name__}: {e})", flush=True)

    def _check(self, lines):
        from muse import spark_json

        said = "\n".join(f"{'Grandchild' if who == 'me' else self.caller}: {english}" for who, english in lines)
        r = spark_json(
            "You keep a short list of useful Telugu words on screen for a grandchild (raised in the US, beginner Telugu) "
            f"during a live phone call with their Telugu-speaking grandparent ({self.caller}). The list is currently about: "
            f"{self.current or 'nothing yet'}.\n"
            "Read the call (newest line last). Reply {\"same\": true} if the newest lines are still about that subject, "
            "including more detail on it or a new angle of it (the mall -> what they bought there is the SAME subject), or if "
            "they are just filler, small talk, or talk about the call or the app itself (can you hear me, the screen). Only "
            "when the newest lines are clearly about a different thing, reply "
            '{"same": false, "subject": "<2-4 '
            'words, sentence case>", "words": [5 items]}: words and short phrases the grandchild could actually use to '
            "talk about THIS subject with the grandparent, specific to it (shopping at the mall -> to buy, price, clothes, "
            '"how much is it?"), in everyday spoken Telugu, respectful forms for phrases. Each item: {"telugu": Telugu '
            'script, "roman": pronunciation in English letters, "english": meaning}.',
            f"The call (newest last):\n{said}", model="muse-spark-1.1", effort="low", timeout=12)
        if not r or r.get("same") is not False:
            return
        words = [w for w in r.get("words") or [] if w.get("telugu") and w.get("roman") and w.get("english")][:5]
        subject = (r.get("subject") or "").strip()
        if subject and len(words) >= 3 and subject.lower() != (self.current or "").lower():
            self.current = subject
            self.on_topic(subject, words)

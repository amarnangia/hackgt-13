# Live "ask her" prompts: when grandma has been telling a story and pauses, suggest one short follow-up question
# the grandkid can ask *in Telugu* (with pronunciation), so they take part instead of just listening.
#
# When: after >= 2 story/news lines, during a pause of >= PAUSE_S, at most once every COOLDOWN_S, and never right
# after she asked the grandkid something (then they should answer, not ask). Laya judges story vs news vs
# questions vs small talk (all 4 stories in testing; a prompt/no-prompt call on 10/10 windows).
# What: Muse Spark writes the question from her last few lines (~1.5 s).
import threading
import time

PAUSE_S = 2.5
COOLDOWN_S = 120
MIN_LINES = 2
WINDOW_S = 90  # only lines from the last minute and a half count

WHAT_IS_SHE_DOING = {"type": "choice", "instructions": "What is the grandmother doing in these lines?", "criteria": {
    "story": "telling a story or memory from her past",
    "news": "sharing recent everyday news or updates",
    "asking": "asking the grandchild questions",
    "small_talk": "greetings, blessings or small talk"}}


class StoryPrompter:
    def __init__(self, decider, caller, on_prompt):
        self.decider, self.caller, self.on_prompt = decider, caller, on_prompt
        self.lines = []            # (time, telugu, english, intent) since the last prompt
        self.speaking = False
        self.last_speech_end = time.monotonic()
        self.last_prompt = -1e9
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
            self.lines.append((time.monotonic(), telugu, english, intent))

    def _watch(self):
        while True:
            time.sleep(0.5)
            now = time.monotonic()
            if self.speaking or now - self.last_speech_end < PAUSE_S or now - self.last_prompt < COOLDOWN_S:
                continue
            with self.lock:
                recent = [l for l in self.lines if now - l[0] < WINDOW_S]
            if len(recent) < MIN_LINES or recent[-1][3] in ("question", "request"):
                continue  # not enough to go on, or she just asked the grandkid something
            english = " ".join(l[2] for l in recent[-5:])
            if self.decider.choose(english, WHAT_IS_SHE_DOING) not in ("story", "news"):
                with self.lock:
                    self.lines = [l for l in self.lines if l[0] > recent[-1][0]]  # don't re-check the same lines
                continue
            self.last_prompt = now
            with self.lock:
                self.lines = []
            threading.Thread(target=self._suggest, args=(recent[-5:],), daemon=True).start()

    def _suggest(self, recent):
        from muse import spark_json

        said = "\n".join(f"{telugu}  =  {english}" for _, telugu, english, _ in recent)
        q = spark_json(
            f"You help a grandchild raised in the US (beginner Telugu) keep a conversation going with their Telugu-speaking "
            f"grandparent ({self.caller}). The grandparent just said the lines below and paused. Suggest ONE short, warm, "
            "curious follow-up question about what they said, that the grandchild can ask in simple spoken Telugu (at most 8 "
            'words). Keys: "telugu" (Telugu script), "roman" (pronunciation in English letters), "english" (meaning).',
            said, model="muse-spark-1.1", effort="minimal", timeout=8)
        if q and q.get("telugu") and q.get("roman"):
            self.on_prompt({"telugu": q["telugu"], "roman": q["roman"], "english": q.get("english", "")})

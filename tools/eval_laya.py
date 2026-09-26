# How well Laya makes its per-line decisions, and how fast (build-plan steps 3 and 5): the numbers for the judges.
#   python tools/eval_laya.py            # topic + intent accuracy and time per line
#   python tools/eval_laya.py --wrong    # also print every line it got wrong
# The lines are English the way the translator gives her Telugu. We wrote and labelled them (6 per topic, plus
# questions and requests); a few are from our real calls. They're not a random sample of calls, so read the numbers
# as "does this work", not a benchmark.
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (line, topic, intent)
LINES = [
    # greetings and checking in
    ("Hello dear, are you doing well?", "greetings", "question"),
    ("Can you hear me now?", "greetings", "question"),
    ("I'm fine, everyone here is fine.", "greetings", "statement"),
    ("Okay, bye, take care.", "greetings", "request"),
    ("It's so good to hear your voice.", "greetings", "statement"),
    ("Namaste, how are you?", "greetings", "question"),
    # food and cooking
    ("Today I made tamarind rice for lunch.", "food", "statement"),
    ("Have you eaten?", "food", "question"),
    ("Add a little tamarind and fry the mustard seeds first.", "food", "request"),
    ("The mango pickle came out very spicy this year.", "food", "statement"),
    ("For Sankranti I made shell-shaped sweets and rice sweets.", "food", "statement"),
    ("Don't eat outside food, drink buttermilk.", "food", "request"),
    # family
    ("Your uncle came to visit with his children yesterday.", "family", "statement"),
    ("Your grandfather loved NTR movies.", "family", "statement"),
    ("How is your mother doing?", "family", "question"),
    ("Your cousin sister got engaged last week.", "family", "statement"),
    ("My mother used to tell me stories every night.", "family", "statement"),
    ("Your aunt's son has become very tall.", "family", "statement"),
    # festivals, temple, ceremonies
    ("We went to the temple this morning for the puja.", "festivals", "statement"),
    ("When we were little we lit Bhogi bonfires.", "festivals", "statement"),
    ("The decorated bulls came to the house for Sankranti.", "festivals", "statement"),
    ("Your cousin's wedding is in December, you must come.", "festivals", "request"),
    ("We drew a big rangoli in front of the house for Diwali.", "festivals", "statement"),
    ("On Ugadi we read the almanac for the new year.", "festivals", "statement"),
    # health
    ("My knee has been hurting for a few days.", "health", "statement"),
    ("I had a fever, but I'm better now.", "health", "statement"),
    ("Did you take your medicine?", "health", "question"),
    ("The doctor said my sugar is a little high.", "health", "statement"),
    ("I couldn't sleep well last night.", "health", "statement"),
    ("Drink warm water, your cold will go away.", "health", "request"),
    # school and work
    ("How are your exams going?", "school", "question"),
    ("Study well and get good marks.", "school", "request"),
    ("Your father is very busy with work these days.", "school", "statement"),
    ("When does your college start again?", "school", "question"),
    ("Your cousin got a job in Bangalore.", "school", "statement"),
    ("I used to walk three kilometres to school.", "school", "statement"),
    # travel and places
    ("We went to Tirupati last month.", "travel", "statement"),
    ("The train to Hyderabad was very crowded.", "travel", "statement"),
    ("Have you ever seen the Godavari river?", "travel", "question"),
    ("Your uncle took us to Araku valley.", "travel", "statement"),
    ("The flight from America takes so many hours.", "travel", "statement"),
    ("We took the bus to Vijayawada.", "travel", "statement"),
    # home and village
    ("There was a big mango tree in front of our house.", "home", "statement"),
    ("The buffalo gave a calf this week.", "home", "statement"),
    ("We used to sleep on the terrace in summer.", "home", "statement"),
    ("The paddy fields are all green now.", "home", "statement"),
    ("I am cleaning the house today.", "home", "statement"),
    ("In our village everyone knew each other.", "home", "statement"),
    # weather
    ("It has been raining here all week.", "weather", "statement"),
    ("It is very hot here, over forty degrees.", "weather", "statement"),
    ("Is it snowing there?", "weather", "question"),
    ("The monsoon came late this year.", "weather", "statement"),
    ("It's getting cold at night now.", "weather", "statement"),
    ("Wear a sweater, it's cold there.", "weather", "request"),
    # feelings and blessings
    ("I miss you so much.", "feelings", "statement"),
    ("I was so worried when you didn't call.", "feelings", "statement"),
    ("May God keep you happy always.", "feelings", "statement"),
    ("I felt very lonely after your grandfather passed.", "feelings", "statement"),
    ("I'm so proud of you.", "feelings", "statement"),
    ("Don't be sad, everything will be fine.", "feelings", "request"),
    # plans and visits
    ("When will you come home?", "plans", "question"),
    ("Come for the summer holidays.", "plans", "request"),
    ("We are planning to visit you next year.", "plans", "statement"),
    ("Call me again on Sunday.", "plans", "request"),
    ("Your parents said you might come in December.", "plans", "statement"),
    ("Send me a photo of your new house.", "plans", "request"),
]


# Held out: the team's sample call (samples/call_script.json), Telugu plus the English our translator gives, labelled
# after the rules were written. Tests the whole topic decision, including her words' topics from lexicon.json.
HELD_OUT = [
    ("నాన్నా, బాగున్నావా? ఇక్కడ అందరం బాగున్నాం.", "Nanna, are you well? Everyone here is fine.", "greetings"),
    ("ఈ రోజు ఉదయం నేను గుడికి వెళ్ళి వచ్చాను, చాలా మంది ఉన్నారు.", "This morning I went to the temple; there were a lot of people.", "festivals"),
    ("ఇక్కడ చాలా వేడిగా ఉంది, వానలు ఇంకా రాలేదు.", "It's very hot here; the rains haven't come yet.", "weather"),
    ("ఈ రోజు నీ కోసం పులిహోర చేశాను.", "I made pulihora for you today.", "food"),
    ("అమ్మమ్మ ఆవకాయ పచ్చడి పెట్టింది.", "Grandma made mango pickle.", "food"),
    ("సంక్రాంతికి ఇంటికి వస్తావా?", "Will you come home for Sankranti?", "plans"),
    ("నీ exam ఎప్పుడు?", "When is your exam?", "school"),
    ("నాకు WhatsApp లో photo పంపించు.", "Send me a photo on WhatsApp.", "plans"),
    ("అన్నం తిన్నావా?", "Have you eaten?", "food"),
    ("ఎప్పుడు వస్తావు నాన్నా?", "When will you come, Nanna?", "plans"),
]

# Her questions to the grandkid, by what she's asking (curious.py offers the matching reply in Telugu); "other" = no reply
REPLY_LINES = [
    ("Have you eaten?", "ate"), ("Did you eat dinner, dear?", "ate"), ("Have you had lunch yet?", "ate"),
    ("Are you doing well?", "wellbeing"), ("How are you, Nanna?", "wellbeing"), ("Is everything okay there?", "wellbeing"),
    ("How are your exams going?", "studies"), ("Are you studying well?", "studies"), ("When is your exam?", "studies"),
    ("When will you come home?", "coming"), ("Will you come for Sankranti?", "coming"), ("Are you coming this summer?", "coming"),
    ("What are you doing?", "doing"), ("What are you doing now?", "doing"),
    ("Did you catch a cold?", "health"), ("Are you sleeping well?", "health"), ("Is your fever gone?", "health"),
    ("Can you hear me?", "hear"), ("Can you hear me now?", "hear"),
    ("Do you like pulihora?", "like"), ("Did you like the sweets I sent?", "like"),
    ("Take care.", "okay"), ("Study well.", "okay"), ("Call me on Sunday.", "okay"),
    ("Did you see the photos?", "other"), ("What is the weather there?", "other"), ("Your uncle bought a new car, did you know?", "other"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wrong", action="store_true", help="print the lines it got wrong")
    a = ap.parse_args()
    from decide import Decider, topic_of
    from lexicon import Lexicon
    print("Loading Laya...", flush=True)
    decider, lexicon = Decider(), Lexicon()
    times, laya_ok, topic_ok, intent_ok, how, wrong = [], 0, 0, 0, {}, []
    for line, topic, intent in LINES:
        start = time.monotonic()
        d = decider(line)
        times.append(time.monotonic() - start)
        got, why = topic_of(line, [], d["topic"])
        how[why] = how.get(why, 0) + 1
        laya_ok += d["topic"] == topic
        topic_ok += got == topic
        intent_ok += d["intent"] == intent
        if got != topic or d["intent"] != intent:
            wrong.append((line, topic, f"{got} ({why})", intent, d["intent"]))
    held_ok, held_wrong = 0, []
    for telugu, english, topic in HELD_OUT:
        got, why = topic_of(english, lexicon.find(telugu, "te"), decider(english)["topic"])
        held_ok += got == topic
        if got != topic:
            held_wrong.append((english, topic, f"{got} ({why})", "", ""))
    from curious import REPLY_KIND, Curious
    curious = Curious(decider, None, 1.0)
    laya_reply_ok = reply_ok = 0
    for line, want in REPLY_LINES:
        laya_reply_ok += decider.choose(line, REPLY_KIND) == want
        curious.asked.clear()
        got = curious.reply(line, "question")
        got = got["id"].split(":")[1] if got else "other"
        reply_ok += got == want
        if got != want:
            wrong.append((line, want, got, "", ""))
    n, h, r = len(LINES), len(HELD_OUT), len(REPLY_LINES)
    times.sort()
    print(f"\n{n} lines, one Laya pass each (intent, category and topic together), on this Mac")
    print(f"  topic, Laya alone       {laya_ok}/{n} = {laya_ok / n:.0%}   (11 topics; chance is ~9%)")
    print(f"  topic, keywords + Laya  {topic_ok}/{n} = {topic_ok / n:.0%}   (decided by {how}; keywords written with these lines in view)")
    print(f"  topic, held-out call    {held_ok}/{h} = {held_ok / h:.0%}   (her words' topics + keywords + Laya, on lines not used to write the rules)")
    print(f"  reply kind, Laya alone  {laya_reply_ok}/{r} = {laya_reply_ok / r:.0%}   (what she's asking, to offer the reply in Telugu)")
    print(f"  reply kind, keywords + Laya >= {0.5}  {reply_ok}/{r} = {reply_ok / r:.0%}   (no reply offered when unsure)")
    print(f"  intent                  {intent_ok}/{n} = {intent_ok / n:.0%}   (question / request / statement, with decide.is_question)")
    print(f"  time                    median {times[n // 2] * 1000:.0f} ms, slowest {times[-1] * 1000:.0f} ms per line")
    if a.wrong:
        for line, topic, got_topic, intent, got_intent in wrong + held_wrong:
            print(f"  {line!r}: topic {topic} -> {got_topic}" + (f", intent {intent} -> {got_intent}" if intent != got_intent else ""))


if __name__ == "__main__":
    main()

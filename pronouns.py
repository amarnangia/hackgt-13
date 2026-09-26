# Telugu తను ("he or she") has no gender, and the translator always turns it into "he", even when the verb
# says otherwise (తను ఆఫీసుకి వెళ్ళింది -> "He went to the office"). It does get ఆమె (she) and అతను (he) right,
# so before translating we work out who తను is and swap in the gendered pronoun:
#   1. తను as the subject: the verb in its clause agrees with it (వెళ్ళింది = she, వెళ్ళాడు = he).
#   2. Otherwise the nearest person mentioned earlier in the sentence (అమ్మ వంట చేస్తోంది, తనకి సహాయం చేయి).
#   3. Otherwise the last person mentioned in the conversation (నా స్నేహితురాలికి ఉద్యోగం వచ్చింది. తను ...).
# If none of those say, తను is left alone. Pure Python so both virtualenvs can import it.
import re

from lexicon import INDIC_LETTERS

WORD = re.compile(rf"[{INDIC_LETTERS}]+|[A-Za-z']+")
CLAUSE = re.compile(r"[,;.?!।]")

# తను's forms -> (she, he). The possessive తన needs ఆమె యొక్క: plain ఆమె అమ్మ came out as "She got her mom".
TANU = {
    "తను": ("ఆమె", "అతను"), "తాను": ("ఆమె", "అతను"), "తనే": ("ఆమె", "అతనే"), "తానే": ("ఆమె", "అతనే"),
    "తన": ("ఆమె యొక్క", "అతని"), "తనకి": ("ఆమెకి", "అతనికి"), "తనకు": ("ఆమెకు", "అతనికి"),
    "తనకే": ("ఆమెకే", "అతనికే"), "తనని": ("ఆమెని", "అతన్ని"), "తనను": ("ఆమెను", "అతన్ని"),
    "తన్ని": ("ఆమెని", "అతన్ని"), "తనతో": ("ఆమెతో", "అతనితో"), "తనది": ("ఆమెది", "అతనిది"),
    "తనలో": ("ఆమెలో", "అతనిలో"),
}
SUBJECT_FORMS = {"తను", "తాను", "తనే", "తానే"}

# People words, as the stem a case ending attaches to. Bare అన్న is left out: it is also "said".
FEMALE = ["ఆమె", "ఆవిడ", "అమ్మ", "అమ్మమ్మ", "నానమ్మ", "అక్క", "చెల్లి", "చెల్లెలు", "చెల్లెలి", "అత్త", "అత్తయ్య",
          "పిన్ని", "పెద్దమ్మ", "ఆంటీ", "అమ్మాయి", "భార్య", "కూతురు", "కూతురి", "స్నేహితురాలు", "స్నేహితురాలి",
          "మనవరాలు", "మనవరాలి", "కోడలు", "కోడలి", "వదిన", "మరదలు", "మరదలి", "మమ్మీ"]
MALE = ["అతను", "అతడు", "అతని", "అతన్ని", "ఆయన", "వాడు", "వాడి", "నాన్న", "తాత", "తాతయ్య", "అన్నయ్య", "తమ్ముడు",
        "తమ్ముడి", "మామయ్య", "బాబాయ్", "బాబాయి", "పెదనాన్న", "అంకుల్", "అబ్బాయి", "భర్త", "కొడుకు", "కొడుకి",
        "స్నేహితుడు", "స్నేహితుడి", "మనవడు", "మనవడి", "అల్లుడు", "అల్లుడి", "బావ", "మరిది", "డాడీ"]
SUFFIXES = ["", "కి", "కు", "ని", "ను", "తో", "ది", "లో", "కే", "ే", "గారు", "గారి", "గారికి", "గారితో", "గారిని"]
ENGLISH = {"f": "she her hers herself mom mother mummy mommy sister girlfriend wife daughter aunt grandma girl",
           "m": "he him his himself dad father daddy brother boyfriend husband son uncle grandpa boy"}
CUES = {w + s: "f" for w in FEMALE for s in SUFFIXES} | {w + s: "m" for w in MALE for s in SUFFIXES}
CUES |= {w: g for g, words in ENGLISH.items() for w in words.split()}
POSSESSIVE = {"నా", "మా", "నీ", "మీ", "మన", "వాళ్ళ", "my", "your", "our", "their"}
GREETINGS = {"hello", "hi", "hey", "హలో", "హాయ్"}

# Third-person verb endings: వెళ్ళాడు / వచ్చాడా = he; వెళ్ళింది / ఉందా = she (or "it", so only used for తను).
MALE_VERB = re.compile(r"ాడ[ుాట]$")
FEMALE_VERB = re.compile(r"ంద[ిాటే]$")


class PronounResolver:
    def __init__(self, lang):
        self.lang = lang
        self.last = None  # "f" or "m": the last person mentioned in the conversation

    def __call__(self, text):
        """`text` with తను made she or he; call once per sentence, in the order they were said."""
        if self.lang != "te":
            return text
        words = list(WORD.finditer(text))
        out, pos, last_in_text = [], 0, None
        for i, m in enumerate(words):
            w = m.group()
            gender = self._person(words, i, text)
            if w in TANU:
                gender = self._tanu(words, i, text, last_in_text)
                if gender:
                    out += [text[pos:m.start()], TANU[w][gender == "m"]]
                    pos = m.end()
            elif MALE_VERB.search(w):
                gender = "m"
            if gender:
                last_in_text = gender
        if last_in_text:
            self.last = last_in_text
        return "".join(out) + text[pos:]

    def _person(self, words, i, text):
        w = words[i].group()
        gender = CUES.get(w) or CUES.get(w.lower())
        if not gender or w.lower() in ("she", "her", "he", "him", "his", "hers", "herself", "himself"):
            return gender
        # Grandma calling the listener (అమ్మా / "నాన్న, ...") is "you", not a third person.
        if w.endswith("ా") and w[:-1] in CUES:
            return None
        before = words[i - 1].group().lower() if i else None
        after = text[words[i].end():].lstrip()[:1]
        if before in GREETINGS or before not in POSSESSIVE and (i == len(words) - 1 or after == ","):
            return None
        return gender

    def _tanu(self, words, i, text, earlier):
        w = words[i].group()
        if w in SUBJECT_FORMS:
            # The verb agrees with its subject: look from తను to the end of its clause.
            end = CLAUSE.search(text, words[i].end())
            end = end.start() if end else len(text)
            verbs = {"m" if MALE_VERB.search(v.group()) else "f" for v in words[i + 1:]
                     if v.start() < end and (MALE_VERB.search(v.group()) or FEMALE_VERB.search(v.group()))}
            if len(verbs) == 1:
                return verbs.pop()
        return earlier or self.last

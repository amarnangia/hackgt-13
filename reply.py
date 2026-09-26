# Did the grandkid understand the Telugu word just kept in grandma's line? Judged from what they say back:
#   understood       the reply only makes sense if they know the word ("save me some mangoes" after "mamidi")
#   not_understood   they ask, sound lost, or answer as if it meant something else ("the coconut tree?")
#   no_signal        nothing either way ("okay", "wow", "hold on, mom's calling")
# That's evidence for progress.py (which words to keep in Telugu). Two parts:
#   - rules for the clear cases, instant (98-99% right where they apply): asking what it means or to repeat ("her
#     what?", "who called?"), backchannels and talk about the call ("okay", "hold on"), naming it in English;
#   - Laya for the rest, with its own small decision head trained for this question (tools/train_reply.py) on
#     top of Laya's shared encoder, so Laya's other decisions (decide.py) are untouched.
# tools/check_reply.py measures it on hand-written examples with words it never trained on.
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
HEAD_PATH = os.path.join(HERE, "models", "reply_head.pt")
LABELS = ("understood", "not_understood", "no_signal")
# Below this confidence Laya's answer isn't used (no evidence rather than a guess). Picked on held-out training words:
# at 0.8, 90% of what it concluded there was right; on the hand-written test, 88% (tools/check_reply.py).
MIN_CONFIDENCE = 0.8
QUESTION = {
    "type": "choice",
    "instructions": "Grandma's sentence kept one Telugu word. Does the grandchild's reply show they understood that word?",
    "criteria": {
        "understood": "the reply fits the word's meaning: it refers to the thing, names it in English, or asks a follow-up "
                      "that only makes sense if they know what it is",
        "not_understood": "they ask what the word or sentence means, sound confused, mishear it, or reply as if the word "
                          "meant something else",
        "no_signal": "the reply shows nothing about the word: okay, mhm, wow, yes, a generic reply, changing the subject, "
                     "or talking about the call",
    },
}

FILLER = r"(?:um+|uh+|like|oh|wait|sorry|so|hmm+|okay|ok|yeah|and|but)"
BACKCHANNEL = re.compile(rf"^(?:{FILLER}\s*)*(?:ok(?:ay)?|mhm+|uh huh|hmm+|yeah|yes|yep|yup|right|sure|nice|cool|wow|aww?|haha|lol|"
                         r"oh|ah|acha|sare|good|great|really|yes (?:grandma|ammamma|nanamma|amma)|thank you|thanks)"
                         r"(?:[\s,.!]+(?:ok(?:ay)?|yeah|yes|sure|nice|wow|hmm+|haha|grandma|ammamma|right|good))*[\s.!]*$",
                         re.IGNORECASE)
LOST = re.compile(r"^\W*(?:(?:um+|uh+|sorry)\W+)?huh\b|\bhuh\s*\?\s*$|\b(?:pardon|come again|say (?:that|it) again|didn'?t (?:catch|get) that|i don'?t (?:understand|get it|"
                  r"know (?:that|what that) (?:word|means?))|what does (?:that|it) mean)\b|^\s*(?:sorry\s*)?what\s*\??\s*$",
                  re.IGNORECASE)


# Asking them to repeat or clarify ("repair" in conversation research): "her what?", "going where?", "who called?",
# "sorry, which pickle?", "what did you say?". Short, and the question word is the point of the reply.
REPAIR = re.compile(r"^(?:(?:sorry|wait|um+|uh+|huh|what)[\s,]+)*(?:\S+\s+){0,2}(?:what|where|who|which one)\s*\??\s*$"
                    r"|^(?:(?:sorry|wait|um+|uh+)[\s,]+)*(?:what|who|where|which)\s+(?:did you|was that|is that|called|came|"
                    r"said)\b[^.?!]{0,20}\??\s*$|^(?:sorry|wait|huh)[\s,]+(?:what|which|who|where)\b[^.?!]{0,20}\??\s*$",
                    re.IGNORECASE)
# About the call or the room, not the word: "hold on, mom's calling", "can you hear me", "anyway..."
META = re.compile(r"\b(?:hold on|one sec(?:ond)?|can you hear|you(?:'re| are) (?:breaking|cutting)|cut out|breaking up|"
                  r"(?:my )?(?:mom|dad|mum) is calling|phone is dying|bad (?:network|connection))\b|^anyway\b", re.IGNORECASE)
STOP = {"a", "an", "the", "of", "and", "with", "for", "to", "in", "on", "my", "your", "may", "you", "live", "long", "life",
        "made", "sweet", "big", "small", "really", "good", "very", "god", "yes", "okay", "dear", "thank", "goodness"}


def mentions_meaning(means, reply):
    """The reply names the thing in English ("say hi to everyone in the village" after palletooru = village)."""
    words = {w for w in re.findall(r"[a-z]+", means.lower()) if len(w) > 2 and w not in STOP}
    said = set(re.findall(r"[a-z]+", reply.lower()))
    shared = sum(w in said or w.rstrip("s") in said or w + "s" in said for w in words)
    # "chicken curry" vs "potato curry" share a word but not the thing: a longer meaning needs two words in common
    return bool(words) and shared >= min(2, len(words))


def rule(word, reply, means=None):
    """The unmistakable cases, or None."""
    text = reply.strip()
    stem = re.escape(word.lower().split()[0][:5])
    if re.match(r"^\s*uh[- ]?huh\b", text, re.IGNORECASE):
        return "no_signal"  # "uh huh" is yes, not "huh?"
    if LOST.search(text) or REPAIR.search(text) or re.search(rf"\bwhat(?:'?s| is| are| does)\b[^.?!]*\b{stem}", text, re.IGNORECASE) \
            or re.search(rf"\b{stem}\w*\s*\?*\s*what\b", text, re.IGNORECASE):
        return "not_understood"
    if BACKCHANNEL.match(text) or META.search(text):
        return "no_signal"
    if means and means.lower() != word.lower() and mentions_meaning(means, text):
        return "understood"
    return None


def state(line, word, means, reply):
    return {"grandma said": line, "Telugu word": word, "it means": means, "grandchild replied": reply}


class ReplyJudge:
    """judge(line, word, means, reply) -> (label, confidence, how). Shares decide.Decider's Laya (and its lock)."""

    def __init__(self, decider, head_path=HEAD_PATH):
        self.decider = decider
        self.agent, self.lock, self.torch = decider.agent, decider.lock, decider.torch
        self.q = self.agent._to_internal(QUESTION)
        self.head = load_head(self.agent, head_path) if head_path and os.path.exists(head_path) else None

    def laya(self, line, word, means, reply):
        """(label, confidence) from Laya: the trained head if there is one, else Laya as shipped."""
        s = state(line, word, means, reply)
        with self.lock:
            if self.head is None:
                a = self.agent.predict(s, {"q": QUESTION})["answers"]["q"]
                label, conf = a["choice"], a["confidence"]
            else:
                probs = head_probs(self.agent, self.head, [s], self.q)[0]
                label, conf = LABELS[int(probs.argmax())], float(probs.max())
            self.torch.mps.empty_cache()
        return label, conf

    def judge(self, line, word, means, reply):
        by_rule = rule(word, reply, means)
        if by_rule:
            return by_rule, 1.0, "rule"
        label, conf = self.laya(line, word, means, reply)
        if conf < MIN_CONFIDENCE:
            return "no_signal", conf, "laya unsure"
        return label, conf, "laya"


# ---------- the trained head: Laya's decision layers, retrained for this one question ----------
def encode(agent, states, q):
    """Laya's own tokenization of (state, question) rows, collated into one batch."""
    from laya.common import collate_items
    groups = [agent._encode_state(s, ["q"], {"q": q}) for s in states]
    return collate_items(groups, agent.tok.pad_token_id)


def run_encoder(model, b, device):
    """The shared, frozen part: Laya's encoder over a batch."""
    import torch
    with torch.no_grad():
        return model.encoder(input_ids=b["input_ids"].to(device), attention_mask=b["attention_mask"].to(device)).last_hidden_state


def run_head(model, head, b, device, h=None):
    """DecisionModel.forward with `head` (a copy of its head, type embedding and scorer) on the shared encoder's
    output `h` (computed here if not given)."""
    import torch
    att = b["attention_mask"].to(device)
    h = run_encoder(model, b, device) if h is None else h
    h = h + head["type_emb"](b["qtype"].to(device))[:, None, :]
    pad = ~att.bool()
    for layer in head["layers"]:
        h = layer(h, src_key_padding_mask=pad)
    pos, mask = b["marker_pos"].to(device), b["marker_mask"].to(device)
    m = torch.gather(h, 1, pos.clamp(min=0)[:, :, None].expand(-1, -1, h.size(-1)))
    return head["scorer"](m).squeeze(-1).float().masked_fill(~mask, -1e4)


def new_head(model):
    """A trainable copy of Laya's decision layers (the encoder stays shared and frozen)."""
    import copy
    import torch.nn as nn
    return nn.ModuleDict({"layers": copy.deepcopy(model.head.layers), "type_emb": copy.deepcopy(model.type_emb),
                          "scorer": copy.deepcopy(model.scorer)})


def load_head(agent, path):
    import torch
    head = new_head(agent.model).float()
    # Only the retrained layers are saved; the rest of the copy keeps Laya's own weights.
    missing, unexpected = head.load_state_dict({k: v.float() for k, v in torch.load(path, map_location="cpu").items()},
                                               strict=False)
    assert not unexpected, f"{path} doesn't match this Laya: {unexpected[:3]}"
    return head.to(agent.device).eval()


def head_probs(agent, head, states, q):
    import torch
    with torch.no_grad():
        logits = run_head(agent.model, head, encode(agent, states, q), agent.device)
    return torch.softmax(logits, -1).cpu().numpy()


# ---------- on a call: watch what the grandkid says (two-way mode transcribes their mic) ----------
REPLY_WINDOW_S = 20   # a reply this soon after a line with a kept word is taken as the reply to it
MIN_ROMAN = 4         # shorter romanized words collide with English too easily
# Romanized word-list words that are also everyday English; hearing them says nothing about Telugu
ENGLISH_TOO = {"auto", "bus", "dosa", "idli", "curry", "rice", "tea", "chai", "coffee", "temple", "cinema", "school"}


class SaidWords:
    """Word-list words in what the grandkid said: in Telugu script (how speech recognition usually writes them), or
    romanized when it's clearly not English ("pulihora", not "auto" or "dosa")."""

    def __init__(self, lexicon, lang):
        self.lexicon, self.lang = lexicon, lang
        self.roman = []
        for e in lexicon.entries.get(lang, []):
            roman = re.sub(r"[^a-z ]", "", (e.get("roman") or "").lower()).strip()
            glosses = {g.lower().rstrip(",") for g in [e.get("translate_as", "")] + e.get("match_english", []) if g}
            if len(roman) >= MIN_ROMAN and roman not in glosses and roman not in ENGLISH_TOO:
                self.roman.append((re.compile(rf"(?<![a-z]){re.escape(roman)}(?![a-z])", re.IGNORECASE), e))

    def __call__(self, text):
        found = {e["id"]: e for e in self.lexicon.find(text, self.lang)}
        for pattern, e in self.roman:
            if pattern.search(text):
                found.setdefault(e["id"], e)
        return list(found.values())


class ReplyWatch:
    """Turns what the grandkid says into evidence for progress.py:
      - saying a Telugu word themselves ("said": the strongest sign they know it);
      - their reply to a line that kept a word in Telugu ("replied" if it shows they understood it, "confused" if it
        shows they didn't; nothing for "okay").
    `shown` is called for each line shown to them with words kept in Telugu, `heard` with each thing they say.
    `learner()` says whether the person at this mic is the one learning Telugu (the English speaker)."""

    def __init__(self, judge, progress, lexicon, lang, learner=lambda: True, log=print):
        import threading
        self.judge, self.progress, self.learner, self.log = judge, progress, learner, log
        self.said = SaidWords(lexicon, lang)
        self.waiting = None  # (time, line shown, kept words) awaiting a reply
        self.lock = threading.Lock()

    def shown(self, line, kept):
        import time
        with self.lock:
            self.waiting = (time.monotonic(), line, list(kept))

    def heard(self, text):
        import threading
        import time
        if not self.learner():
            return
        for e in self.said(text):
            if rule(e.get("roman") or e["id"], text) == "not_understood":
                continue  # "what's mamidi?" names the word but isn't knowing it
            self.progress.observe(e["id"], "said")
            self.log(f"  [you said {e.get('roman') or e['id']}: you know it]")
        with self.lock:
            waiting, self.waiting = self.waiting, None
        if waiting and time.monotonic() - waiting[0] <= REPLY_WINDOW_S:
            threading.Thread(target=self._judge, args=(waiting[1], waiting[2], text), daemon=True).start()

    def _judge(self, line, kept, reply):
        for k in kept:
            try:
                label, conf, how = self.judge.judge(line, k["telugu"], k["english"], reply)
            except Exception as e:
                self.log(f"  (reply check failed: {type(e).__name__}: {e})")
                return
            if label == "no_signal":
                continue
            self.progress.observe(k["id"], "replied" if label == "understood" else "confused")
            self.log(f"  [your reply {'shows you understood' if label == 'understood' else 'shows you did not get'} "
                     f"{k['telugu']} ({how} {conf:.0%})]")

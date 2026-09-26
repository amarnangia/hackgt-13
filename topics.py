# "Ask her about it": when she mentions something with a picture or a card (pulihora, Sankranti, Thatayya, a proverb),
# suggest a question in simple Telugu that turns it into a story she can tell ("How do you make pulihora? Will you
# teach me?"). Hand-written templates, no model call, so the question is ready the moment she pauses; prompts.py
# shows it (instead of asking Muse Spark for one) and never repeats a topic in a call.

# {te}/{ro}/{en}: the thing's name in Telugu script, romanized, and in English
KIND = {
    "food": ("{te} ఎలా చేస్తారు? నాకు నేర్పిస్తారా?", "{ro} ela chestaru? Naaku nerpistara?", "How do you make {en}? Will you teach me?"),
    "festival": ("మీ చిన్నప్పుడు {te} ఎలా జరుపుకునేవారు?", "Mee chinnappudu {ro} ela jarupukunevaaru?",
                 "How did you celebrate {en} when you were little?"),
    "place": ("{te} గురించి చెప్పండి. మీరు అక్కడికి ఎప్పుడు వెళ్ళారు?", "{ro} gurinchi cheppandi. Meeru akkadiki eppudu vellaru?",
              "Tell me about {en}. When did you go there?"),
    "nature": ("మీ చిన్నప్పుడు ఇంటి దగ్గర {te} ఉండేదా?", "Mee chinnappudu inti daggara {ro} undeda?",
               "Was there {en} near your house when you were little?"),
    "clothing": ("మీరు {te} ఎప్పుడు వేసుకునేవారు?", "Meeru {ro} eppudu vesukunevaaru?", "When did you use to wear {en}?"),
    "vehicle": ("చిన్నప్పుడు {te} లో ఎక్కడికి వెళ్ళేవారు?", "Chinnappudu {ro} lo ekkadiki vellevaaru?",
                "Where did you go by {en} when you were young?"),
    "household": ("మీ ఇంట్లో {te} ఉండేదా? దాని గురించి చెప్పండి", "Mee intlo {ro} undeda? Daani gurinchi cheppandi",
                  "Did you have {en} at home? Tell me about it"),
    "game": ("మీరు చిన్నప్పుడు {te} ఆడేవారా? ఎవరితో?", "Meeru chinnappudu {ro} aadevaara? Evaritho?",
             "Did you play {en} as a child? With whom?"),
    "art": ("మీరు ఎప్పుడైనా {te} నేర్చుకున్నారా?", "Meeru eppudaina {ro} nerchukunnara?", "Did you ever learn {en}?"),
    "show": ("మీ చిన్నప్పుడు {te} చూసేవారా?", "Mee chinnappudu {ro} chusevaara?", "Did you use to see {en} when you were little?"),
    "person": ("{te} గురించి మీకు ఏం గుర్తుంది?", "{ro} gurinchi meeku em gurthundi?", "What do you remember about {en}?"),
    "film": ("{te} మీరు మొదటిసారి ఎక్కడ చూశారు?", "{ro} meeru modatisari ekkada chusaru?", "Where did you first watch {en}?"),
    "epic": ("{te} లో మీకు ఇష్టమైన కథ చెప్పండి", "{ro} lo meeku ishtamaina katha cheppandi", "Tell me your favourite story from the {en}"),
    "ceremony": ("మన ఇంట్లో జరిగిన {te} గురించి చెప్పండి", "Mana intlo jarigina {ro} gurinchi cheppandi",
                 "Tell me about a {en} in our family"),
    "memory": ("{te} గురించి మీకు ఏదైనా జ్ఞాపకం ఉందా?", "{ro} gurinchi meeku edaina gnapakam undaa?", "Do you have a memory about {en}?"),
    "idiom": ("ఈ సామెత మీకు ఎవరు నేర్పారు?", "Ee sametha meeku evaru nerparu?", "Who taught you this saying?"),
    "relative": ("{te} చిన్నప్పుడు ఎలా ఉండేవారు?", "{ro} chinnappudu ela undevaaru?", "What was {ro} like when they were little?"),
}
# Word-list categories that don't name their kind of question directly
CATEGORY_KIND = {"culture": "memory"}
RELATIVES = {"nanamma", "mamayya", "attayya", "babai", "pinni", "peddamma", "pedananna", "atta", "muttata", "muttavva"}

# Better questions for the things that come up most (library or word-list id)
SPECIAL = {
    "wedding": ("మీ పెళ్ళి ఎలా జరిగింది?", "Mee pelli ela jarigindi?", "How was your wedding?"),
    "pelli": ("మీ పెళ్ళి ఎలా జరిగింది?", "Mee pelli ela jarigindi?", "How was your wedding?"),
    "thatayya": ("మీరు, తాతయ్య ఎలా కలిశారు?", "Meeru, Thatayya ela kalisaru?", "How did you and Thatayya meet?"),
    "amma": ("అమ్మ చిన్నప్పుడు ఎలా ఉండేది?", "Amma chinnappudu ela undedi?", "What was Mom like as a little girl?"),
    "temple": ("మీరు ఏ గుడికి వెళ్ళేవారు?", "Meeru ye gudiki vellevaaru?", "Which temple did you use to go to?"),
    "polam": ("మన పొలంలో ఏం పండించేవారు?", "Mana polamlo em pandinchevaaru?", "What did we grow in our fields?"),
    "paddy_field": ("మన పొలంలో ఏం పండించేవారు?", "Mana polamlo em pandinchevaaru?", "What did we grow in our fields?"),
    "silk_saree": ("మీ పెళ్ళి పట్టుచీర ఎలా ఉండేది?", "Mee pelli pattu cheera ela undedi?", "What was your wedding silk saree like?"),
    "pattu_cheera": ("మీ పెళ్ళి పట్టుచీర ఎలా ఉండేది?", "Mee pelli pattu cheera ela undedi?", "What was your wedding silk saree like?"),
    "kite": ("చిన్నప్పుడు గాలిపటాలు ఎగరేసేవారా?", "Chinnappudu galipatalu egaresevaara?", "Did you fly kites when you were little?"),
    "galipatam": ("చిన్నప్పుడు గాలిపటాలు ఎగరేసేవారా?", "Chinnappudu galipatalu egaresevaara?", "Did you fly kites when you were little?"),
    "rangoli": ("ముగ్గులు వేయడం నాకు నేర్పిస్తారా?", "Muggulu veyadam naaku nerpistara?", "Will you teach me to draw muggulu?"),
    "muggu": ("ముగ్గులు వేయడం నాకు నేర్పిస్తారా?", "Muggulu veyadam naaku nerpistara?", "Will you teach me to draw muggulu?"),
    "mango_tree": ("ఆ మామిడి చెట్టు ఎక్కేవారా?", "Aa mamidi chettu ekkevaara?", "Did you use to climb that mango tree?"),
    "mamidi_chettu": ("ఆ మామిడి చెట్టు ఎక్కేవారా?", "Aa mamidi chettu ekkevaara?", "Did you use to climb that mango tree?"),
    "ooru": ("మన ఊరు ఎలా ఉండేది?", "Mana ooru ela undedi?", "What was our village like?"),
    "palle": ("మన ఊరు ఎలా ఉండేది?", "Mana ooru ela undedi?", "What was our village like?"),
    "badi": ("మీ బడి ఎలా ఉండేది?", "Mee badi ela undedi?", "What was your school like?"),
    "cinema": ("మీకు ఇష్టమైన సినిమా ఏది?", "Meeku ishtamaina cinema edi?", "What's your favourite movie?"),
    "avakaya": ("ఆవకాయ ఎలా పెడతారు? నాకు నేర్పిస్తారా?", "Avakaya ela pedataru? Naaku nerpistara?",
                "How do you make avakaya? Will you teach me?"),
}


def _plain(name):
    """'Muggu (rangoli)' -> 'Muggu'; the card already explains it."""
    return name.split(" (")[0].strip()


def _fill(template, te, ro, en, about, key):
    t, r, e = (part.format(te=te, ro=ro, en=en) for part in template)
    return {"telugu": t, "roman": r[:1].upper() + r[1:], "english": e, "about": about, "key": key}


def about(hits, picture=None, lexicon=None):
    """The question to suggest for this line, or None. `hits`: word-list entries in what she said; `picture`: the
    card that popped up (pictures.PictureFinder.card), which wins because it's what the grandkid is looking at."""
    by_id = {e["id"]: e for e in (lexicon or [])}
    if picture and picture.get("id") and not str(picture["id"]).startswith("web:"):
        key = picture["id"]
        # its Telugu name: the word she used, else the word list's entry for it, else the English name
        entry = next((h for h in hits if h["id"] in picture.get("lexicon_ids", [])), None) \
            or next((by_id[i] for i in picture.get("lexicon_ids", []) if i in by_id), None)
        name = _plain(picture["name"])
        te = entry["forms"][0].strip(" ,.^") if entry else name
        ro = (entry.get("roman") or name) if entry else name
        special = SPECIAL.get(key) or (entry and SPECIAL.get(entry["id"]))
        template = special or KIND.get(picture.get("kind") or picture.get("category"), KIND["memory"])
        return _fill(template, te, ro, name, name, key)
    if picture:  # a Wikipedia picture of something not in the library
        return _fill(KIND["memory"], picture["name"], picture["name"], picture["name"], picture["name"], picture["id"])
    for h in hits:  # otherwise the most story-worthy word she used
        te, ro = h["forms"][0].strip(" ,.^"), h.get("roman") or h["id"].replace("_", " ")
        name = ro[:1].upper() + ro[1:]
        if h.get("ask"):
            return {**h["ask"], "about": name, "key": h["id"]}
        if h["id"] in SPECIAL:
            return _fill(SPECIAL[h["id"]], te, ro, h.get("translate_as") or name, name, h["id"])
        if h["category"] == "idiom" and h.get("note"):
            return _fill(KIND["idiom"], te, ro, "", "this saying", h["id"])
        if h["id"] in RELATIVES:
            return _fill(KIND["relative"], te, name, name, name, h["id"])
        kind = CATEGORY_KIND.get(h["category"], h["category"])
        if kind in ("food", "festival", "place", "vehicle", "clothing", "memory") and h.get("roman"):
            return _fill(KIND[kind], te, ro, name, name, h["id"])  # her word, so the grandkid learns it
    return None

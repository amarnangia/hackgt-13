# A pretend call for building the overlay without a real call, audio or models: plays a scripted conversation
# with Ammamma over the same WebSocket and message format as subtitles.py (ws://localhost:8765), serves the
# pictures, and answers the overlay's clicks. Loops until Ctrl+C.
#   python tools/fake_call.py            # then open WhatsApp Web (with the extension) or extension/dev.html
#   python tools/fake_call.py --fast     # shorter pauses
# Don't run it at the same time as subtitles.py: both use port 8765.
import argparse
import http
import json
import mimetypes
import os
import sys
import threading
import time

from websockets.datastructures import Headers
from websockets.http11 import Response
from websockets.sync.server import serve

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from lexicon import Lexicon  # noqa: E402
from pictures import PictureFinder  # noqa: E402

CALLER = "Ammamma"
# (Telugu she says, English shown, words kept in Telugu, intent, picture id, topic)
SCRIPT = [
    ("నమస్కారం నాన్నా, బాగున్నావా?", "Hello Nanna, are you doing well?", ["nanna_vocative"], "question", None, None),
    ("అన్నం తిన్నావా?", "Have you eaten?", [], "question", None, None),
    ("నిన్న సంక్రాంతికి గవ్వలు, అరిసెలు చేశాను.", "Yesterday I made shell-shaped sweets and rice sweets for Sankranti.", [], "statement", "gavvalu", "Food and cooking"),
    ("పులిహోర కూడా చేశాను, నీకు చాలా ఇష్టం కదా.", "I made tamarind rice too, you like it a lot, right?", [], "question", "pulihora", "Food and cooking"),
    ("మా చిన్నప్పుడు భోగి మంటలు వేసేవాళ్ళం, గంగిరెద్దులు ఇంటికి వచ్చేవి.", "When we were little we lit Bhogi bonfires, and decorated bulls came to the house.", [], "statement", "bhogi", "Festivals"),
    ("నోరు మంచిదైతే ఊరు మంచిది అని మా అమ్మ చెప్పేది.", "My Amma used to say, if your words are kind, the whole village is kind.", ["amma"], "statement", None, "Family"),
    ("మీ తాతయ్య ఎన్టీఆర్ సినిమాలు చాలా ఇష్టపడేవారు.", "Your Thatayya loved NTR movies.", ["thatayya"], "statement", "ntr", "Family"),
    ("బాగా చదువుకో, జాగ్రత్తగా ఉండు.", "Study well, take care.", [], "request", None, None),
]
TOPIC_WORDS = {
    "Food and cooking": [("అన్నం", "annam", "rice"), ("కూర", "kura", "curry"), ("పచ్చడి", "pachadi", "chutney"), ("పెరుగు", "perugu", "yogurt"),
                         ("తిన్నాను", "tinnanu", "I ate"), ("చాలా బాగుంది", "chala bagundi", "it's really good"), ("ఆకలి", "aakali", "hunger")],
    "Festivals": [("పండుగ", "pandaga", "festival"), ("ముగ్గు", "muggu", "rangoli"), ("పూజ", "puja", "prayer"), ("గుడి", "gudi", "temple"),
                  ("కొత్త బట్టలు", "kotta battalu", "new clothes"), ("శుభాకాంక్షలు", "subhakankshalu", "best wishes")],
    "Family": [("అమ్మ", "amma", "mom"), ("నాన్న", "nanna", "dad"), ("తాతయ్య", "thatayya", "grandpa"), ("అక్క", "akka", "older sister"),
               ("అన్నయ్య", "annayya", "older brother"), ("చుట్టాలు", "chuttalu", "relatives")],
}
ASKS = {  # prompts at a few points: (after line index, question)
    1: {"telugu": "గవ్వలు ఎలా చేస్తారు? నాకు నేర్పిస్తారా?", "roman": "Gavvalu ela chestaru? Naaku nerpistara?",
        "english": "How do you make gavvalu? Will you teach me?", "about": "Gavvalu"},
    4: {"telugu": "మీ చిన్నప్పుడు భోగి ఎలా జరుపుకునేవారు?", "roman": "Mee chinnappudu Bhogi ela jarupukunevaaru?",
        "english": "How did you celebrate Bhogi when you were little?", "about": "Bhogi"},
    6: {"telugu": "మీరు, తాతయ్య ఎలా కలిశారు?", "roman": "Meeru, Thatayya ela kalisaru?", "english": "How did you and Thatayya meet?",
        "about": "Thatayya"},
}

clients = set()
lexicon = Lexicon()
entries = {e["id"]: e for e in lexicon.entries["te"]}
pictures = PictureFinder(None)


def broadcast(msg):
    data = json.dumps(msg, ensure_ascii=False)
    for c in list(clients):
        try:
            c.send(data)
        except Exception:
            clients.discard(c)


def cards(telugu):
    """The same card fields subtitles.py sends in "details"."""
    out = []
    for e in lexicon.find(telugu, "te"):
        title = (e.get("roman") or (e["forms"][0] if e["category"] == "idiom" else e["id"].replace("_", " ").title())).strip(" ,^")
        out.append({"id": e["id"], "title": title, "category": e["category"], "note": e.get("note", ""),
                    "telugu": e["forms"][0].strip(" ,.^"), "english": e.get("translate_as") or (e.get("match_english") or [""])[0],
                    "p": 0.95 if e.get("start_known") else 0.3})
    return out


def handler(conn):
    clients.add(conn)
    try:
        for raw in conn:
            msg = json.loads(raw)
            e = entries.get(msg.get("id"))
            if msg.get("type") == "ask" and e:
                broadcast({"type": "answer", "id": e["id"], "text": e.get("note") or e.get("translate_as", ""),
                           "telugu": e["forms"][0].strip(" ,.^"), "roman": (e.get("roman") or "").strip(" ,")})
            print("overlay says:", msg, flush=True)
    finally:
        clients.discard(conn)


def serve_files(conn, request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None
    path = request.path.split("?")[0]
    file = os.path.realpath(os.path.join(ROOT, path.lstrip("/")))
    if not path.startswith("/images/") or not file.startswith(os.path.join(ROOT, "images") + os.sep) or not os.path.isfile(file):
        return conn.respond(http.HTTPStatus.NOT_FOUND, "not found")
    body = open(file, "rb").read()
    return Response(http.HTTPStatus.OK, "OK", Headers([("Content-Type", mimetypes.guess_type(file)[0] or "image/jpeg"),
                                                       ("Content-Length", str(len(body))), ("Connection", "close")]), body)


def play(pause):
    time.sleep(2)
    n = 0
    while True:
        broadcast({"type": "topic", "topic": "Greetings", "words": []})
        for i, (telugu, english, kept_ids, intent, pic, topic) in enumerate(SCRIPT):
            n += 1
            broadcast({"type": "speaking"})
            words = telugu.split()
            for k in range(1, len(words) + 1):  # her words appear as Muse hears them
                broadcast({"type": "partial", "text": " ".join(words[:k])})
                time.sleep(0.25)
            broadcast({"type": "partial", "text": ""})
            broadcast({"type": "original", "id": n, "text": telugu, "route": "native"})
            time.sleep(0.5)
            kept, shown = [], english
            for wid in kept_ids:
                roman = entries[wid]["roman"].strip(" ,")
                gloss = entries[wid].get("translate_as", "").strip(" ,")
                if gloss and gloss.lower() in shown.lower():
                    start = shown.lower().index(gloss.lower())
                    shown = shown[:start] + roman + shown[start + len(gloss):]
                kept.append({"id": wid, "telugu": roman, "english": gloss})
            broadcast({"type": "english", "id": n, "text": shown, "route": "native", "kept": kept})
            broadcast({"type": "details", "id": n, "intent": intent, "cards": cards(telugu)})
            if pic:
                broadcast({"type": "picture", **pictures.card(pic), "line": n})
            if topic:
                broadcast({"type": "topic", "topic": topic,
                           "words": [{"id": None, "telugu": t, "roman": r, "english": en} for t, r, en in TOPIC_WORDS[topic]]})
            if i in ASKS:
                time.sleep(1.2)
                broadcast({"type": "prompt", "caller": CALLER, **ASKS[i]})
            time.sleep(pause)
        time.sleep(pause * 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--fast", action="store_true")
    a = ap.parse_args()
    server = serve(handler, "localhost", a.port, process_request=serve_files)
    threading.Thread(target=play, args=(2.5 if a.fast else 5.0,), daemon=True).start()
    print(f"Pretend call with {CALLER} on ws://localhost:{a.port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

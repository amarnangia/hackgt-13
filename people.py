# The family: everyone who uses Weave or gets called, and whether they have a personalized voice (eleven.py).
# The iPhone app asks "who are you?" from this list (garden/server.py /api/people), and subtitles.py looks up a
# person's voice here by --me / --caller. Kept in calls/people.json (gitignored) and in Firestore, one document per
# person (sync.py), so every laptop on the team has the same people.
#
#   {person id: {name, updated, voice_id?, voice_created?, consent_by?, bytes?}}
#
# voice_id is None once their voice is removed; `updated` says which copy is newer when laptops disagree.
import json
import os
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "calls", "people.json")
_lock = threading.Lock()  # the Weave server handles requests on several threads


def person_id(name):
    """Same id the iPhone app gives a person (People.swift): "Ammamma" -> "ammamma", "Saanvi R" -> "saanvi-r"."""
    return name.strip().lower().replace(" ", "-")


def load():
    try:
        return json.load(open(REGISTRY, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(everyone):
    os.makedirs(os.path.dirname(REGISTRY), exist_ok=True)
    json.dump(everyone, open(REGISTRY, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def update(name, **fields):
    """Add `name` if new, set `fields` on them, and return (id, record)."""
    pid = person_id(name)
    with _lock:
        everyone = load()
        record = {**everyone.get(pid, {}), "name": name.strip(), **fields, "updated": time.time()}
        everyone[pid] = record
        save(everyone)
    return pid, record


def add(name):
    pid, record = person_id(name), load().get(person_id(name))
    return (pid, record) if record else update(name)


def voice_for(name):
    """This person's ElevenLabs voice_id, or None."""
    return load().get(person_id(name), {}).get("voice_id")


def merge(a, b):
    """Per person, the newer record."""
    out = dict(a)
    for pid, record in b.items():
        if pid not in out or record.get("updated", 0) > out[pid].get("updated", 0):
            out[pid] = record
    return out

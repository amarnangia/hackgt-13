# Keeps the team's laptops in step through Firestore: pull() when subtitles.py starts, push() when the call ends.
# The local files stay the working copy; if Firebase can't be reached the call goes on without it.
#   python sync.py pull | push        # by hand
# Needs FIREBASE_KEY=<path to a service-account key> in .env (keep the key outside the repo, e.g. ~/.config/weave/).
# Firestore's rules deny every client; the Admin SDK ignores rules, so only laptops with a key can read or write.
# What syncs: progress.json (merged per word), garden/garden.db and calls/family_dictionary.json (newest wins), and
# each call's text files (call.json, the story page), add-only by folder. Recordings stay on the laptop (no Storage bucket).
# And the family (people.py: everyone, and who has a personalized ElevenLabs voice): one document per person in
# weave/people/members/{person id}, merged per person (the newer change wins).
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRESS = os.path.join(HERE, "progress.json")
GARDEN = os.path.join(HERE, "garden", "garden.db")
CALLS = os.path.join(HERE, "calls")
SHARED = ["family_dictionary.json", "dictionary.html"]  # in calls/, newest wins
CALL_FILES = (".json", ".html", ".txt")
TIMEOUT_S = 20

_db = None


def _key_path():
    key = os.environ.get("FIREBASE_KEY")
    if not key and os.path.exists(os.path.join(HERE, ".env")):
        for line in open(os.path.join(HERE, ".env")):
            if line.startswith("FIREBASE_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    return os.path.expanduser(key) if key else None


def _client():
    global _db
    if _db is None:
        import firebase_admin
        from firebase_admin import credentials, firestore
        firebase_admin.initialize_app(credentials.Certificate(_key_path()))
        _db = firestore.client()
    return _db


def _col():
    return _client().collection("weave")


# ---------- progress.json: merged, so two laptops' learning both count ----------
def _read_json(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def merge_progress(a, b):
    """Per word, the newer estimate; per word, the higher hearing count."""
    words = dict(a.get("words", {}))
    for wid, w in b.get("words", {}).items():
        if wid not in words or w.get("t", 0) > words[wid].get("t", 0):
            words[wid] = w
    heard = dict(a.get("heard", {}))
    for wid, n in b.get("heard", {}).items():
        heard[wid] = max(n, heard.get(wid, 0))
    return {"heard": heard, "words": words}


def _remote_progress():
    doc = _col().document("progress").get()
    return json.loads(doc.get("json")) if doc.exists else {}


def _write_json(path, data):
    json.dump(data, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# ---------- whole files, newest wins ----------
def _file_bytes(path):
    if path.endswith(".db"):  # a consistent copy even if the garden app has it open
        with sqlite3.connect(path) as c:
            return c.serialize()
    return open(path, "rb").read()


def _pull_file(name, path):
    doc = _col().document(name).get()
    if doc.exists and doc.get("mtime") > (os.path.getmtime(path) if os.path.exists(path) else 0) + 1:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(doc.get("data"))
        os.utime(path, (doc.get("mtime"), doc.get("mtime")))
        return True


def _push_file(name, path):
    if not os.path.exists(path):
        return
    doc = _col().document(name).get()
    mtime = os.path.getmtime(path)
    if not doc.exists or mtime > doc.get("mtime") + 1:
        _col().document(name).set({"data": _file_bytes(path), "mtime": mtime})
        return True


def _shared():
    return [("garden.db", GARDEN)] + [(n, os.path.join(CALLS, n)) for n in SHARED]


# ---------- calls/: add-only by folder name ----------
def _local_calls():
    if not os.path.isdir(CALLS):
        return []
    return sorted(d for d in os.listdir(CALLS) if os.path.isdir(os.path.join(CALLS, d)))


def _calls_col():
    return _col().document("calls").collection("calls")


def _pull_calls():
    have, n = set(_local_calls()), 0
    for ref in _calls_col().list_documents():
        if ref.id in have:
            continue
        doc = ref.get()
        folder = os.path.join(CALLS, doc.id)
        os.makedirs(folder, exist_ok=True)
        for f in doc.get("files"):
            open(os.path.join(folder, f["name"]), "w", encoding="utf-8").write(f["text"])
        n += 1
    return n


def _push_calls():
    remote = {d.id for d in _calls_col().select([]).stream()}
    n = 0
    for name in _local_calls():
        if name in remote:
            continue
        folder = os.path.join(CALLS, name)
        files = [{"name": f, "text": open(os.path.join(folder, f), encoding="utf-8").read()}
                 for f in sorted(os.listdir(folder)) if f.endswith(CALL_FILES)]
        if files:
            _calls_col().document(name).set({"files": files})
            n += 1
    return n


# ---------- people: one document per person ----------
def _people_col():
    return _col().document("people").collection("members")


def _sync_people():
    import people
    local = people.load()
    remote = {d.id: d.to_dict() for d in _people_col().stream()}
    merged = people.merge(local, remote)
    if merged != local:
        people.save(merged)
    for pid, record in merged.items():
        if remote.get(pid) != record:
            _people_col().document(pid).set(record)
    return ["people"] if merged != local or merged != remote else []


# ---------- pull / push ----------
def _pull(skip_progress=False):
    done = []
    if not skip_progress:
        local, remote = _read_json(PROGRESS), _remote_progress()
        if remote and (merged := merge_progress(local, remote)) != local:
            _write_json(PROGRESS, merged)
            done.append("progress")
    done += [name for name, path in _shared() if _pull_file(name, path)]
    if n := _pull_calls():
        done.append(f"{n} call(s)")
    return done + _sync_people()


def _push(replace_progress=False):
    done = []
    local, remote = _read_json(PROGRESS), _remote_progress()
    merged = local if replace_progress else merge_progress(local, remote)
    if (local or replace_progress) and merged != remote:
        _col().document("progress").set({"json": json.dumps(merged, ensure_ascii=False)})
        done.append("progress")
    done += [name for name, path in _shared() if _push_file(name, path)]
    if n := _push_calls():
        done.append(f"{n} call(s)")
    return done + _sync_people()


def _run(what, fn, **kw):
    """fn in the background with a time limit; never raises. No key set up = quietly off."""
    key = _key_path()
    if not key:
        return
    if not os.path.exists(key):
        print(f"Sync off: FIREBASE_KEY points to {key}, which doesn't exist.", flush=True)
        return
    pool = ThreadPoolExecutor(1)
    try:
        done = pool.submit(fn, **kw).result(timeout=TIMEOUT_S)
        print(f"Firebase {what}: {', '.join(done) or 'already up to date'}.", flush=True)
    except ImportError:
        print("Sync off: pip install firebase-admin", flush=True)
    except Exception as e:  # offline, timed out, bad key: the local files are still there
        print(f"Firebase {what} failed ({type(e).__name__}: {str(e)[:120]}); using the local files.", flush=True)
    finally:
        pool.shutdown(wait=False)


def pull(skip_progress=False):
    _run("pull", _pull, skip_progress=skip_progress)


def push(replace_progress=False):
    _run("push", _push, replace_progress=replace_progress)


def people():
    """Right after someone is added, or records or removes a voice, in the Weave app, so the other laptops get it."""
    _run("people", _sync_people)


if __name__ == "__main__":
    {"pull": pull, "push": push}.get(sys.argv[1] if len(sys.argv) > 1 else "",
                                     lambda: sys.exit("usage: python sync.py pull | push"))()

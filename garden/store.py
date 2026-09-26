"""Known-words garden: every phrase heard on a call is a plant. Feeds the dashboard and phone widget.

Hearing a phrase waters it; tapping "?" on its subtitle cuts it back a stage.
    seed    growth < 3        -> dub it in English
    sprout  3 <= growth < 8   -> original audio + subtitle
    bloom   growth >= 8       -> original audio, faint or no subtitle

`heard` is the lifetime count (for stats); `growth` drives the stage and drops when you ask.

Pipeline usage:
    from garden import Garden
    g = Garden()
    with g.call():                                   # optional: tracks call count/minutes
        mode = g.heard("పులిహోర", english="tamarind rice", category="food", note="Tangy tamarind rice", roman="pulihora")
        # mode is "dub" | "subtitle" | "none" - how to present it *this* time
        g.asked("పులిహోర")                           # the "?" button
"""
import json, os, sqlite3, time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent / "garden.db"
SUBTITLE_AT, BLOOM_AT = 3, 8
CATEGORIES = ("food", "vehicle", "place", "clothing", "festival", "family", "idiom", "slang", "none")  # lexicon.json categories
FLOWER_FOR = {"culture": "festival", "phrase": "idiom"}  # lexicon.json's other categories; plain "word" is jasmine


def from_lexicon(entry):
    """heard() arguments for a lexicon.json entry, the way the translator finds words in what was said."""
    return dict(phrase=entry["forms"][0].strip(" ,.^"), english=(entry.get("translate_as") or entry.get("note") or "").strip(" ,") or None,
                category=FLOWER_FOR.get(entry.get("category"), entry.get("category")), note=entry.get("note") or None,
                roman=entry.get("roman") or entry["id"].replace("_", " "))


def stage(growth):
    return "bloom" if growth >= BLOOM_AT else "sprout" if growth >= SUBTITLE_AT else "seed"


def mode(growth):
    return {"seed": "dub", "sprout": "subtitle", "bloom": "none"}[stage(growth)]


def _key(phrase):
    return " ".join(phrase.lower().split())


def _day(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


class Garden:
    def __init__(self, db=None):
        self.db = str(db or os.environ.get("GARDEN_DB") or DEFAULT_DB)
        self._call_id = None
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS phrases (
                    phrase TEXT PRIMARY KEY, english TEXT, category TEXT DEFAULT 'none', note TEXT, roman TEXT,
                    heard INT DEFAULT 0, asked INT DEFAULT 0, growth INT DEFAULT 0,
                    first_heard REAL, last_heard REAL, last_asked REAL);
                CREATE TABLE IF NOT EXISTS events (ts REAL, phrase TEXT, kind TEXT);  -- heard | asked | sprouted | bloomed
                CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, started REAL, ended REAL);
                CREATE TABLE IF NOT EXISTS call_keys (key TEXT PRIMARY KEY);  -- story keeper call ids already counted
                CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
            """)

    def _conn(self):
        c = sqlite3.connect(self.db, timeout=5)
        c.row_factory = sqlite3.Row
        return c

    # --- writes (called by the pipeline) ---

    def heard(self, phrase, english=None, category=None, note=None, roman=None, ts=None):
        """Record one hearing. Returns how to present it this time: "dub", "subtitle" or "none"."""
        k, ts = _key(phrase), ts or time.time()
        with self._conn() as c:
            row = c.execute("SELECT growth FROM phrases WHERE phrase=?", (k,)).fetchone()
            before = row["growth"] if row else 0
            c.execute("""INSERT INTO phrases (phrase, english, category, note, roman, heard, growth, first_heard, last_heard)
                         VALUES (?, ?, ?, ?, ?, 1, 1, ?, ?)
                         ON CONFLICT(phrase) DO UPDATE SET heard=heard+1, growth=growth+1, last_heard=excluded.last_heard,
                           english=COALESCE(excluded.english, english), category=COALESCE(excluded.category, category),
                           note=COALESCE(excluded.note, note), roman=COALESCE(excluded.roman, roman)""",
                      (k, english, category if category in CATEGORIES else None, note, roman, ts, ts))
            c.execute("INSERT INTO events VALUES (?, ?, 'heard')", (ts, k))
            if stage(before + 1) != stage(before):
                c.execute("INSERT INTO events VALUES (?, ?, ?)", (ts, k, "bloomed" if stage(before + 1) == "bloom" else "sprouted"))
        return mode(before)

    def asked(self, phrase, ts=None):
        """The "?" button: drop the phrase back to the start of the stage below."""
        k, ts = _key(phrase), ts or time.time()
        with self._conn() as c:
            row = c.execute("SELECT growth FROM phrases WHERE phrase=?", (k,)).fetchone()
            if not row:
                return
            growth = SUBTITLE_AT if row["growth"] >= BLOOM_AT else 0
            c.execute("UPDATE phrases SET asked=asked+1, growth=?, last_asked=? WHERE phrase=?", (growth, ts, k))
            c.execute("INSERT INTO events VALUES (?, ?, 'asked')", (ts, k))

    def mode(self, phrase):
        with self._conn() as c:
            row = c.execute("SELECT growth FROM phrases WHERE phrase=?", (_key(phrase),)).fetchone()
        return mode(row["growth"] if row else 0)

    @contextmanager
    def call(self, started=None, key=None):
        """key: the story keeper's call id (calls/<id>/), so import_calls() won't count this call again."""
        with self._conn() as c:
            c.execute("UPDATE calls SET ended=started WHERE ended IS NULL")  # a call the translator never closed (it crashed)
            self._call_id = c.execute("INSERT INTO calls (started) VALUES (?)", (started or time.time(),)).lastrowid
            if key:
                c.execute("INSERT OR IGNORE INTO call_keys VALUES (?)", (key,))
        try:
            yield self
        finally:
            with self._conn() as c:
                c.execute("UPDATE calls SET ended=? WHERE id=?", (time.time(), self._call_id))
            self._call_id = None

    def import_calls(self, calls_dir, lexicon, lang="te"):
        """Plant the words from calls the story keeper saved (calls/*/call.json) that aren't in the garden yet,
        e.g. calls made before the translator fed the garden. Returns how many calls were added."""
        added = 0
        for f in sorted(Path(calls_dir).glob("*/call.json")):
            try:
                call = json.load(open(f, encoding="utf-8"))
                start = time.mktime(time.strptime(call["started"][:16], "%Y-%m-%dT%H:%M"))
            except (OSError, ValueError, KeyError):
                continue
            with self._conn() as c:
                if c.execute("SELECT 1 FROM call_keys WHERE key=?", (call["id"],)).fetchone():
                    continue
                c.execute("INSERT INTO call_keys VALUES (?)", (call["id"],))
                c.execute("INSERT INTO calls (started, ended) VALUES (?, ?)", (start, start + (call.get("duration_s") or 0)))
            for i, line in enumerate(call.get("lines") or []):
                if line.get("route") == "english":
                    continue  # she said it in English: no Telugu words heard
                for entry in lexicon.find(line.get("telugu", ""), lang):
                    self.heard(**from_lexicon(entry), ts=start + (line.get("start_s") or i * 5))
            added += 1
        return added

    # --- reads (dashboard + widget) ---

    def snapshot(self, days=14):
        now = time.time()
        with self._conn() as c:
            plants = [dict(r) for r in c.execute("SELECT * FROM phrases ORDER BY first_heard")]
            events = [dict(r) for r in c.execute("SELECT * FROM events WHERE ts > ? ORDER BY ts", (now - days * 86400,))]
            recent = [dict(r) for r in c.execute("SELECT * FROM events WHERE kind != 'heard' ORDER BY ts DESC LIMIT 10")]
            recent += [dict(r) for r in c.execute("SELECT * FROM events WHERE kind = 'heard' AND ts > ? ORDER BY ts DESC LIMIT 2", (now - 600,))]
            recent.sort(key=lambda e: -e["ts"])
            calls = c.execute("SELECT COUNT(*) n, SUM(COALESCE(ended, ?) - started) secs, MAX(started) last FROM calls", (now,)).fetchone()
            live = c.execute("SELECT 1 FROM calls WHERE ended IS NULL LIMIT 1").fetchone() is not None
            active_days = {r[0] for r in c.execute("SELECT DISTINCT date(ts, 'unixepoch', 'localtime') FROM events WHERE kind='heard'")}

        for p in plants:
            p["category"] = p["category"] or "none"
            p["stage"], p["mode"] = stage(p["growth"]), mode(p["growth"])
            p["to_next"] = (SUBTITLE_AT if p["stage"] == "seed" else BLOOM_AT) - p["growth"] if p["stage"] != "bloom" else 0
            p["thirsty"] = bool(p["last_asked"] and now - p["last_asked"] < 3 * 86400 and p["stage"] != "bloom")

        by_day = {_day(now - i * 86400): {"heard": 0, "new": 0, "bloomed": 0} for i in range(days - 1, -1, -1)}
        first = {p["phrase"]: _day(p["first_heard"]) for p in plants}
        for e in events:
            d = by_day.get(_day(e["ts"]))
            if d is None:
                continue
            if e["kind"] == "heard":
                d["heard"] += 1
            elif e["kind"] == "bloomed":
                d["bloomed"] += 1
        for day in first.values():
            if day in by_day:
                by_day[day]["new"] += 1

        streak, t = 0, now if _day(now) in active_days else now - 86400  # today not over yet: don't break the streak
        while _day(t) in active_days:
            streak, t = streak + 1, t - 86400

        count = lambda s: sum(p["stage"] == s for p in plants)
        return {
            "plants": plants,
            "totals": {"seed": count("seed"), "sprout": count("sprout"), "bloom": count("bloom"),
                       "phrases": len(plants), "heard": sum(p["heard"] for p in plants)},
            "streak": streak,
            "days": [{"date": d, **v} for d, v in by_day.items()],
            "calls": {"count": calls["n"], "minutes": round((calls["secs"] or 0) / 60), "last": calls["last"], "live": live},
            "recent": recent,
            "thresholds": {"subtitle": SUBTITLE_AT, "bloom": BLOOM_AT},
            "now": now,
        }

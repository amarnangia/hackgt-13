# Steps 2-3 of plan.md: live call audio -> Muse Voice Transcribe -> Muse Spark translation -> overlay.
#   python subtitles.py --out "MacBook Air Speakers"         # live call (see Audio setup in plan.md)
#   python subtitles.py --file samples/telugu_grandma.wav    # no call needed, replays a recording
# Then open http://localhost:8765 for the subtitle overlay.
# The offline Whisper version of this file is in git history (commit d111471).
import argparse
import asyncio
import atexit
import collections
import copy
import difflib
import glob
import http
import json
import mimetypes
import os
import re
import subprocess
import threading
import time
import urllib.parse
import wave
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, TimeoutError, wait

import numpy as np
from websockets.datastructures import Headers
from websockets.http11 import Response

from muse import Translator, transcribe
from decide import is_question, topic_of
from latency import LatencyTracker
from lexicon import Lexicon, indic_share
import origins
from progress import KEEP_AT, Progress
from pronouns import PronounResolver
from roles import Roles
from translate_server import LocalTranslator

PORT = int(os.environ.get("OVERLAY_PORT", 8765))
HERE = os.path.dirname(os.path.abspath(__file__))
CHUNK_MS = 80
SILENCE_WARN_S = 15  # warn if the call has been silent this long
VOICE_SAMPLE = "caller_voice.wav"  # the caller's voice, saved locally (gitignored) and reused next call
MY_VOICE_SAMPLE = "my_voice.wav"    # --outgoing: your own voice, so the English you send sounds like you
SAMPLE_RATE = 48000  # AudioLoop's rate
SENTENCE_END = re.compile(r"[.?!।]+")
CLAUSE_END = re.compile(r"[,;]")
NATIVE_MIN_SHARE = 0.34  # at least a third of the words in Telugu script -> translate and voice it
MIN_CLAUSE_WORDS = 5  # Muse often joins sentences with commas; cut there once a clause is long enough to translate well
MAX_WAIT_WORDS = 20   # run-on speech with no punctuation: translate once this many words are waiting. 12 cut
                      # mid-sentence when Muse left out punctuation and mistranslated; the translator handles long runs fine
HOLD_BACK_WORDS = 3   # ...except the newest few, which Muse may still correct
TRANSLATE_WORKERS = 3
# Live draft captions: while she's still mid-sentence, translate what she's said so far (faded on the overlay), like
# Google's live translation. Telugu puts the verb last, so a draft can change as she goes; the final line replaces
# it. Drafts only run when no real translation is waiting, so they never slow the final English or the voice.
DRAFT_EVERY_S = 0.6
DRAFT_MIN_WORDS = 3
LOCAL_DEADLINE_S = 1.2  # after this, race Muse Spark against the local translator
ECHO_WINDOW_S = 20      # --two-way: a line from your mic matching something played to you this recently is echo
ECHO_MATCH = 0.6
CATCH_UP_S = 12         # --two-way: when the roles are decided or change, translate lines from this long ago again

class Hub:
    """One overlay page's WebSocket clients. --two-way has two: their side on PORT, yours on PORT + 2."""

    def __init__(self):
        self.clients = set()
        self.on_message = None  # handles clicks sent from the overlay
        self.welcome = []  # sent to each page that connects before she starts talking (the next-call starter)
        self.current = {}  # latest message of each kind every new page should get at once (the topic words)

    def broadcast(self, msg):
        data = json.dumps(msg, ensure_ascii=False)
        for c in list(self.clients):
            try:
                c.send(data)
            except Exception:
                self.clients.discard(c)

    def handler(self, conn):
        self.clients.add(conn)
        for msg in list(self.welcome) + list(self.current.values()):
            conn.send(json.dumps(msg, ensure_ascii=False))
        try:
            for message in conn:
                if self.on_message:
                    self.on_message(json.loads(message))
        finally:
            self.clients.discard(conn)


HUB = Hub()     # the one-way app's page; with --two-way, their side (the call -> you)
ME_HUB = Hub()  # --two-way: your side (you -> the call), on PORT + 2 like --outgoing
broadcast = HUB.broadcast


def serve_overlay(conn, request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
        if not origins.allowed(request.headers.get("Origin")):  # another website trying to read the call
            print(f"(refused a connection from {request.headers.get('Origin')})", flush=True)
            return conn.respond(http.HTTPStatus.FORBIDDEN, "Only Weave's own pages can connect.\n")
        return None
    path = urllib.parse.unquote(request.path.split("?")[0])
    for folder in ("images", "calls"):  # pop-up pictures; call story pages, the family dictionary and voice clips
        if path.startswith(f"/{folder}/"):
            file = os.path.realpath(os.path.join(HERE, path.lstrip("/")))
            if not file.startswith(os.path.join(HERE, folder) + os.sep) or not os.path.isfile(file):
                return conn.respond(http.HTTPStatus.NOT_FOUND, "not found")
            body = open(file, "rb").read()
            kind = mimetypes.guess_type(file)[0] or "application/octet-stream"
            if kind.startswith("text/"):
                kind += "; charset=utf-8"
            return Response(http.HTTPStatus.OK, "OK", Headers([("Content-Type", kind), ("Content-Length", str(len(body))),
                                                                ("Cache-Control", "no-cache"), ("Connection", "close")]), body)
    with open(os.path.join(HERE, "overlay.html"), "rb") as f:
        body = f.read()
    # Build the response directly: conn.respond() adds text/plain headers, and setting them again
    # duplicates them, which Chrome rejects ("localhost sent an invalid response").
    return Response(http.HTTPStatus.OK, "OK", Headers([
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Connection", "close"),
    ]), body)


class Captioner:
    """Turns Muse's live partials into sentences and translates each one as soon as it ends.

    Pieces are translated in parallel so a backlog can't build up; the overlay places each result
    by id, so they still show in order.
    """

    def __init__(self, lang, translator="local", keep_at=KEEP_AT, keep_known=True, hub=None, share_with=None, side=None,
                 roles=None):
        """--two-way makes two: side "them" (their voice, to you) and side "me" (yours, to them), sharing the
        translator and word progress (`share_with`), each with its own overlay page (`hub`). `roles` says which
        language each person understands, and so which way each line is translated."""
        self.hub = hub or HUB
        self.side, self.roles = side, roles
        self.audio = None             # the AudioLoop this side plays through (set by listen_two_way)
        self.original_volume = 0.2    # its between-lines volume for a language the listener doesn't know
        self.speaking = False         # between Muse's speechStart and speechEnd
        self.on_speech_start = None   # --two-way: cut the translation playing to this person (they interrupted)
        self.echo_filter = None       # --two-way: callable(text) -> True if it's our speakers, not you
        self.shown = collections.deque(maxlen=30)  # (time, text) this side showed/played, for the other side's echo check
        self.redo_lines = collections.deque(maxlen=12)  # (time, sentence, to, marks): redone if the roles change
        self.translate = None
        if share_with:
            translator = None
            self.translate = share_with.translate
        if translator == "local":
            local = LocalTranslator(lang)
            if local.available():
                self.translate = local
                print("Translating locally with IndicTrans2 (translate_server.py)", flush=True)
            else:
                print("Local translator isn't running (start it with: .venv-translate/bin/python translate_server.py). "
                      "Using Muse Spark instead.", flush=True)
        if self.translate is None:
            self.translate = Translator(lang)
            print("Translating with Muse Spark", flush=True)
        # drafts: their own connection to the local translator, one at a time (off with --no-drafts or on Muse Spark)
        self.drafts = LocalTranslator(lang) if isinstance(self.translate, LocalTranslator) else None
        self.draft_pool = ThreadPoolExecutor(max_workers=1)
        self.draft_busy, self.draft_at, self.draft_src = False, 0.0, ""
        self.finals_waiting = 0  # sentences sent for translation that haven't come back yet
        self.draft_lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS)
        self.race_pool = ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS * 2)  # local vs Muse Spark when slow
        if not share_with:
            for _ in range(TRANSLATE_WORKERS):
                self.pool.submit(self.translate.warm_up)  # the first request pays for TLS setup (~3 s)
        self.next_id = 0
        self.partial = ""  # latest cumulative transcript for the current turn
        self.done = 0      # how many characters of it have been sent for translation
        self.latency = LatencyTracker()
        self.dubber = None                    # set by listen() unless --no-voice
        self.sampler = None                   # collects the caller's voice for cloning
        self.decider = None                   # Laya, set by listen()
        self.pictures = None                  # picture pop-ups (pictures.py), set by listen()
        self.recorder = None                  # the family story keeper (calls.py)
        self.prompter = None                  # live "ask her" prompts (prompts.py)
        self.curious = None                   # the overlay's "Curious?" questions (curious.py), set by listen()
        self.topic, self.topic_votes = None, collections.deque(maxlen=3)  # what the conversation is about now
        self.topic_lock = threading.Lock()
        self.vocab = json.load(open(os.path.join(HERE, "vocab.json"), encoding="utf-8"))["topics"]
        self.recent = collections.deque(maxlen=8)  # (Telugu, English) of her last lines, for answering questions
        self.answers = {}                      # question -> answer, so asking twice doesn't ask the LLM twice
        self.garden = self.garden_call = None  # Weave's garden (garden/garden.db): each Telugu word heard grows a plant
        self.speak_all = False                # --speak all: also voice lines she said (mostly) in English
        self.questions_only = False           # --speak questions: voice only questions/requests to you
        self.lexicon = share_with.lexicon if share_with else Lexicon()
        self.lang = lang
        self.pronouns = PronounResolver(lang)  # తను -> she or he, from who was mentioned before
        self.backup = None  # Muse Spark, created if the local translator fails mid-call
        if share_with:  # one progress file: your known words
            self.progress = share_with.progress
            self.known_at_start, self.heard_at_start = share_with.known_at_start, share_with.heard_at_start
        else:
            self.progress = Progress(self.lexicon, lang, keep_at=keep_at)  # how likely they know each word; known ones stay in Telugu
            self.known_at_start = {i for i in self.progress.entries if self.progress.known(i)}  # for the story page
            self.heard_at_start = dict(self.progress.heard)
        self.keep_known = keep_known  # off for --outgoing: the person you're calling doesn't know Telugu
        self.order_lock = threading.Lock()    # translations finish out of order; the voice must not
        self.next_to_voice, self.finished_lines = 1, {}

    def _plant(self, hits):
        from garden import from_lexicon
        try:
            for entry in hits:
                self.garden.heard(**from_lexicon(entry))
        except Exception as e:  # the garden is a view; never let it stop the call
            print(f"(garden not updated: {type(e).__name__}: {e})", flush=True)

    def on_event(self, ev):
        if self.sampler:
            self.sampler.on_event(ev)
        if self.recorder:
            self.recorder.on_event(ev)
        if self.prompter:
            self.prompter.on_event(ev)
        kind = ev.get("type")
        if kind == "speechStart":
            self.partial, self.done = "", 0
            self.speaking = True
            if self.on_speech_start:
                self.on_speech_start()
            self.latency.new_turn()
            self.hub.broadcast({"type": "speaking"})
        elif kind == "transcript" and not ev.get("final"):
            self.partial = ev["transcript"]
            self.latency.on_partial(self.partial, ev.get("audioProcessedMs"))
            self._pass_through_if_understood()
            self._cut(final=False)
            self.hub.broadcast({"type": "partial", "text": self.partial[self.done:].strip()})
            self._draft()
        elif kind == "speechEnd":
            self.speaking = False
            self._cut(final=True)
            self.hub.broadcast({"type": "partial", "text": ""})

    def _pass_through_if_understood(self):
        """--two-way: while someone speaks the listener's own language, play their real voice at full volume
        (nothing to translate); in the other language keep it low under the translation."""
        if not (self.roles and self.audio):
            return
        text = self.partial[self.done:] or self.partial
        if len(text.split()) < 2:
            return  # too little to tell yet; keep the last setting (people tend to stay in one language)
        lang = "te" if indic_share(text) >= NATIVE_MIN_SHARE else "en"
        self.audio.set_original(1.0 if lang == self.roles.listener_lang(self.side) else self.original_volume)

    def is_echo(self, text):
        """Called on the *other* side's line: does it match something this side just played to its listener?"""
        norm = lambda t: "".join(ch for ch in t.lower() if ch.isalnum())
        if len(text.split()) < 3:
            return False
        now = time.monotonic()
        return any(now - t < ECHO_WINDOW_S and difflib.SequenceMatcher(None, norm(text), norm(shown)).ratio() >= ECHO_MATCH
                   for t, shown in list(self.shown))

    def catch_up(self):
        """The roles were just decided or changed: lines from the last few seconds that went through untranslated
        (the guess was wrong) get translated now, so nothing said early in the call is lost."""
        now = time.monotonic()
        for t, sentence, to, marks in list(self.redo_lines):
            if to is None and now - t < CATCH_UP_S:
                self._submit(sentence, None, marks=marks, redo=True)

    def _draft(self):
        """Translate what she's said of the current sentence so far, if the translator is free."""
        if self.roles and self.roles.listener_lang(self.side) != "en":
            return  # --two-way: drafts are Telugu -> English, only for the English speaker
        rest = self.partial[self.done:].strip()
        now = time.monotonic()
        if (not self.drafts or self.draft_busy or self.finals_waiting or len(rest.split()) < DRAFT_MIN_WORDS
                or rest == self.draft_src or now - self.draft_at < DRAFT_EVERY_S or indic_share(rest) < NATIVE_MIN_SHARE):
            return
        self.draft_busy, self.draft_at, self.draft_src, done = True, now, rest, self.done

        def run():
            try:
                english = self.drafts(rest)
            except Exception:
                english = None
            finally:
                self.draft_busy = False
            if english and self.done == done and not self.finals_waiting:  # still the sentence she's saying
                self.hub.broadcast({"type": "draft", "text": english})
        self.draft_pool.submit(run)

    def _cut(self, final):
        rest = self.partial[self.done:]
        ends = sorted({m.end() for m in SENTENCE_END.finditer(rest)} | {m.end() for m in CLAUSE_END.finditer(rest)})
        if final and rest.strip():
            ends.append(len(rest))
        start = 0
        for end in ends:
            piece = rest[start:end].strip()
            is_sentence = bool(SENTENCE_END.search(piece[-1:])) or end == len(rest) and final
            if not piece or (not is_sentence and len(piece.split()) < MIN_CLAUSE_WORDS):
                continue  # short clause: keep it and send it together with what follows
            self._submit(piece, self.done + end)
            start = end
        self.done += start

        # Run-on speech: don't wait for punctuation that may never come.
        words = list(re.finditer(r"\S+", self.partial[self.done:]))
        if not final and len(words) >= MAX_WAIT_WORDS:
            cut = self.done + words[-HOLD_BACK_WORDS - 1].end()
            self._submit(self.partial[self.done:cut].strip(), cut)
            self.done = cut

    def _submit(self, sentence, end_offset, marks=None, redo=False):
        if not redo and self.echo_filter and self.echo_filter(sentence):
            print(f"  [ignored, it was our own speakers: {sentence}]", flush=True)
            return
        self.next_id += 1
        seg_id = self.next_id
        marks = marks or self.latency.piece_cut(end_offset)
        start_s, end_s = self.recorder.span(marks["audio_ms"]) if self.recorder else (None, None)
        share = indic_share(sentence)
        # english: grandma said it in English, you understood it -> show as-is, no translation, no voice
        # mixed:   mostly English with a Telugu word or two -> translated subtitle, no voice
        # native:  Telugu (or mostly) -> translated subtitle + English voice
        route = "english" if share == 0 else "mixed" if share < NATIVE_MIN_SHARE else "native"
        # `to`: the language this line is translated into for its listener, or None if they understand it as said.
        # --two-way goes by who is listening: Telugu lines to the English speaker, English lines to the Telugu speaker.
        if self.roles:
            if not redo:
                self.roles.heard(self.side, sentence)  # this line may itself settle who speaks what
            to = "en" if self.roles.listener_lang(self.side) == "en" else "te"
            if (to == "en" and route == "english") or (to == "te" and route == "native"):
                to = None
            if redo and to is None:
                return
            self.redo_lines.append((time.monotonic(), sentence, to, marks))
        else:
            to = None if route == "english" else "en"
        self.hub.broadcast({"type": "original", "id": seg_id, "text": sentence, "route": route, "to": to})
        to_translate = self.pronouns(sentence) if to == "en" else sentence  # in order said, so not in work()
        if to:
            with self.draft_lock:
                self.finals_waiting += 1

        def work():
            if to is None:
                english = sentence
            else:
                try:
                    english = self._translate_in_time(to_translate) if to == "en" else self._to_indic(sentence)
                finally:  # (to == "te": Telugu text, despite the name)
                    with self.draft_lock:
                        self.finals_waiting -= 1
            full_english, kept = (sentence if to == "te" else english), []  # Laya and pictures read English
            hits = self.lexicon.find(sentence, self.lang)
            known_before = {h["id"] for h in hits if self.progress.known(h["id"])}  # before counting this hearing
            if self.keep_known and to == "en" and not english.startswith("("):
                # Words the listener knows stay in Telugu ("Today, Ammamma made pulihora"); the rest is English.
                english, kept = self.progress.keep_known_words(english, hits)
                self.progress.heard_words(hits, kept={k["id"] for k in kept})
            if self.garden and to == "en" and hits:
                self._plant(hits)
            self.hub.broadcast({"type": "english", "id": seg_id, "text": english, "route": route, "kept": kept, "to": to})
            self.recent.append((sentence, full_english))
            self.shown.append((time.monotonic(), sentence))
            self.shown.append((time.monotonic(), full_english))
            self.hub.welcome.clear()  # the call is under way; pages opened from now on don't need the starter
            row = self.latency.finished(marks, sentence, english)
            row["route"] = route
            if self.roles:
                row["side"], row["to"] = self.side, to
            usable = self.decider and not english.startswith("(")
            decision = None
            if self.questions_only and usable:
                decision = self.decider(full_english)  # --speak questions needs Laya's request check before voicing
            # Voice first: nothing below changes what gets said, and Laya + the picture lookup (sometimes a web fetch)
            # used to hold the voice back ~0.3-0.6 s. The question rule alone sets its priority (questions keep their
            # place when the voice is behind); Laya's request check still labels the line for cards and prompts.
            quick = decision or {"intent": "question" if is_question(full_english) else "statement",
                                 "needs_attention": is_question(full_english)}
            with self.order_lock:
                self.finished_lines[seg_id] = (english, marks, row, quick, route, to)
                while self.next_to_voice in self.finished_lines:
                    self._voice(self.next_to_voice, *self.finished_lines.pop(self.next_to_voice))
                    self.next_to_voice += 1
            # Then the extras, while the English is already playing.
            if decision is None and usable:
                decision = self.decider(full_english)
            self.hub.broadcast({"type": "details", "id": seg_id,
                                "intent": decision["intent"] if decision else None, "cards": self._cards(sentence, decision)})
            topic, _ = topic_of(full_english, hits, decision.get("topic") if decision else None)
            self._follow_topic(topic)
            # Pictures and Curious? questions help the English speaker with Telugu, so not on lines to the Telugu speaker.
            picture = self._picture(seg_id, hits, full_english, known_before) if to != "te" else None
            if self.curious and to != "te" and not english.startswith("("):
                try:
                    questions = self.curious.for_line(full_english, hits if route != "english" else [], picture,
                                                      decision["intent"] if decision else None, known_before)
                except Exception as e:
                    print(f"(Curious? questions failed: {type(e).__name__}: {e})", flush=True)
                    questions = []
                if questions:
                    self.hub.broadcast({"type": "curious", "line": seg_id, "questions": questions})
            if self.prompter and route != "english":
                import topics
                self.prompter.offer(topics.about(hits, picture, self.lexicon.entries.get(self.lang)))
            row["laya"] = decision["seconds"] if decision else None
            intent = decision["intent"] if decision else None
            if self.recorder:
                self.recorder.add_line(id=seg_id, telugu=sentence, english=english, english_full=full_english, route=route,
                                       kept=kept, intent=intent, picture=picture, start_s=start_s, end_s=end_s)
            if self.prompter and route != "english":
                self.prompter.on_line(sentence, full_english, intent, route)

        def work_logged():
            try:
                work()
            except Exception:
                import traceback
                traceback.print_exc()  # thread-pool errors are otherwise silent

        self.pool.submit(work_logged)

    def _translate_in_time(self, sentence):
        """Local translation normally takes ~0.3 s, but when the Mac is short on memory it can take ~10 s.
        If it hasn't answered in LOCAL_DEADLINE_S, also ask Muse Spark and use whichever answers first."""
        local = self.race_pool.submit(self.translate, sentence)
        try:
            return local.result(timeout=LOCAL_DEADLINE_S)
        except TimeoutError:
            pass
        except Exception as e:
            return self._fallback_translate(sentence, e)
        if isinstance(self.translate, Translator):
            return local.result()  # already on Muse Spark; nothing faster to try
        if self.backup is None:
            self.backup = Translator(self.lang)
        remote = self.race_pool.submit(self.backup, sentence)
        done, _ = wait([local, remote], return_when=FIRST_COMPLETED)
        for f in done:
            if not f.exception():
                if f is remote:
                    print("(local translator slow; used Muse Spark for this line)", flush=True)
                return f.result()
        try:
            return (remote if local in done else local).result()
        except Exception as e:
            return f"(translation failed: {type(e).__name__})"

    def _picture(self, seg_id, hits, english, known_before):
        """Pop up a picture of the thing in this line the grandkid most likely doesn't know (Laya picks).
        Words they knew before this line don't need one (so: a picture on first mention, the Telugu word after)."""
        if not self.pictures or english.startswith("("):
            return None
        try:
            key = self.pictures.pick(english, hits, known=lambda lexicon_id: lexicon_id in known_before)
            card = self.pictures.card(key) if key else None
        except Exception as e:
            print(f"Picture lookup failed: {type(e).__name__}: {e}", flush=True)
            return None
        if card:
            for entry in hits if self.keep_known else []:  # seeing its picture helps them learn the word
                if entry["id"] in card.get("lexicon_ids", []):
                    self.progress.observe(entry["id"], "picture")
            # "id" is the picture's own id (Weave looks it up in the library); "line" says which line it belongs to
            self.hub.broadcast({"type": "picture", **card, "line": seg_id})
            print(f"  [picture: {card['name']}]", flush=True)
        return card

    def _to_indic(self, sentence):
        """English -> Telugu for the Telugu speaker (--two-way; local translator only)."""
        try:
            return self.translate.to_indic(sentence)
        except Exception as e:
            return f"(translation failed: {type(e).__name__})"

    def _fallback_translate(self, sentence, error):
        """The local translator died mid-call (e.g. its process was stopped): use Muse Spark for this line."""
        if isinstance(self.translate, Translator):
            return f"(translation failed: {type(error).__name__})"
        if self.backup is None:
            print(f"Local translator failed ({type(error).__name__}); using Muse Spark until it's back.", flush=True)
            self.backup = Translator(self.lang)
        try:
            return self.backup(sentence)
        except Exception as e:
            return f"(translation failed: {type(e).__name__})"

    def _follow_topic(self, topic):
        """Move the overlay's topic words once the same topic wins 2 of the last 3 lines (so they don't flicker)."""
        if not topic:
            return
        with self.topic_lock:
            self.topic_votes.append(topic)
            if topic == self.topic or self.topic_votes.count(topic) < 2:
                return
        self.show_topic(topic)

    def show_topic(self, topic):
        """Send the words for `topic`: word-list words of this topic she has used that they're still learning
        (progress.py), then phrases they can say (vocab.json)."""
        self.topic = topic
        learning = []
        for e in self.lexicon.entries.get(self.lang, []):
            p = self.progress.probability(e["id"])
            if e.get("topic") == topic and e.get("roman") and self.progress.heard.get(e["id"]) and 0.2 <= p < KEEP_AT:
                learning.append((p, {"id": e["id"], "telugu": e["forms"][0].strip(" ,.^"), "roman": e["roman"].strip(" ,"),
                                     "english": e.get("translate_as") or (e.get("match_english") or [""])[0],
                                     "p": round(p, 2), "learning": True}))
        words = [w for _, w in sorted(learning, key=lambda x: -x[0])[:4]]
        have = {w["roman"].lower().strip("?") for w in words}
        words += [w for w in self.vocab[topic]["words"] if w["roman"].lower().strip("?") not in have]
        msg = {"type": "topic", "topic": self.vocab[topic]["name"], "key": topic, "words": words}
        self.hub.current["topic"] = msg
        self.hub.broadcast(msg)
        print(f"  [topic: {self.vocab[topic]['name']}]", flush=True)

    def answer(self, question, caller):
        """Answer a "Curious?" question the word list can't, with Muse Spark and her last few lines as context."""
        if question in self.answers:
            return self.answers[question]
        from muse import spark_json
        said = "\n".join(f"{te}  =  {en}" for te, en in self.recent) or "(nothing yet)"
        a = spark_json(
            f"You help a grandchild raised in the US (beginner Telugu) understand their Telugu-speaking grandparent "
            f"({caller}) during a live call. Answer the grandchild's question in 2-3 short, warm, simple sentences, using "
            "what was said on the call for context. If the answer is about a Telugu word or phrase, include it; anything the "
            "grandchild could say to the grandparent must use the respectful form (meeru, mimmalni). Keys: "
            '"text" (the answer in English), "telugu" (the key Telugu word or phrase in Telugu script, or ""), '
            '"roman" (how to say it in English letters, or "").',
            f"The call so far:\n{said}\n\nQuestion: {question}", model="muse-spark-1.1", effort="minimal", timeout=10)
        if a and a.get("text"):
            self.answers[question] = a
        return a

    def _cards(self, sentence, decision):
        """Word-list matches in what grandma said (exact), else Laya's category guess for the English line."""
        # Titled with her word (romanized), or a proverb in her own words, not our internal id ("Noru Manchidaite")
        title = lambda e: (e.get("roman") or (e["forms"][0] if e["category"] == "idiom" else e["id"].replace("_", " ").title())).strip(" ,^")
        cards = [{"id": e["id"], "title": title(e), "category": e["category"], "note": e.get("note", ""),
                  "telugu": e["forms"][0].strip(" ,.^"), "english": e.get("translate_as") or (e.get("match_english") or [""])[0],
                  "p": round(self.progress.probability(e["id"]), 2)}  # how likely they know it (progress.py)
                 for e in self.lexicon.find(sentence, self.lang)]
        cards += [{"id": e["id"], "title": e["id"].replace("_", " ").title(), "category": e["category"],
                   "note": e.get("note", "")} for e in self.lexicon.find(sentence, "en")]  # English slang she used
        seen = set()  # two list entries for the same word (ఊరు as "village" and as "hometown"): one card
        cards = [c for c in cards if not (c["title"].lower() in seen or seen.add(c["title"].lower()))]
        if decision and decision["category"] != "none" and not any(c["category"] == decision["category"] for c in cards):
            cards.append({"id": None, "title": decision["category"].title(), "category": decision["category"], "note": ""})
        return cards

    def _voice(self, seg_id, english, marks, row, decision, route, to):
        """Voice Telugu lines (in order). Questions/requests to you keep their place when the voice is behind."""
        def on_start():
            self.latency.voice_started(row, marks)
            self.hub.broadcast({"type": "voice", "id": seg_id})
        asks = bool(decision and decision["needs_attention"])
        if self.roles:  # --two-way: say the translation; a line the listener already understood plays as it was
            if not to:
                voiced, why = False, "they understand it as said"
            elif not self.dubber:
                voiced, why = False, ""
            else:
                voiced = self.dubber.say(english, spoken_at=marks["spoken"], on_start=on_start, priority=asks, lang=to)
                why = "" if voiced else "voice was behind"
        elif route != "native" and not self.speak_all:
            voiced, why = False, "she said it in English" if route == "english" else "mostly English"
        elif self.questions_only and not asks:
            voiced, why = False, "statement (--speak questions)"
        elif not self.dubber:
            voiced, why = False, ""
        else:
            voiced = self.dubber.say(english, spoken_at=marks["spoken"], on_start=on_start, priority=asks)
            why = "" if voiced else "voice was behind"
        if not voiced:
            self.latency.log_row(row)
        tag = f"  [voice{': ' + decision['intent'] if asks else ''}]" if voiced else (f"  [no voice: {why}]" if why else "")
        who = {"them": "them -> you ", "me": "you -> them "}.get(self.side, "")
        print(f"{who}{LatencyTracker.line(row)} {row['text']}  ->  {english}{tag}", flush=True)


def load_recording(path):
    """A 16/24/48 kHz mono 16-bit wav as 48 kHz float32, to play through AudioLoop like a call."""
    with wave.open(path) as w:
        rate = w.getframerate()
        assert w.getnchannels() == 1 and w.getsampwidth() == 2, "file must be mono 16-bit wav"
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = int(len(audio) * SAMPLE_RATE / rate)
    return np.interp(np.arange(n) * rate / SAMPLE_RATE, np.arange(len(audio)), audio).astype(np.float32)


def prepare_voice_sample(args):
    """The caller's voice clip to clone: --voice-sample (any audio file, e.g. a WhatsApp voice note), else the one
    saved from the last call, else None (learn it during this call)."""
    if args.voice_sample:
        # Trim silences and even out the volume; 30 s matched the speaker's pitch better than 15 s at the same speed.
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", args.voice_sample, "-af",
                        "silenceremove=start_periods=1:start_threshold=-40dB:stop_periods=-1:stop_duration=0.6:"
                        "stop_threshold=-40dB,loudnorm", "-ac", "1", "-ar", "24000", "-t", "30", args.voice_file], check=True)
        return args.voice_file
    if args.new_voice and os.path.exists(args.voice_file):
        os.remove(args.voice_file)
    return args.voice_file if os.path.exists(args.voice_file) else None


def make_audio(args, loop, target):
    """Set up AudioLoop to play the call (or --file recording) through AudioLoop and copy it to Muse as 24 kHz 16-bit PCM.

    `target["q"]` is the queue of the current Muse session; it is swapped on reconnect. The latency clock
    starts when the first frame of a session is captured (frames queue up while Muse connects).
    """
    import sounddevice as sd
    from audio_loop import AudioLoop, check_volume, find_device

    source = load_recording(args.file) if args.file else None
    in_dev = None if args.file else find_device(args.inp, "input")
    if args.out == "none":
        out_dev = None  # silent, for tests; only works with --file
    else:
        out_dev = find_device(args.out, "output") if args.out else sd.default.device[1]
        out_name = sd.query_devices(out_dev)["name"]
        if args.outgoing and "BlackHole" not in out_name:
            raise SystemExit(f"--outgoing sends the English to {out_name!r}, but it should go to a virtual mic. "
                             "Install one with: brew install --cask blackhole-16ch")
        if args.outgoing and out_name == sd.query_devices(sd.default.device[1])["name"]:
            raise SystemExit(f"The Mac's sound output is {out_name}, the device the English goes into, so the call would "
                             "hear itself. Set System Settings > Sound > Output to BlackHole 2ch (or your speakers/headphones); "
                             f"pick {out_name} only as Chrome's microphone (chrome://settings/content/microphone).")
        if not args.outgoing and "BlackHole" in out_name:
            raise SystemExit("Output is BlackHole, so you'd hear nothing (and a live call would feed back into itself). "
                             'Pass --out "MacBook Air Speakers" or your headphones.')
    if not args.file and not args.outgoing:
        check_volume()
    buf = []

    def on_audio(mono48k):
        # 48 kHz -> 24 kHz by averaging pairs; batch 10 ms blocks into 80 ms frames.
        buf.append((mono48k.reshape(-1, 2).mean(axis=1) * 32767).clip(-32768, 32767).astype(np.int16))
        if len(buf) * 10 >= CHUNK_MS:
            pcm = np.concatenate(buf)
            buf.clear()
            sampler = target.get("sampler")
            recorder = target.get("recorder")
            if target.get("fresh"):
                target["fresh"] = False
                target["latency"].audio_started(time.monotonic() - CHUNK_MS / 1000)  # frame start, not end
                if sampler:
                    sampler.new_session()
                if recorder:
                    recorder.new_session()
            if sampler:
                sampler.add_frame(pcm)  # same audio Muse hears, to clone the caller's voice
            if recorder:
                recorder.add_frame(pcm)  # her side of the call, for the story page
            try:
                loop.call_soon_threadsafe(target["q"].put_nowait, pcm.tobytes())
            except RuntimeError:
                pass  # the app is shutting down (event loop closed) but the audio device is still delivering

    # The original voice (theirs, or yours with --outgoing) stays low so the English leads, and drops further while
    # an English line plays. Not silent in between: waiting for the end of a sentence in silence felt like lag.
    return AudioLoop(in_dev, out_dev, on_audio=on_audio, source=source,
                     original=args.original_volume, duck=args.duck_volume)


async def run(args):
    if args.reset_progress and os.path.exists("progress.json"):
        os.remove("progress.json")
    if args.two_way:
        return await run_two_way(args)
    captioner = Captioner(args.lang, args.translator, args.keep_at, keep_known=not args.outgoing)
    if args.no_drafts:
        captioner.drafts = None
    HUB.on_message = make_on_message(captioner, args, HUB)
    try:
        await listen(args, captioner)
    finally:  # also on Ctrl+C
        print("\n" + captioner.latency.summary() + "\n(per-sentence log: latency_log.jsonl)", flush=True)
        end_call(captioner, args)


def make_on_message(captioner, args, hub):
    """Clicks from an overlay page: questions about words, practice, "didn't know it"."""
    def on_message(msg):
        kind, wid = msg.get("type"), msg.get("id")
        words = {e["id"]: e for e in captioner.lexicon.entries.get(captioner.lang, [])}
        entry = words.get(msg.get("word")) or words.get(wid) if wid else None
        if kind == "ask" and entry:
            # "What does ___ mean?" from the overlay: strong evidence they don't know it yet, then the answer teaches it.
            # Word-list words are answered at once from the list's note.
            captioner.progress.observe(entry["id"], "asked")
            hub.broadcast({"type": "answer", "id": wid, "text": entry.get("note") or entry.get("translate_as", ""),
                           "telugu": entry["forms"][0].strip(" ,.^"), "roman": (entry.get("roman") or "").strip(" ,")})
            captioner.progress.observe(entry["id"], "answer")
        elif kind == "ask" and wid and msg.get("text") and not wid.startswith("reply:"):  # replies come with their answer
            def reply():  # anything else: Muse Spark, with the call so far (~1-2 s), off the WebSocket thread
                a = captioner.answer(msg["text"], args.caller)
                hub.broadcast({"type": "answer", "id": wid, "text": (a or {}).get("text") or "Couldn't look that up right now.",
                               "telugu": (a or {}).get("telugu", ""), "roman": (a or {}).get("roman", "")})
            threading.Thread(target=reply, daemon=True).start()
        elif kind == "practiced" and entry:
            captioner.progress.observe(wid, "practiced")
        if kind == "forget" and wid:
            captioner.progress.forget(wid)
            if captioner.garden and entry:
                from garden import from_lexicon
                captioner.garden.asked(from_lexicon(entry)["phrase"])  # the "?" in the garden: it gets more help again
            print(f"Marked '{msg['id']}' as not known; it will be translated again.", flush=True)
    return on_message


def end_call(captioner, args):
    captioner.pool.shutdown(wait=True)  # the last lines count too
    captioner.progress.finish()  # words still showing in Telugu, untapped: understood
    if captioner.garden_call:
        captioner.garden_call.__exit__(None, None, None)  # Weave's garden: no longer "on a call"
    finish_call(captioner, args)


def watch_call_audio(audio, args):
    """Say so, in the terminal and on the overlay, when the call's sound isn't reaching the app. Otherwise a call can
    run to the end with nothing picked up and only "nothing was said" to show for it."""
    import sounddevice as sd

    warned_silent = warned_volume = False
    while True:
        time.sleep(3)
        quiet_for = time.monotonic() - audio.last_sound
        if quiet_for > SILENCE_WARN_S and not warned_silent:
            warned_silent = True
            msg = (f"No sound from the call for {quiet_for:.0f} s. If she's talking: the Mac's output should be BlackHole 2ch "
                   "at 100%, and in the WhatsApp Web call (⋯ > Settings) the speaker should be Default or BlackHole 2ch, "
                   "not the MacBook speakers. Test with: python tools/blackhole_check.py 15")
            print("\n⚠️  " + msg, flush=True)
            broadcast({"type": "warning", "text": msg})
        elif quiet_for < 1:
            warned_silent = False
        if not args.outgoing and "BlackHole" in sd.query_devices(sd.default.device[1])["name"]:
            vol = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                                 capture_output=True, text=True).stdout.strip()
            if vol.isdigit() and int(vol) < 100 and not warned_volume:
                warned_volume = True
                msg = (f"The Mac volume is {vol}%. While BlackHole is the output, the volume keys turn down the call going "
                       "into the app, not your speakers. Set it back to 100%.")
                print("\n⚠️  " + msg, flush=True)
                broadcast({"type": "warning", "text": msg})
            elif vol == "100":
                warned_volume = False


def next_call_starter(caller, this_call=None):
    """A question from the last call's story page ("questions for next time"), as an "ask her" prompt."""
    from calls import CALLS_DIR
    for f in sorted(glob.glob(os.path.join(CALLS_DIR, "*", "call.json")), reverse=True):
        try:
            call = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        story = call.get("story") or {}
        if call.get("id") == this_call or call.get("caller", "").lower() != caller.lower() or not story.get("questions"):
            continue
        q = story["questions"][0]
        if q.get("telugu") and q.get("roman"):
            return {"type": "prompt", "caller": caller, "telugu": q["telugu"], "roman": q["roman"], "english": q.get("english", ""),
                    "context": f"Last call: {story.get('title') or 'your last call'}"}
    return None


def finish_call(captioner, args):
    """Turn the call into its story page and update the family dictionary."""
    if not captioner.recorder:
        return
    captioner.pool.shutdown(wait=True)  # the last lines must be translated before the page is written
    print("Writing the family story page for this call...", flush=True)
    page = captioner.recorder.finish(captioner.known_at_start, captioner.heard_at_start, captioner.progress,
                                     captioner.lexicon, args.lang)
    if not page:
        print("(nothing was said, so no story page)", flush=True)
        return
    print(f"Story page:        {page}\nFamily dictionary: {os.path.normpath(os.path.join(os.path.dirname(page), os.pardir, 'dictionary.html'))}", flush=True)
    if not args.no_open:
        subprocess.run(["open", page], check=False)


async def load_helpers(loop, args, captioner, target):
    """Laya, pictures, the story keeper, Weave's garden and 'ask her' prompts, attached to `captioner`."""
    print("Loading Laya...", flush=True)
    from decide import Decider
    captioner.decider = await loop.run_in_executor(None, Decider)
    from pictures import PictureFinder
    captioner.pictures = PictureFinder(captioner.decider)
    await loop.run_in_executor(None, captioner.pictures._nouns, "warm up the noun finder")
    if not args.no_story:
        from calls import CallRecorder
        target["recorder"] = captioner.recorder = CallRecorder(args.caller, record_audio=not args.no_record)
        print(f"Keeping this call's story in calls/{captioner.recorder.id}/"
              + ("" if not args.no_record else " (no audio: --no-record)"), flush=True)
    if not args.outgoing:  # Weave's garden grows from her Telugu (python -m garden shows it)
        from garden import Garden
        captioner.garden = Garden()
        captioner.garden_call = captioner.garden.call(key=captioner.recorder.id if captioner.recorder else None)
        captioner.garden_call.__enter__()
    if not args.no_prompts:
        from prompts import StoryPrompter

        def on_prompt(q):
            captioner.hub.broadcast({"type": "prompt", "caller": args.caller, **q})
            if captioner.recorder:
                captioner.recorder.add_prompt(q)
            print(f"  [ask {args.caller}: {q['roman']}  ({q['english']})]", flush=True)
        captioner.prompter = StoryPrompter(captioner.decider, args.caller, on_prompt, cooldown_s=args.prompt_every)
        starter = next_call_starter(args.caller, captioner.recorder.id if captioner.recorder else None)
        if starter:  # a question the last call's story suggested, to open this one with
            captioner.hub.welcome.append(starter)
            captioner.hub.broadcast(starter)
            print(f"  [to start: ask {args.caller}: {starter['roman']}  ({starter['english']})]", flush=True)
    if not args.outgoing:
        from curious import Curious
        captioner.curious = Curious(captioner.decider, captioner.progress, captioner.progress.keep_at)
    if not args.outgoing:
        captioner.show_topic("greetings")  # calls start with hello; the words follow the conversation from there


async def load_voice(loop, args, captioner, audio, target, who, indic_voice=None):
    """The English voice for this side (cloned from `who` once we have their speech), plus Telugu if given."""
    from dub import Dubber, VoiceSampler
    sample = prepare_voice_sample(args)
    clone = args.voice == "clone"
    captioner.dubber = await loop.run_in_executor(
        None, lambda: Dubber(audio.voice, clone=clone, voice_sample=sample, indic_voice=indic_voice))
    if clone and captioner.dubber.cloning:
        print(f"English voice: {who}voice from {sample}. (--new-voice to relearn it on this call)", flush=True)
    elif clone:
        print(f"English voice: stock voice until {who}voice is learned (~10 s of speech).", flush=True)
        target["sampler"] = captioner.sampler = VoiceSampler(args.voice_file, captioner.dubber.use_voice_sample)


async def wait_for_audio(target, what="the input device"):
    # Connect to Muse only once audio is actually flowing; a silent gap right after connecting makes it hang up.
    for _ in range(50):
        if not target["q"].empty():
            return
        await asyncio.sleep(0.1)
    print(f"No audio is arriving from {what} after 5 s. Check that the terminal has microphone "
          "permission (System Settings > Privacy & Security > Microphone).", flush=True)


async def stream(loop, args, captioner, audio, target):
    """Feed the audio to Muse and its events to `captioner`, reconnecting if the connection drops.
    With --file, returns once the recording has been transcribed and translated."""
    failures = 0
    while True:
        audio_q = target["q"] = asyncio.Queue()
        target["fresh"] = True
        if args.file:
            async def end_of_file():  # 1 s of silence after the recording, then close the Muse stream
                await loop.run_in_executor(None, audio.source_done.wait)
                audio_q.put_nowait(None)
            ender = asyncio.create_task(end_of_file())
        try:
            async for ev in transcribe(audio_q, args.lang, "PCM_24KHZ"):
                if failures:
                    print("Reconnected to Muse.", flush=True)
                    failures = 0
                captioner.on_event(ev)
        except Exception as e:
            if args.file:
                raise
            failures += 1
            offline = "nodename nor servname" in str(e) or "Temporary failure in name resolution" in str(e)
            if failures == 1:
                print(f"Muse connection dropped ({e}); reconnecting...", flush=True)
            elif offline and failures == 2:
                print("No internet (can't reach Muse). Waiting for the Wi-Fi to come back...", flush=True)
            await asyncio.sleep(min(0.2 * 2 ** (failures - 1), 3.0))  # 0.2, 0.4, ... up to 3 s between tries
            continue
        if args.file:
            await ender
            await loop.run_in_executor(None, lambda: captioner.pool.shutdown(wait=True))  # last translations
            return


async def finish_voice(captioner, audio):
    while captioner.dubber and (captioner.dubber.behind() > 0 or audio.voice.active()):
        await asyncio.sleep(0.2)  # let the last line finish speaking


async def listen(args, captioner):
    loop = asyncio.get_running_loop()
    target = {"q": asyncio.Queue(), "latency": captioner.latency}
    audio = make_audio(args, loop, target)
    await load_helpers(loop, args, captioner, target)
    captioner.speak_all = args.speak == "all"
    captioner.questions_only = args.speak == "questions"
    if not args.no_voice:  # load before audio starts, or the first seconds of the call are lost
        print("Loading the English voice (Kokoro)...", flush=True)
        await load_voice(loop, args, captioner, audio, target, "your " if args.outgoing else "the caller's ")
    threading.Thread(target=audio.run, kwargs={"meter": False}, daemon=True).start()
    if not args.file:
        threading.Thread(target=watch_call_audio, args=(audio, args), daemon=True).start()
    await wait_for_audio(target)
    await stream(loop, args, captioner, audio, target)
    if args.file:
        await finish_voice(captioner, audio)
        await asyncio.sleep(0.3)
        audio.stop.set()


def side_args(args, side):
    """--two-way runs the one-way app twice in one process: "them" is the normal direction (the call -> you), "me"
    is --outgoing (your mic -> the call)."""
    a = copy.copy(args)
    if side == "them":
        a.outgoing, a.voice_file = False, VOICE_SAMPLE
        a.inp = args.inp or "BlackHole 2ch"
    else:
        a.outgoing, a.voice_file, a.voice_sample = True, MY_VOICE_SAMPLE, None
        a.inp, a.file = args.my_in or "MacBook", args.my_file
        a.out = "none" if args.out == "none" else (args.my_out or "BlackHole 16ch")
        a.new_voice = False
    return a


def with_language_choice(on_message, roles):
    """The overlay's "I speak English / Telugu" switch sets the roles; everything else goes to `on_message`."""
    def handle(msg):
        if msg.get("type") == "i_speak" and msg.get("lang") in ("en", "te"):
            roles.set("them" if msg["lang"] == "en" else "me", f"you picked {'English' if msg['lang'] == 'en' else 'Telugu'} in Weave")
        else:
            on_message(msg)
    return handle


async def run_two_way(args):
    them_args, me_args = side_args(args, "them"), side_args(args, "me")
    hubs = {"them": HUB, "me": ME_HUB}

    def on_roles(telugu, why):
        english = "them" if telugu == "me" else "me"
        print(f"Roles {why} -> {'you' if telugu == 'me' else args.caller} speak{'s' if telugu == 'them' else ''} Telugu, "
              f"{'you' if english == 'me' else args.caller} English", flush=True)
        for hub in hubs.values():
            hub.current["roles"] = msg = {"type": "roles", "you": roles.lang_of("me"), "them": roles.lang_of("them"),
                                          "fixed": roles.fixed}
            hub.broadcast(msg)
        for c in (them, me):
            c.catch_up()
    fixed = None if args.telugu_speaker == "auto" else args.telugu_speaker
    roles = Roles(fixed=fixed, default="me", on_change=on_roles)
    them = Captioner(args.lang, args.translator, args.keep_at, hub=HUB, side="them", roles=roles)
    # Words kept in Telugu follow *your* progress, so only for what you hear, never in what goes to them.
    me = Captioner(args.lang, args.translator, args.keep_at, keep_known=False, hub=ME_HUB, share_with=them,
                   side="me", roles=roles)
    for c in (them, me):
        c.original_volume = args.original_volume
        if args.no_drafts:
            c.drafts = None
        c.hub.on_message = with_language_choice(make_on_message(them, args, c.hub), roles)
    for hub in hubs.values():  # pages that connect get the current roles, so the overlay's "I speak" switch shows it
        hub.current["roles"] = {"type": "roles", "you": roles.lang_of("me"), "them": roles.lang_of("them"), "fixed": roles.fixed}
    print(f"Roles to start: {'you speak Telugu, they speak English' if roles.telugu == 'me' else 'they speak Telugu, you speak English'}"
          + (" (fixed by --telugu-speaker)" if fixed else " (until the call shows otherwise)"), flush=True)
    try:
        await listen_two_way(args, them_args, me_args, them, me)
    finally:  # also on Ctrl+C
        for c, name in ((them, "them -> you"), (me, "you -> them")):
            print(f"\n{name}:\n" + c.latency.summary(), flush=True)
        print("(per-sentence log: latency_log.jsonl)", flush=True)
        me.pool.shutdown(wait=True)
        end_call(them, args)


async def listen_two_way(args, them_args, me_args, them, me):
    loop = asyncio.get_running_loop()
    import sounddevice as sd
    them_target = {"q": asyncio.Queue(), "latency": them.latency}
    me_target = {"q": asyncio.Queue(), "latency": me.latency}
    them_audio = make_audio(them_args, loop, them_target)  # the call -> your headphones/speakers
    me_audio = make_audio(me_args, loop, me_target)        # your mic -> BlackHole 16ch -> the call
    them.audio, me.audio = them_audio, me_audio

    # Walkie-talkie: on the laptop speakers your mic hears everything we play you, so while they're making sound
    # your mic counts as silent. With headphones you can talk over anything.
    out_name = sd.query_devices(them_audio.out_dev)["name"] if them_audio.out_dev is not None else ""
    walkie = args.walkie == "on" or (args.walkie == "auto" and "speaker" in out_name.lower())
    if walkie:
        me_audio.gate = lambda: them_audio.sounding(0.4)
        print(f"Walkie-talkie mode ({out_name}): your mic is ignored while anything plays to you, so wait for it to "
              "finish before you talk. Headphones let you talk freely.", flush=True)
    me.echo_filter = them.is_echo  # a line from your mic that matches what just played to you is our speakers

    # Turn-taking: never play a translation to someone while they're talking, and if they start talking while one
    # is playing to them, fade it out (the subtitle stays).
    them_audio.hold = lambda: me.speaking   # to you: wait while you talk
    me_audio.hold = lambda: them.speaking   # to them: wait while they talk

    def interrupted(audio, captioner, who, whom):
        def cut():
            if audio.voice.playing():
                audio.voice.fade_out()
                if captioner.dubber:
                    captioner.dubber.cancel()
                print(f"  [{who} started talking: faded out the translation playing to {whom}]", flush=True)
        return cut
    me.on_speech_start = interrupted(them_audio, them, "you", "you")
    them.on_speech_start = interrupted(me_audio, me, "they", "them")

    if args.record_out:
        record_outputs(args.record_out, them_audio, me_audio)

    print("Loading English -> Telugu and the Telugu voice...", flush=True)
    error = await loop.run_in_executor(None, them.translate.load_two_way) if hasattr(them.translate, "load_two_way") \
        else "the local translator isn't running"
    if error:
        print(f"English -> Telugu isn't available ({error}); English lines to the Telugu speaker will be subtitles "
              "only.", flush=True)
    indic_voice = None if error else them.translate.speak
    await load_helpers(loop, args, them, them_target)  # story page, prompts: about the person you called
    me.decider, me.pictures = them.decider, them.pictures
    if not args.no_voice:
        print("Loading the voices...", flush=True)
        await load_voice(loop, them_args, them, them_audio, them_target, "the caller's ", indic_voice)
        await load_voice(loop, me_args, me, me_audio, me_target, "your ", indic_voice)
    for audio in (them_audio, me_audio):
        threading.Thread(target=audio.run, kwargs={"meter": False}, daemon=True).start()
    if not args.file:
        threading.Thread(target=watch_call_audio, args=(them_audio, them_args), daemon=True).start()
    await wait_for_audio(them_target, "the call (BlackHole 2ch)")
    await wait_for_audio(me_target, "your mic")
    print("Two-way translation is live. Ctrl+C to stop.", flush=True)
    await asyncio.gather(stream(loop, them_args, them, them_audio, them_target),
                         stream(loop, me_args, me, me_audio, me_target))
    if args.file:  # tests: both recordings done
        await finish_voice(them, them_audio)
        await finish_voice(me, me_audio)
        await asyncio.sleep(0.3)
        them_audio.stop.set()
        me_audio.stop.set()
        await asyncio.sleep(0.2)
        if args.record_out:
            write_recordings(args.record_out)


RECORDINGS = {}


def record_outputs(folder, them_audio, me_audio):
    """Tests: keep what each person hears (mix) and the translation alone (voice), plus when it was, to check timing."""
    for name, audio in (("to_you", them_audio), ("to_them", me_audio)):
        RECORDINGS[name] = {"mix": [], "voice": []}

        def tap(mix, voice, rec=RECORDINGS[name]):
            rec["mix"].append(mix.copy())
            rec["voice"].append(voice.copy())
        audio.on_output = tap


def write_recordings(folder):
    import soundfile as sf
    os.makedirs(folder, exist_ok=True)
    for name, rec in RECORDINGS.items():
        for kind, blocks in rec.items():
            if blocks:
                sf.write(os.path.join(folder, f"{name}_{kind}.wav"), np.concatenate(blocks), SAMPLE_RATE)
    print(f"Recorded what each side heard in {folder}/", flush=True)


def start_translator(lang):
    """Start translate_server.py in its own virtualenv unless it's already running; stop it when we exit."""
    if LocalTranslator(lang).available():
        return  # already running, e.g. in another terminal
    python = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv-translate", "bin", "python")
    if not os.path.exists(python):
        print("No .venv-translate yet (see Setup in plan.md), so translation will use Muse Spark.", flush=True)
        return
    log = open("translate_server.log", "w")
    proc = subprocess.Popen([python, "translate_server.py"], stdout=log, stderr=subprocess.STDOUT,
                            env={**os.environ, "HF_HUB_DISABLE_PROGRESS_BARS": "1"})
    atexit.register(proc.terminate)
    print("Starting the local translator (the first run downloads ~4 GB)...", end="", flush=True)
    while not LocalTranslator(lang).available():
        if proc.poll() is not None:
            print(" it crashed; see translate_server.log. Using Muse Spark instead.", flush=True)
            return
        time.sleep(1)
        print(".", end="", flush=True)
    print(" ready.", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lang", default="te", help="language code: te (Telugu), hi (Hindi), ta, kn, ml, bn, mr")
    p.add_argument("--translator", choices=["local", "muse"], default="local",
                   help="local = IndicTrans2 via translate_server.py (fast, same output every time); muse = Muse Spark")
    p.add_argument("--file", help="replay a 16/24 kHz mono wav instead of listening to the call")
    p.add_argument("--outgoing", action="store_true",
                   help="translate what YOU say: your mic -> English voice -> BlackHole 16ch, which WhatsApp Web uses "
                        "as its microphone, so the other person hears only the English")
    p.add_argument("--two-way", action="store_true",
                   help="translate both ways in one call: the Telugu speaker hears everything in Telugu and the English "
                        "speaker in English (needs Mac output = BlackHole 2ch and WhatsApp's mic = BlackHole 16ch)")
    p.add_argument("--telugu-speaker", choices=["auto", "me", "them"], default="auto",
                   help="--two-way: who speaks Telugu (auto: assume you, then go by who speaks more Telugu)")
    p.add_argument("--walkie", choices=["auto", "on", "off"], default="auto",
                   help="--two-way: ignore your mic while anything plays to you (auto: when --out is the laptop speakers)")
    p.add_argument("--my-in", help="--two-way: your microphone (default: the MacBook's)")
    p.add_argument("--my-out", help="--two-way: where your side goes (default: BlackHole 16ch)")
    p.add_argument("--my-file", help="--two-way tests: a recording to use as your mic (with --file as their side)")
    p.add_argument("--record-out", help=argparse.SUPPRESS)  # tests: folder for what each side heard
    p.add_argument("--original-volume", type=float, default=0.2,
                   help="how loud the original voice is between English lines, 0-1 (0 = only the English voice)")
    p.add_argument("--duck-volume", type=float, default=0.05,
                   help="how loud the original voice is while an English line plays, 0-1")
    p.add_argument("--in", dest="inp", default=None, help="input device (default: BlackHole 2ch; with --outgoing, the Mac's mic)")
    p.add_argument("--out", default=None, help='output device (default: system default; with --outgoing, BlackHole 16ch); '
                                               '"none" = silent, with --file')
    p.add_argument("--no-voice", action="store_true", help="subtitles only, no English voice")
    p.add_argument("--no-drafts", action="store_true", help="no live draft captions while she's mid-sentence")
    p.add_argument("--voice", choices=["clone", "stock"], default="clone",
                   help="clone = the English sounds like the caller (learned from ~10 s of their speech); stock = Kokoro")
    p.add_argument("--voice-sample", help="audio of the caller to clone right away, e.g. a WhatsApp voice note (.opus/.m4a/.wav)")
    p.add_argument("--new-voice", action="store_true", help="relearn the caller's voice on this call (calling someone else)")
    p.add_argument("--caller", default="Grandma", help='who you are calling, e.g. "Ammamma" (used on the story page and prompts)')
    p.add_argument("--no-story", action="store_true", help="don't keep a story page for this call")
    p.add_argument("--no-record", action="store_true", help="keep the story page but save no audio of the call")
    p.add_argument("--no-prompts", action="store_true", help="no live 'ask her' question suggestions")
    p.add_argument("--prompt-every", type=float, default=25, help="at most one 'ask her' prompt this many seconds apart")
    p.add_argument("--no-open", action="store_true", help="don't open the story page when the call ends")
    p.add_argument("--keep-at", type=float, default=KEEP_AT,
                   help="keep a word in Telugu once it's this likely they know it, 0-1 (progress.py; lower = sooner, "
                        "e.g. 0.4 for a demo keeps a word from its second mention)")
    p.add_argument("--reset-progress", action="store_true", help="forget which words you know (deletes progress.json)")
    p.add_argument("--speak", choices=["telugu", "questions", "all"], default=None,
                   help="telugu = voice what she says in Telugu, never her English; questions = only Telugu "
                        "questions/requests to you (Laya decides); all = every line (default while --original-volume "
                        "is low, since her own English would be too quiet to follow)")
    args = p.parse_args()
    if args.outgoing:
        args.inp = args.inp or "MacBook"  # the built-in mic ("MacBook Pro Microphone"); pass --in for a headset mic
        args.out = args.out or "BlackHole 16ch"
    args.speak = args.speak or ("all" if args.original_volume < 0.5 else "telugu")
    args.inp = args.inp or "BlackHole 2ch"  # not just "BlackHole": that also matches BlackHole 16ch, the --outgoing mic
    args.voice_file = MY_VOICE_SAMPLE if args.outgoing else VOICE_SAMPLE
    if args.two_way and args.outgoing:
        p.error("--two-way already includes your side (--outgoing)")
    # Both directions can run at once (two terminals), so --outgoing gets its own overlay page.
    port = PORT + 2 if args.outgoing and "OVERLAY_PORT" not in os.environ else PORT

    if args.translator == "local":
        start_translator(args.lang)

    from websockets.sync.server import serve
    pages = [(HUB, port)] + ([(ME_HUB, port + 2)] if args.two_way else [])
    for hub, hub_port in pages:
        server = serve(hub.handler, "localhost", hub_port, process_request=serve_overlay)
        threading.Thread(target=server.serve_forever, daemon=True).start()
    if args.two_way:
        print(f"Overlay: http://localhost:{port} (them -> you), http://localhost:{port + 2} (you -> them)", flush=True)
    else:
        print(f"Overlay: http://localhost:{port}", flush=True)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()

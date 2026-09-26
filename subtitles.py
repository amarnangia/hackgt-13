# Steps 2-3 of plan.md: live call audio -> Muse Voice Transcribe -> Muse Spark translation -> overlay.
#   python subtitles.py --out "MacBook Air Speakers"         # live call (see Audio setup in plan.md)
#   python subtitles.py --file samples/telugu_grandma.wav    # no call needed, replays a recording
# Then open http://localhost:8765 for the subtitle overlay.
# The offline Whisper version of this file is in git history (commit d111471).
import argparse
import asyncio
import atexit
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
from latency import LatencyTracker
from lexicon import Lexicon, indic_share
from progress import Progress
from pronouns import PronounResolver
from translate_server import LocalTranslator

PORT = int(os.environ.get("OVERLAY_PORT", 8765))
HERE = os.path.dirname(os.path.abspath(__file__))
CHUNK_MS = 80
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
LOCAL_DEADLINE_S = 1.2  # after this, race Muse Spark against the local translator

clients = set()
on_client_message = None  # set by main(): handles clicks sent from the overlay


def broadcast(msg):
    data = json.dumps(msg, ensure_ascii=False)
    for c in list(clients):
        try:
            c.send(data)
        except Exception:
            clients.discard(c)


def ws_handler(conn):
    clients.add(conn)
    try:
        for message in conn:
            if on_client_message:
                on_client_message(json.loads(message))
    finally:
        clients.discard(conn)


def serve_overlay(conn, request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
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

    def __init__(self, lang, translator="local", learn_after=1, keep_known=True):
        self.translate = None
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
        self.pool = ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS)
        self.race_pool = ThreadPoolExecutor(max_workers=TRANSLATE_WORKERS * 2)  # local vs Muse Spark when slow
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
        self.speak_all = False                # --speak all: also voice lines she said (mostly) in English
        self.questions_only = False           # --speak questions: voice only questions/requests to you
        self.lexicon = Lexicon()
        self.lang = lang
        self.pronouns = PronounResolver(lang)  # తను -> she or he, from who was mentioned before
        self.backup = None  # Muse Spark, created if the local translator fails mid-call
        self.progress = Progress(self.lexicon, lang, learn_after=learn_after)  # words kept in Telugu
        self.known_at_start = {i for i in self.progress.entries if self.progress.known(i)}  # for the story page
        self.heard_at_start = dict(self.progress.heard)
        self.keep_known = keep_known  # off for --outgoing: the person you're calling doesn't know Telugu
        self.order_lock = threading.Lock()    # translations finish out of order; the voice must not
        self.next_to_voice, self.finished_lines = 1, {}

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
            self.latency.new_turn()
            broadcast({"type": "speaking"})
        elif kind == "transcript" and not ev.get("final"):
            self.partial = ev["transcript"]
            self.latency.on_partial(self.partial, ev.get("audioProcessedMs"))
            self._cut(final=False)
            broadcast({"type": "partial", "text": self.partial[self.done:].strip()})
        elif kind == "speechEnd":
            self._cut(final=True)
            broadcast({"type": "partial", "text": ""})

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

    def _submit(self, sentence, end_offset):
        self.next_id += 1
        seg_id = self.next_id
        marks = self.latency.piece_cut(end_offset)
        start_s, end_s = self.recorder.span(marks["audio_ms"]) if self.recorder else (None, None)
        share = indic_share(sentence)
        # english: grandma said it in English, you understood it -> show as-is, no translation, no voice
        # mixed:   mostly English with a Telugu word or two -> translated subtitle, no voice
        # native:  Telugu (or mostly) -> translated subtitle + English voice
        route = "english" if share == 0 else "mixed" if share < NATIVE_MIN_SHARE else "native"
        broadcast({"type": "original", "id": seg_id, "text": sentence, "route": route})
        to_translate = self.pronouns(sentence)  # here, not in work(): it must see sentences in the order said

        def work():
            if route == "english":
                english = sentence
            else:
                english = self._translate_in_time(to_translate)
            full_english, kept = english, []
            hits = self.lexicon.find(sentence, self.lang)
            known_before = {h["id"] for h in hits if self.progress.known(h["id"])}  # before counting this hearing
            if self.keep_known and route != "english" and not english.startswith("("):
                # Words the listener knows stay in Telugu ("Today, Ammamma made pulihora"); the rest is English.
                english, kept = self.progress.keep_known_words(english, hits)
                self.progress.heard_words(hits)
            broadcast({"type": "english", "id": seg_id, "text": english, "route": route, "kept": kept})
            row = self.latency.finished(marks, sentence, english)
            row["route"] = route
            # Laya reads the all-English version; cards follow the text by ~0.15 s
            decision = self.decider(full_english) if self.decider and not english.startswith("(") else None
            broadcast({"type": "details", "id": seg_id,
                       "intent": decision["intent"] if decision else None, "cards": self._cards(sentence, decision)})
            picture = self._picture(seg_id, hits, full_english, known_before)
            row["laya"] = decision["seconds"] if decision else None
            intent = decision["intent"] if decision else None
            if self.recorder:
                self.recorder.add_line(id=seg_id, telugu=sentence, english=english, english_full=full_english, route=route,
                                       kept=kept, intent=intent, picture=picture, start_s=start_s, end_s=end_s)
            if self.prompter and route != "english":
                self.prompter.on_line(sentence, full_english, intent, route)
            with self.order_lock:
                self.finished_lines[seg_id] = (english, marks, row, decision, route)
                while self.next_to_voice in self.finished_lines:
                    self._voice(self.next_to_voice, *self.finished_lines.pop(self.next_to_voice))
                    self.next_to_voice += 1

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
            broadcast({"type": "picture", "id": seg_id, **card})
            print(f"  [picture: {card['name']}]", flush=True)
        return card

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

    def _cards(self, sentence, decision):
        """Word-list matches in what grandma said (exact), else Laya's category guess for the English line."""
        cards = [{"id": e["id"], "title": e["id"].replace("_vocative", "").replace("_", " ").title(),
                  "category": e["category"], "note": e.get("note", "")} for e in self.lexicon.find(sentence, self.lang)]
        cards += [{"id": e["id"], "title": e["id"].replace("_", " ").title(), "category": e["category"],
                   "note": e.get("note", "")} for e in self.lexicon.find(sentence, "en")]  # English slang she used
        if decision and decision["category"] != "none" and not any(c["category"] == decision["category"] for c in cards):
            cards.append({"id": None, "title": decision["category"].title(), "category": decision["category"], "note": ""})
        return cards

    def _voice(self, seg_id, english, marks, row, decision, route):
        """Voice Telugu lines (in order). Questions/requests to you keep their place when the voice is behind."""
        def on_start():
            self.latency.voice_started(row, marks)
            broadcast({"type": "voice", "id": seg_id})
        asks = bool(decision and decision["needs_attention"])
        if route != "native" and not self.speak_all:
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
        print(f"{LatencyTracker.line(row)} {row['text']}  ->  {english}{tag}", flush=True)


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
    captioner = Captioner(args.lang, args.translator, args.learn_after, keep_known=not args.outgoing)

    def on_message(msg):
        if msg.get("type") == "forget" and msg.get("id"):
            captioner.progress.forget(msg["id"])
            print(f"Marked '{msg['id']}' as not known; it will be translated again.", flush=True)
    global on_client_message
    on_client_message = on_message
    try:
        await listen(args, captioner)
    finally:  # also on Ctrl+C
        print("\n" + captioner.latency.summary() + "\n(per-sentence log: latency_log.jsonl)", flush=True)
        finish_call(captioner, args)


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
    print(f"Story page:        {page}\nFamily dictionary: {os.path.join(HERE, 'calls', 'dictionary.html')}", flush=True)
    if not args.no_open:
        subprocess.run(["open", page], check=False)


async def listen(args, captioner):
    loop = asyncio.get_running_loop()
    target = {"q": asyncio.Queue(), "latency": captioner.latency}
    audio = make_audio(args, loop, target)
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
    if not args.no_prompts:
        from prompts import StoryPrompter

        def on_prompt(q):
            broadcast({"type": "prompt", "caller": args.caller, **q})
            if captioner.recorder:
                captioner.recorder.add_prompt(q)
            print(f"  [ask {args.caller}: {q['roman']}  ({q['english']})]", flush=True)
        captioner.prompter = StoryPrompter(captioner.decider, args.caller, on_prompt)
    captioner.speak_all = args.speak == "all"
    captioner.questions_only = args.speak == "questions"
    if not args.no_voice:  # load before audio starts, or the first seconds of the call are lost
        print("Loading the English voice (Kokoro)...", flush=True)
        from dub import Dubber, VoiceSampler
        sample = prepare_voice_sample(args)
        who = "your " if args.outgoing else "the caller's "
        clone = args.voice == "clone"
        captioner.dubber = await loop.run_in_executor(
            None, lambda: Dubber(audio.voice, clone=clone, voice_sample=sample))
        if clone and captioner.dubber.cloning:
            print(f"English voice: {who}voice from {sample}. (--new-voice to relearn it on this call)", flush=True)
        elif clone:
            print(f"English voice: stock voice until {who}voice is learned (~10 s of speech).", flush=True)
            target["sampler"] = captioner.sampler = VoiceSampler(args.voice_file, captioner.dubber.use_voice_sample)
    threading.Thread(target=audio.run, kwargs={"meter": False}, daemon=True).start()
    # Connect to Muse only once audio is actually flowing; a silent gap right after connecting makes it hang up.
    for _ in range(50):
        if not target["q"].empty():
            break
        await asyncio.sleep(0.1)
    else:
        print("No audio is arriving from the input device after 5 s. Check that the terminal has microphone "
              "permission (System Settings > Privacy & Security > Microphone).", flush=True)
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
                captioner.on_event(ev)
        except Exception as e:
            if args.file:
                raise
            print(f"Muse connection dropped ({e}); reconnecting...", flush=True)
            await asyncio.sleep(0.2)
            continue
        if args.file:
            await ender
            await loop.run_in_executor(None, lambda: captioner.pool.shutdown(wait=True))  # last translations
            while captioner.dubber and (captioner.dubber.behind() > 0 or audio.voice.active()):
                await asyncio.sleep(0.2)  # let the last English line finish speaking
            await asyncio.sleep(0.3)
            audio.stop.set()
            return


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
    p.add_argument("--original-volume", type=float, default=0.2,
                   help="how loud the original voice is between English lines, 0-1 (0 = only the English voice)")
    p.add_argument("--duck-volume", type=float, default=0.05,
                   help="how loud the original voice is while an English line plays, 0-1")
    p.add_argument("--in", dest="inp", default=None, help="input device (default: BlackHole 2ch; with --outgoing, the Mac's mic)")
    p.add_argument("--out", default=None, help='output device (default: system default; with --outgoing, BlackHole 16ch); '
                                               '"none" = silent, with --file')
    p.add_argument("--no-voice", action="store_true", help="subtitles only, no English voice")
    p.add_argument("--voice", choices=["clone", "stock"], default="clone",
                   help="clone = the English sounds like the caller (learned from ~10 s of their speech); stock = Kokoro")
    p.add_argument("--voice-sample", help="audio of the caller to clone right away, e.g. a WhatsApp voice note (.opus/.m4a/.wav)")
    p.add_argument("--new-voice", action="store_true", help="relearn the caller's voice on this call (calling someone else)")
    p.add_argument("--caller", default="Grandma", help='who you are calling, e.g. "Ammamma" (used on the story page and prompts)')
    p.add_argument("--no-story", action="store_true", help="don't keep a story page for this call")
    p.add_argument("--no-record", action="store_true", help="keep the story page but save no audio of the call")
    p.add_argument("--no-prompts", action="store_true", help="no live 'ask her' question suggestions")
    p.add_argument("--no-open", action="store_true", help="don't open the story page when the call ends")
    p.add_argument("--learn-after", type=int, default=1,
                   help="keep a word in Telugu after hearing it this many times (0 = keep every known word from the start)")
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
    # Both directions can run at once (two terminals), so --outgoing gets its own overlay page.
    port = PORT + 2 if args.outgoing and "OVERLAY_PORT" not in os.environ else PORT

    if args.translator == "local":
        start_translator(args.lang)

    from websockets.sync.server import serve
    server = serve(ws_handler, "localhost", port, process_request=serve_overlay)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Overlay: http://localhost:{port}", flush=True)
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()

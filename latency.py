# Per-sentence latency for the live pipeline, split by stage, with a p50/p90 summary at the end.
#
#   spoken ──► text ──► sent ──► English on screen
#     │  speech-to-text │  split  │  translate (incl. queue)
#     └──────────────── total ────┘
#
# "spoken" is when the sentence's last word was said, on the wall clock: the moment the first audio frame
# was captured plus Muse's audioProcessedMs for the update that first contained that word. Muse reports
# how much audio it had processed, not exact word times, so this is a slight upper bound on "spoken"
# and the totals are slightly optimistic (by at most one 80 ms audio frame plus Muse's lookahead).
import json
import statistics
import time

STAGES = ["speech_to_text", "split", "translate", "laya", "total", "voice_wait", "total_voice"]
LABELS = {"speech_to_text": "speech-to-text", "split": "waiting to split", "translate": "translate", "laya": "Laya decides",
          "total": "spoken -> English", "voice_wait": "English -> voice", "total_voice": "spoken -> voice"}


class LatencyTracker:
    def __init__(self, log_path="latency_log.jsonl"):
        self.stream_start = None  # wall clock when the session's first audio frame was captured
        self.seen = []            # (end offset in the partial, audio ms, wall time) as text first appears
        self.rows = []
        self.log = open(log_path, "a")

    def audio_started(self, t):
        self.stream_start = t

    def new_turn(self):
        self.seen = []

    def on_partial(self, text, audio_ms):
        if not self.seen or len(text) > self.seen[-1][0]:
            self.seen.append((len(text), audio_ms, time.monotonic()))

    def piece_cut(self, end_offset):
        """Call when a piece ending at `end_offset` of the current partial is sent for translation."""
        audio_ms, recognized = None, time.monotonic()
        for offset, ms, wall in self.seen:
            if offset >= end_offset:
                audio_ms, recognized = ms, wall
                break
        spoken = self.stream_start + audio_ms / 1000 if self.stream_start and audio_ms is not None else None
        return {"spoken": spoken, "recognized": recognized, "cut": time.monotonic()}

    def finished(self, marks, text, english):
        now = time.monotonic()
        row = {
            "text": text, "english": english,
            "speech_to_text": marks["recognized"] - marks["spoken"] if marks["spoken"] else None,
            "split": marks["cut"] - marks["recognized"],
            "translate": now - marks["cut"],
            "total": now - marks["spoken"] if marks["spoken"] else None,
            "voice_wait": None, "total_voice": None, "english_at": now, "laya": None,
        }
        self.rows.append(row)
        return row

    def voice_started(self, row, marks):
        """The English voice for this line just started playing."""
        now = time.monotonic()
        row["voice_wait"] = now - row["english_at"]
        row["total_voice"] = now - marks["spoken"] if marks["spoken"] else None
        self.log_row(row)

    def log_row(self, row):
        self.log.write(json.dumps({k: v for k, v in row.items() if k != "english_at"}, ensure_ascii=False) + "\n")
        self.log.flush()

    @staticmethod
    def line(row):
        fmt = lambda v: f"{v:.2f}s" if v is not None else "?"
        return (f"[spoken -> English {fmt(row['total'])} | speech-to-text {fmt(row['speech_to_text'])}, "
                f"split {fmt(row['split'])}, translate {fmt(row['translate'])}]")

    def summary(self):
        if not self.rows:
            return "No sentences measured."
        out = [f"Latency over {len(self.rows)} sentences (seconds):", f"  {'stage':20} {'p50':>6} {'p90':>6} {'max':>6}"]
        for stage in STAGES:
            vals = sorted(r[stage] for r in self.rows if r.get(stage) is not None)
            if not vals:
                continue
            p90 = vals[min(len(vals) - 1, int(round(0.9 * (len(vals) - 1))))]
            out.append(f"  {LABELS[stage]:20} {statistics.median(vals):6.2f} {p90:6.2f} {vals[-1]:6.2f}")
        return "\n".join(out)

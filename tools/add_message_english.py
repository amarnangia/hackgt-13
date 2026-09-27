# Calls saved before the story keeper wrote an English version of the message to send her: add it (Muse Spark),
# so the app's Message tab can show what the Telugu says. Only fills in "message_en" where it's missing; nothing else
# in call.json changes.
#   python tools/add_message_english.py
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from calls import CALLS_DIR  # noqa: E402
from muse import spark_json  # noqa: E402

for path in sorted(glob.glob(os.path.join(CALLS_DIR, "*", "call.json"))):
    call = json.load(open(path, encoding="utf-8"))
    story = call.get("story") or {}
    if not story.get("message_te") or story.get("message_en"):
        continue
    a = spark_json("Translate this WhatsApp message from a grandchild to their Telugu-speaking grandparent into natural, "
                   'warm English. Key: "english".', story["message_te"], model="muse-spark-1.1", effort="minimal", timeout=30)
    if not (a and a.get("english")):
        print(f"{call['id']}: couldn't translate it (try again later)")
        continue
    story["message_en"] = a["english"].strip()
    json.dump(call, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{call['id']}: {story['message_en']}")

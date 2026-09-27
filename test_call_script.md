# Roots: test call and demo script ("Ammamma's Sankranti")

A real test call that exercises the core features, and doubles as the demo. **Your friend** runs Roots on their Mac
(Chrome overlay plus the iPhone app). **You** call from your phone as Ammamma and read the Telugu lines.

Every line below was run through the real engine (no audio) on 2026-09-27, and "What should happen" is what it
actually produced. (Line 5 is the first sentence of a tested line; the second sentence was dropped because it
mistranslated "peanuts" as "chillies".) If something doesn't happen on the real call, the "If it doesn't" column says where to look.

---

## Part 1: Setup on your friend's Mac (about 10 minutes, before calling)

### 1. Get the latest code and packages
```
cd ~/hackgt-13
git pull
.venv/bin/pip install -r requirements.txt
```
**Don't skip the `pip install`.** The new idiom detector needs a package (`rapidfuzz`) that was added recently. Without
it, idioms and sayings silently never appear. We found exactly this on one of our Macs.

### 2. Chrome extension
- Go to `chrome://extensions` and click ↻ on **Roots overlay**. If Chrome asks to allow access to **localhost**, allow
  it. That permission is what lets pictures load.

### 3. Quick picture test, before the real call (2 minutes)
This tests the picture fix in the real extension:
```
.venv/bin/python tools/fake_call.py --fast
```
- Open any website tab (e.g. web.whatsapp.com) and press **Option+Shift+W**.
- Within about 30 s you should see **pictures pop up in the top right** (pulihora, gavvalu, Bhogi) and a **"Saying"
  card at the top center**.
- ✅ Pictures appear → continue. ❌ Dark or empty boxes, or no pictures → see Troubleshooting, row 1.
- Stop it with **Ctrl+C** (it uses the same port as the real engine).

### 4. Sound
- System Settings → Sound → **Output: BlackHole 2ch**, volume **100%**. **Input:** the Mac's microphone.
- Headphones on your friend, so the English voice doesn't echo back to your phone.

### 5. Start Roots
**Terminal 1, the engine** (`--keep-at 0.4` makes a word stay in Telugu from its second mention, so it shows within
one call):
```
cd ~/hackgt-13
.venv/bin/python subtitles.py --caller Ammamma --me <friend's name> --out "<headphones>" --original-volume 0.6 --duck-volume 0.15 --speak telugu --keep-at 0.4
```
Wait for `Overlay: http://localhost:8765` and "listening".

**Terminal 2, for the iPhone app:**
```
cd ~/hackgt-13
python3 -m garden
```
Then open the iPhone app in the Simulator (▶ in Xcode) on the **Progress** tab.

### 6. The call
- Open **web.whatsapp.com in Chrome** (not the WhatsApp Mac app). In the call's **⋯ → Settings**, set **Speaker =
  Default**.
- You call from your phone. Your friend answers in WhatsApp Web and presses **Option+Shift+W**.

---

## Part 2: The test call

**How to speak:** clearly, at a normal pace, one line at a time. **Pause 3–4 s after each line**; the "Ask her"
questions only appear in pauses. Your friend (the grandkid) says their parts out loud.

| # | You say (Ammamma) | How to say it | Means | What should happen (tested) | If it doesn't |
|---|---|---|---|---|---|
| 1 | నాన్నా, బాగున్నావా? అన్నం తిన్నావా? | *Nanna, bagunnava? Annam tinnava?* | Dear, are you well? Did you eat? | Caption: **"Nanna, are you doing well? Have you eaten?"** · **"Asked you"** tag · English spoken in a voice · top center: **Saying: "annam tinnava"**, *"'Did you eat?' is how Telugu elders say 'How are you? I care about you'"* | No caption → Troubleshooting 2. No voice → 4. No saying → 3 |
| 2 | *(Grandkid:)* "Avunu Ammamma, tinnanu!" | | Yes Grandma, I ate! | Nothing special (this is the grandkid talking) | — |
| 3 | ఈ రోజు నీ కోసం పులిహోర చేశాను. | *Ee roju nee kosam pulihora chesanu.* | Today I made pulihora for you. | Caption: **"Today I made *tamarind rice* for you."** (first time: translated) · **Pulihora picture** top right · **pause 3–4 s** → top center: **"Pulihora ela chestaru? Naaku nerpistara?"** (How do you make pulihora? Will you teach me?) | No picture → Troubleshooting 1. No question after the pause → 5 |
| 4 | *(Grandkid reads the question on screen:)* "Pulihora ela chestaru? Naaku nerpistara?" | | | | |
| 5 | మా అమ్మ నాకు పులిహోర నేర్పింది. | *Maa amma naaku pulihora nerpindi.* | My mother taught me pulihora. | Caption: **"My Amma taught me *pulihora*."** Now **pulihora stays in Telugu**, underlined, with "(tamarind rice)" small next to it: the grandkid learned it | Still says "tamarind rice" → Troubleshooting 6 |
| 6 | సంక్రాంతికి గవ్వలు, అరిసెలు కూడా చేశాను. | *Sankranti ki gavvalu, ariselu kooda chesanu.* | For Sankranti I also made gavvalu and ariselu. | Caption: **"I also made shell-shaped sweets and rice sweets for Sankranti."** · **Gavvalu picture** · small corner cards for Sankranti and ariselu | No picture → 1 |
| 7 | మా చిన్నప్పుడు భోగి మంటలు వేసేవాళ్ళం, గంగిరెద్దులు ఇంటికి వచ్చేవి. | *Maa chinnappudu Bhogi mantalu vesevallam, gangireddulu intiki vachevi.* | When we were little we lit Bhogi bonfires, and decorated bulls came to the house. | Caption: **"In our childhood, we used to make bhogi bonfires and decorated bulls used to come home."** · **Bhogi picture** · after the pause: **"Mee chinnappudu Bhogi ela jarupukunevaaru?"** (How did you celebrate Bhogi when you were little?) | No picture → 1. No question → 5 |
| 8 | నోరు మంచిదైతే ఊరు మంచిది అని మా అమ్మ చెప్పేది. | *Noru manchidaite ooru manchidi ani maa amma cheppedi.* | My mother used to say: if your words are kind, the whole village is kind. | Top center, big: **Saying: "noru manchidaite uru manchidi"** with its meaning. The caption may be literal (**"if the mouth is good, the town is good"**); **that's the point:** the card explains what the literal translation misses | No saying card → Troubleshooting 3 |
| 9 | ఎప్పుడు వస్తావు నాన్నా? జాగ్రత్తగా ఉండు. | *Eppudu vastavu nanna? Jagrattaga undu.* | When will you come, dear? Take care. | Caption: **"When will you come Nanna? Take care."** · **"Asked you"** tag | — |
| 10 | *(Grandkid:)* "Tvaralo vastanu, Ammamma. Bye!" then hang up | | I'll come soon, Grandma. | | |

### After the call
Your friend presses **Ctrl+C** in Terminal 1.

| Check | What should happen | If it doesn't |
|---|---|---|
| Story page | Opens in the browser after about 30 s: a title, a summary, **the stories she told with clips of your voice**, the pictures, the words from the call, **3 questions for next time**, and **a Telugu message to send her (with the English)** | Nothing opens → Troubleshooting 7 |
| iPhone **Progress** tab (pull down to refresh) | The plant has grown, and the **Next call** card shows a question from this call ("Ask Ammamma: …") | Old question → refresh, and check Terminal 2 is running |
| iPhone **Words** tab | *pulihora*, *gavvalu*, *annam tinnava* and others are listed as New or Learning | Empty → Terminal 2 must be running |

### Scorecard (fill in during the call)
| Feature | Worked? | Notes |
|---|---|---|
| Captions appear within ~1–2 s after each line | ☐ | |
| English voice plays | ☐ | |
| Pulihora, gavvalu and Bhogi pictures show (not black boxes) | ☐ | |
| "annam tinnava" and the proverb appear big at the top center | ☐ | |
| "Ask her" question appears after lines 3 and 7 | ☐ | |
| *pulihora* stays in Telugu on line 5 | ☐ | |
| "Asked you" tag on lines 1 and 9 | ☐ | |
| Story page with your voice clips and the message | ☐ | |
| iPhone Next call card and Words tab update | ☐ | |

---

## Part 3: Troubleshooting (what went wrong, where to look)

| # | Symptom | Most likely cause | Fix |
|---|---|---|---|
| 1 | Pictures don't show, or show as dark boxes | The extension wasn't reloaded, or the localhost permission wasn't allowed | `chrome://extensions` → ↻ Roots overlay → allow localhost → reload the WhatsApp tab. Run the Part 1 step 3 test |
| 2 | No captions at all | The call's sound isn't reaching Roots | Output = **BlackHole 2ch**, volume **100%**, call in **WhatsApp Web** (not the app), WhatsApp Web speaker = Default. Terminal 1 prints a warning after 15 s of silence |
| 3 | No "Saying" card at the top | `rapidfuzz` isn't installed, **or** speech recognition wrote the saying very differently | Look in Terminal 1 for `sayings check failed: … rapidfuzz` → run `.venv/bin/pip install -r requirements.txt`. Otherwise say the line again, slowly |
| 4 | No English voice | The voice skips lines that would be more than ~3 s late, and lines she said in English | Pause longer between lines. Terminal 1 says `[no voice: voice was behind]` when it skipped one |
| 5 | No "Ask her" question | It only appears after a **2 s pause**, and not right after she **asked** something | Pause 3–4 s after lines 3 and 7. Don't end those lines with a question |
| 6 | Pulihora is still translated on line 5 | The word wasn't heard earlier (line 3 missed), or the engine was started without `--keep-at 0.4` | Check line 3 came through, and check the command |
| 7 | No story page | Ctrl+C before anything was said, or no internet (Muse Spark writes it) | Terminal 1 prints the page's path; look in `calls/` |
| 8 | Captions come very late (5+ s) | The Mac is short on memory | Close other apps. Use the 24 GB Mac for the demo |
| 9 | Wrong words in the caption | Speech recognition misheard, or the translator is imperfect | Terminal 1 prints what was heard (Telugu) and the English. Note which line and what it said |

**Terminal 1 tells you everything:** for each line it prints what was heard, the English, the picture, and why the
voice was or wasn't played. When something goes wrong, screenshot Terminal 1 at that moment.

---

## Part 4: The demo (use the same call)

The judges said to focus, so the demo shows **three moments**. Everything else is just there.

1. **Understanding her:** line 1 (caption, her voice, and the saying *annam tinnava*).
2. **The connection moment:** line 3 → the pulihora picture → **"Ask her"** → the grandkid asks in Telugu → she
   answers with where the recipe came from (line 5).
3. **Learning:** line 5 → *pulihora* now stays in Telugu. Then hang up → the story page with her voice.

Lines 6–9 are optional in the demo. Use line 8 (the proverb) only if there's time.

### What to say over it
- **Before the call:** "My grandmother only speaks Telugu. I don't. Our calls used to be 'did you eat?' and 'bye.'
  Roots runs on the WhatsApp call we already make. She installs nothing."
- **Line 1:** "I hear her in English, and it even tells me that 'annam tinnava', 'did you eat?', is how she says 'I
  care about you.'"
- **Line 3 → "Ask her":** "I don't know what pulihora is, so Roots shows me. And instead of explaining her life to
  me, it gives me a question to ask her, in Telugu."
- **Line 5:** "She tells me who taught her. The AI didn't tell that story; it got her to tell it. And notice:
  *pulihora* stayed in Telugu. I've learned it, so Roots stopped translating it."
- **Hang up:** "Every call becomes a page for our family, with her voice, and a message in Telugu I can send her."
- **Close:** "Most translators get better at translating. Roots gets better at knowing when not to."

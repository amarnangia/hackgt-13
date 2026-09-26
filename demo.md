# Demo: a 2–3 minute call with Ammamma

Two people. **Grandma** calls from a phone on WhatsApp and reads the lines below. **The grandkid** takes the call on
the laptop in Chrome (WhatsApp Web) with Weave on top. Every line below was run through the pipeline to check what it triggers.

## Before you start (5 minutes)
1. Laptop: Mac output = **BlackHole 2ch**, volume **100%**, and **headphones** on, so the English voice doesn't echo back to the phone.
2. Terminal: `python subtitles.py --out "MacBook Air Speakers" --caller "Ammamma" --original-volume 0.6 --duck-volume 0.15 --speak telugu --keep-at 0.4`
   (`--keep-at 0.4` keeps a word in Telugu from its second mention, so the learning shows within one call.)
3. Wait for `Overlay: http://localhost:8765` and "listening".
4. In Chrome, open the WhatsApp Web call. Press **Alt+Shift+W** to turn Weave on.
5. Grandma: speak clearly, one line at a time, and pause about 2 seconds after each.
6. Backup: record the screen during a good run. If the live audio fails at the table, play the recording.

## The call

| # | Grandma says (Telugu) | How to say it | What shows up | Grandkid does |
|---|---|---|---|---|
| 1 | నాన్నా, బాగున్నావా? అన్నం తిన్నావా? | *Nanna, bagunnava? Annam tinnava?* | English in her cloned voice; **Asked you** tag; left: *How do I say "Yes, I ate. Did you eat?"* and *What does "annam tinnava" mean?*; words: **Saying hello** | Clicks the reply and says it: *"Avunu, tinnanu. Meeru tinnara?"* |
| 2 | నిన్న సంక్రాంతికి గవ్వలు, అరిసెలు చేశాను. | *Ninna Sankranti ki gavvalu, ariselu chesanu.* | Right: **gavvalu** picture; left: *What is gavvalu?*, *What is ariselu?*; words switch to **Food and cooking**; at the pause: **Ask Ammamma about Gavvalu**: *"Gavvalu ela chestaru? Naaku nerpistara?"* | Clicks *What is gavvalu?* (the answer shows at once) |
| 3 | ఈ రోజు పులిహోర చేశాను, నీకు చాలా ఇష్టం కదా? | *Ee roju pulihora chesanu, neeku chala ishtam kada?* | **pulihora** picture; *How do I say "Yes, I like it a lot"* → *"Avunu, naaku chala ishtam"* | Says it |
| 4 | పులిహోర చాలా బాగా వచ్చింది. | *Pulihora chala baaga vachindi.* | The caption now keeps **pulihora** in Telugu: the grandkid learned it; at the pause, **Ask Ammamma about Pulihora**: *"Pulihora ela chestaru?"* | Asks her, in Telugu |
| 5 | మా చిన్నప్పుడు భోగి మంటలు వేసేవాళ్ళం, గంగిరెద్దులు ఇంటికి వచ్చేవి. | *Maa chinnappudu Bhogi mantalu vesevallam, gangireddulu intiki vachevi.* | **Bhogi** picture; **gangireddu** custom card; words switch to **Festivals and temple**; *What is gangireddu?*, *What does "chinnappudu" mean?* | Clicks *What is gangireddu?* |
| 6 | నోరు మంచిదైతే ఊరు మంచిది అని మా అమ్మ చెప్పేది. | *Noru manchidaite ooru manchidi ani maa amma cheppedi.* | The caption is literal ("if the mouth is good, the town is good"); the card on the right gives what it means: *if your words are kind, the whole village is kind* | Points out the card: word-for-word translation misses it |
| 7 | మీ తాతయ్య ఎన్టీఆర్ సినిమాలు చాలా ఇష్టపడేవారు. | *Mee thatayya NTR cinemalu chala ishtapadevaru.* | **NTR** picture; *Who is NTR?*; at the pause: **Ask Ammamma: "Meeru, Thatayya ela kalisaru?"** (How did you and Thatayya meet?) | Asks it: the moment the demo is about |
| 8 | ఎప్పుడు వస్తావు నాన్నా? జాగ్రత్తగా ఉండు, బాగా చదువుకో. | *Eppudu vastavu nanna? Jagrattaga undu, baaga chaduvuko.* | **Request** tag; *How do I say "I'll come soon"* → *"Tvaralo vastanu"* | Says *"Tvaralo vastanu, Ammamma"*, then hangs up |
| 9 | (the call ends) | | Stop `subtitles.py` (Ctrl+C): the **story page** opens with her stories, her voice clips, pictures, the words from this call and questions for next time | Shows the story page and the family dictionary |

"Ask Ammamma" questions come at most every 25 s (`--prompt-every`), at her pauses, so with about 10–15 s per line they
appear after lines 2, 4 and 7. Checked by running these lines through the pipeline (without audio).

## What to say over it (for the video)
- **0:00** "My grandmother only really talks in Telugu. I don't. Our calls used to be 'did you eat?' and 'bye'."
- **0:15** Line 1: "Weave runs on the WhatsApp call I already make. I hear her in English, in her own voice, and it tells me how to answer in Telugu."
- **0:40** Lines 2–4: "It shows me what she's talking about, and once I've learned a word, it stops translating it."
- **1:20** Lines 5–7: "It explains her sayings, and at every pause it gives me a question to ask her, so she tells me the story instead of me just listening."
- **2:00** Line 9: "When we hang up, the call becomes a page for the family, with her voice."
- **2:20** "Meta's Muse hears and writes; a small local model, Laya, makes five decisions per sentence in a quarter of a second, so the call stays fast."

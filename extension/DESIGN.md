# Weave design system

One system for the overlay (`panel.css`, `content.js`), the web app (`garden/web/index.html`), the iPhone app and
widget (`garden/ios/Shared/Theme.swift`) and the call summary pages (`calls.py`, `STYLE`).

## English only

Nothing in Telugu script is shown. Romanized words and English only; `noTe()` in panel.js is the last filter every
shown string passes through. Captions show the English of each line (never her words as heard), and there's no speaker
label.

## Layout over a call

A video call puts the other person's face in the middle, your camera in a bottom corner and the call's buttons along the
bottom. Weave uses the edges and the space just above the call's buttons. Every panel is its own frame, placed with
`translate3d` once per size change and shown, hidden and moved only with transform and opacity.

| Zone | Where | Size | When it's there |
|---|---|---|---|
| Ask her (top) | top center, 16px down | the pill's own width, up to 620px | after a 2 s pause in the talk; stays at least 5 s; leaves once someone has talked for 1.5 s; the question lasts 45 s |
| Words (left) | the top-left corner, 16px in | 300px wide, as tall as its 5 word bubbles and 3 question bubbles; no box | always; the words button hides it |
| Pictures and meanings (float) | the top-right corner, 16px in | 320px wide, as tall as its cards (at most 2), up to the full window height so a small call window never squeezes them | each shows for about 2.5 s and fades out in 0.7 s; they can't be clicked (clicks go through to the call) |
| Translation bubble | bottom center, right above the orb | up to 700 × 148, fixed | while someone talks; fades 9 s after the last words |
| The line | bottom center, 66px up (just above the call's buttons) | 240 × 56 | always; beside it the words and pictures buttons, and English / Telugu in two-way calls |

## Tokens

| Token | Value | Use |
|---|---|---|
| bg-1 / bg-2 / bg-3 | `#121212` / `#1a1a1a` / `#232326` | app backgrounds, image placeholders |
| glass | `rgba(20,20,22,.72)` + `backdrop-filter: blur(24px) saturate(1.5)` | dock, questions panel, menu (the blur is on the frame, in `content.js`: a page inside a frame can't blur what's behind it) |
| glass-solid | `rgba(18,18,20,.90)` | cards over video that have no blur behind them |
| edge / edge-2 | `rgba(255,255,255,.05)` / `.09` | inner borders, hairlines |
| inner | `inset 0 1px 0 rgba(255,255,255,.06), inset 0 0 0 1px rgba(255,255,255,.05)` | every floating surface |
| shadow | `0 24px 48px -16px rgba(0,0,0,.6), 0 4px 12px -4px rgba(0,0,0,.35)` | every floating surface |
| text / text-2 / text-3 | `#f4f5f7` / `#a1a1aa` / `#6b6b74` | primary, secondary, labels |
| cyan / blue / violet (now WhatsApp green / Spotify green / dark Spotify green) | `#25d366` / `#1db954` / `#168d40` | active states only |
| grad | `linear-gradient(135deg, #25d366 0%, #1db954 52%, #168d40 100%)` | the orb, "Ask her", the main button, the chosen language |
| amber | `#fbbf24` | warnings only |

Type: Manrope (bundled in `fonts/`, OFL), 400–800; Telugu in Noto Sans Telugu / Kohinoor Telugu. Labels are 10.5px,
700, +.08em, uppercase, text-3. Captions are 22px at 650 weight, with the earlier line shrunk to 16px at half opacity.

Color by meaning: cyan = connected and "Asked you"/"Request" tags; blue = selected or open; violet = sayings and "Ask her".

## Colors and type (same as the iPhone app)

Greens are the primary accents (WhatsApp green `#25d366`, Spotify green `#1db954`, deep `#168d40`). Muted lavender
`#b3a6d4` is the quiet third: question bubbles, the kind tag on meanings, the tail of the line and the "Ask her"
border. Surfaces are raised: lit from above (`--raised`), a bright top edge and a soft shadow (`--lift`). The words
themselves (word bubbles, the "Ask her" question, picture titles) are in Newsreader, a serif like the app's titles;
everything else is Manrope.

## Components

**Ask her (top pill).** This is a frosted glass pill (the blur is on its frame).
- Its 1.5px conic gradient border turns once every 5 seconds, over violet and cyan light.
- A gradient spark badge sits on the left.
- Next to it: the label, then what to say (18px, 800), then the Telugu and the English.
- A 2px line drains over the question's 45 seconds.
- It comes down from 18px above with a spring (`--spring`, 560ms) and leaves upward with `--ease-in`.

**Words (left).** Each word is its own raised bubble (no panel behind them): romanized word in the serif, English
under it, a green dot when she said it on this call. New bubbles pop in with a spring, one after another (70ms
apart, after the old ones have faded in 180ms), and every bubble drifts by 2px, out of step with the others.
Questions are lavender bubbles that open to their answer.

**Dictionary (left, before).** This is a frosted rail. Each word shows romanized in bold white (15px, 800), with its Telugu small and faint beside it and the English muted underneath.
- Words she said get a gradient bar and a "she said" tag.
- The hear button appears on hover.
- Rows keep their elements: new ones spring in, moved ones glide (FLIP with `translate3d`), and removed ones lift out.
- "Curious?" questions sit underneath, and their answers slide open.

**Word bubbles (float).** Pictures are pills with a round thumbnail and the name. Meanings are pills with a gradient kind tag.
- They spring in from 60% scale (`--spring`) out of the bottom-right corner.
- Hovering opens the picture and description. Clicking keeps a bubble (blue ring, no timeout).

**Translation bubble.** This is frosted glass with a fixed height, and its top edge fades out.
- The words update in place: each line keeps its element, and the draft firms up in place.
- A line that grows eases its height, and lines that come or go glide by their bottom edges.
- A new line waits 180ms so the one above can start moving.
- A thin line of the orb's gradient runs along the bottom, brighter while someone talks.

**Controls.** The status and all the buttons are 40px glass circles that spring out on either side of the orb on hover. The menu opens above the orb.

## The line

This line replaces the orb. It's a 240 × 56 canvas (drawn every frame, so there's no layout at all) showing two gradient strands (cyan → blue → violet), pinned at both ends and slightly out of step, so it reads like a vibrating string.
- **Real sound:** offscreen.js reads the captured tab's sound as 48 log-spaced bands from 80 Hz to 5 kHz, about 30 times a second. Low frequencies drive the middle of the line and high ones the ends.
- **Movement:** levels rise fast and fall slowly, and the glow grows with overall loudness.
- **No sound to read** (no capture, or the preview page): the line follows Weave's state instead. It's nearly flat when idle, ripples small and fast while translating, and moves more while someone talks or Weave speaks. When there's no engine it's a gray flat line.

## Motion

| Token | Curve | Use |
|---|---|---|
| ease-out | `cubic-bezier(.16, 1, .3, 1)` | arriving: cards, captions, tooltips |
| spring | `cubic-bezier(.34, 1.56, .64, 1)` | things popping in: bubbles, rows, the pill, the controls |
| ease-sheet | `cubic-bezier(.32, .72, 0, 1)` | panels, gliding rows, the orb growing |
| ease-in | `cubic-bezier(.7, 0, .84, 0)` | leaving |
| fast / med / slow | 140 / 260 / 420ms | hovers / small changes / panels |

- **Panels open:** opacity over 220ms (ease-out), and transform from `translateY(-10px) scale(.96)` over 420ms (spring), growing out from the dock.
- **Panels close:** 160–220ms with ease-in, then they're hidden.
- **Menu:** same as panels, 200/360ms in and 160/200ms out.
- **Cards arrive:** from `translateY(-8px) scale(.98) blur(4px)` over 420ms (ease-out).
- **Captions:** a new line rises 6px over 260ms. When talk stops they fade and drop 10px over 700ms (ease-in).
- **Buttons:** press to scale .92 over 140ms.

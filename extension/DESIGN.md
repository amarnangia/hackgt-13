# Weave design system

One system for the overlay (`panel.css`, `content.js`), the web app (`garden/web/index.html`), the iPhone app and
widget (`garden/ios/Shared/Theme.swift`) and the call summary pages (`calls.py`, `STYLE`).

## Layout over a call

A video call puts the other person's face in the middle, your own camera in a bottom corner and the call's buttons
along the bottom. Weave stays on the edges and only takes space while it has something to show.

| Zone | Where | Size | When it's there |
|---|---|---|---|
| Dock | top left, 16px in | 48px tall capsule | always (just the orb while hidden) |
| Questions and words | under the dock (top 78px) | up to 340 × 560, stops above where the caption words sit | opened from the dock |
| "Ask her" + pictures and meanings | top right, 16px in | 260–340px wide (26% of the window); ends 230px above the bottom, leaving room for your camera tile | only while there's something; "Ask her" is on top and opens this side by itself; the bottom 28px fades out |
| Captions | bottom middle, 104px above the bottom (clear of the call's buttons) | a fixed 820 × 230 box; the words move inside it, the box never moves | while someone talks; fades 9 s after the last words |

Each panel is its own frame, so it only covers the call where it actually is. The captions frame lets clicks through
while it's faded out.

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
| cyan / blue / violet | `#22d3ee` / `#4f8cff` / `#8b5cf6` | active states only |
| grad | `linear-gradient(135deg, #22d3ee 0%, #4f8cff 52%, #8b5cf6 100%)` | the orb, "Ask her", the main button, the chosen language |
| amber | `#fbbf24` | warnings only |

Type: Manrope (bundled in `fonts/`, OFL), 400–800; Telugu in Noto Sans Telugu / Kohinoor Telugu. Labels are 10.5px,
700, +.08em, uppercase, text-3. Captions are 22px at 650 weight, with the earlier line shrunk to 16px at half opacity.

Color by meaning: cyan = connected and "Asked you"/"Request" tags; blue = selected or open; violet = sayings and "Ask her".

## Components

**Dock.** It's a glass capsule holding the orb, a divider, and three 36px icon buttons (questions, pictures, ⋯).
- Hovering the dock opens its status label (max-width 0 → 240px). The label also shows for about 3 seconds when Weave connects or disconnects.
- An open panel's button is blue: `rgba(79,140,255,.18)` fill with a `.38` inner ring.
- New content in a closed panel shows a 7px gradient dot on its button.
- Tooltips appear after 350ms.

**Menu (⋯).** It's a glass popover under the dock. It holds the two-way "I speak" switch (a segmented control with a gradient for the chosen side) and "Hide Weave ⌥⇧W".

**"Ask her" (top right, in focus).** It's the one thing on screen that asks for attention.
- A 1.5px conic gradient border turns once every 5 seconds, with a blurred copy behind it as a glow.
- Violet and cyan light pools in the corners, behind a sparkle badge.
- Type goes from biggest to smallest: what to say (20px, 800), the Telugu, then the English.
- A 2px gradient line drains over the 45 seconds before the card leaves.
- It's drawn only when the question changes, so the border and timer never restart.

**Questions and words.** It's one glass panel, with its sections split by hairlines rather than boxed.
- "Curious?" answers slide open (grid rows 0fr → 1fr).
- Words she used get a cyan tint.

**Pictures and meanings.** Pictures are cinematic: the image runs edge to edge with its name over a dark gradient. Meanings have a gradient bar down the left. A kept card gets a blue ring. They fade over their last 8 seconds, then leave.

**Captions.** There's no box: a dark radial pool sits under the words, with the orb's colors drifting low and slow behind it (brighter while someone talks). Each line has a small speaker label (gradient dot + name), her words, then the English at 28px and weight 750.
- **Drawn in place.** Each line keeps its element and only its text changes. What she's saying right now becomes that line's element when the sentence ends, so nothing flashes.
- **The draft** (the English guessed so far) is gray and firms up to white in place.
- **English with no draft** writes itself in from the left, once.
- **Translating** shows three gradient dots.
- **When the current line changes height,** it grows or shrinks over 340ms and pushes the line above along with it.
- **When a line arrives or leaves,** the others glide to their new place (tracked by their bottom edges). The previous line shrinks to 74% at 40% opacity, and the line before that lifts away in 260ms.

## The orb

It's 28px: a turning conic gradient (cyan → blue → violet) under a highlight, with a soft glow behind it.

| State | When | Motion |
|---|---|---|
| off | no engine | grayscale, 55% opacity, still |
| idle | connected, quiet | breathes: scale .90 ↔ 1, opacity .6 ↔ .88, 4.2s ease-in-out; gradient turns once per 14s |
| listening | someone is talking | grows to 1.12 (spring); two blurred blobs morph and turn (2.6s and 3.4s, one reversed); glow grows to 1.15 |
| thinking | a line is being translated | gradient turns every .9s; a bright arc sweeps round the edge at the same speed |
| speaking | Weave's voice is playing | three rings go out (scale 1 → 1.75, fading out, 1.5s, .5s apart); core and glow follow a voice-like level every 110ms |

The page can't hear Weave's audio, so the speaking level is a smoothed random envelope (`--amp`). When reduced motion is on, the orb doesn't animate.

## Motion

| Token | Curve | Use |
|---|---|---|
| ease-out | `cubic-bezier(.16, 1, .3, 1)` | arriving: cards, captions, tooltips |
| ease-spring | `cubic-bezier(.32, .72, 0, 1)` | panels, menus, the dock label, the orb growing |
| ease-in | `cubic-bezier(.7, 0, .84, 0)` | leaving |
| fast / med / slow | 140 / 260 / 420ms | hovers / small changes / panels |

- **Panels open:** opacity over 220ms (ease-out), and transform from `translateY(-10px) scale(.96)` over 420ms (spring), growing out from the dock.
- **Panels close:** 160–220ms with ease-in, then they're hidden.
- **Menu:** same as panels, 200/360ms in and 160/200ms out.
- **Cards arrive:** from `translateY(-8px) scale(.98) blur(4px)` over 420ms (ease-out).
- **Captions:** a new line rises 6px over 260ms. When talk stops they fade and drop 10px over 700ms (ease-in).
- **Buttons:** press to scale .92 over 140ms.

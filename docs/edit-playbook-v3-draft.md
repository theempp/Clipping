# Edit Playbook (D114)

Shared by all streamer agents. Per-streamer weights start equal and are tuned by the learn pass.
**No clip is a template.** Approved clips add tools and weight; they are never copied whole (Zo, 2026-11-23: "I want every clip to be different").

## Shared core toolbox
| Slot | Tool | Use when | Notes |
|---|---|---|---|
| Opener | Cold hard cut on the line | default | hook in 3 s |
| Opener | Bloom clear (blur/overexposed clears in ~0.45 s) | game shot opens the clip | ref: Kai Cenat clip |
| Cut | Hard cut | default | no fades or wipes |
| Cut | Black-frame spacer 0.2-0.5 s | compilation, joke-to-joke | |
| Punchline | White flash + impact into B&W | absurd/cringe line | ref: Lacy cat clip; approved in v3 |
| Punchline | Eased slow-mo ramp 0.75>0.5>0.75x, motion-interpolated, light vignette | the line itself is the joke | never a hard 0.5x snap; approved in v3 |
| Punchline | Layout swap (full face / full game) | reaction or game peak | facecam must be big enough in source |
| Ending | Darken out ~0.6 s | reaction hold | ref: CaseOh clip; approved in v3 |
| Ending | Hard cut ~1 s after peak | default | |
| Audio | Impact (full-range: sub + transient + body) | punchline hit | the old lowpassed hit read as muffled; rejected |
| Audio | Whoosh | layout swap | |
| Audio | Music cue (ducked) | mock-serious beat | needs a real library; the synth pad was rejected |
| Captions | Headline box (Apple emoji) | every clip | |
| Captions | Word-by-word | speech carries the joke | A/B variant; refs use none |
| Flashback | VHS rewind + rewind SFX | agent proposes, Zo approves | never automatic (D113) |

Banned everywhere: zooms and punch-ins (D112), the synth music pad, the muffled hit.

## Variety rules (every clip)
- Pick one tool per slot (opener, punchline, ending) plus 0-2 audio tools, weighted by the streamer's weights.
- Never reuse the previous clip's opener + punchline + ending combo. No punchline treatment more than 2 clips in a row per streamer.
- 1 clip in 4 explores a low-weight tool.
- Headline text and emoji are always new to the clip.
- Store the chosen combo in the recipe so the next pick can check it.

## Per-streamer weights
Lacy: the v3 combo (bloom clear, flash+impact into B&W, eased slow-mo, darken out, word captions) was approved 2026-11-23, so each of those tools gets +1. Everything else stays at 1. Jynxzi and Stable Ronaldo: all 1, no bans yet. The learn skill raises a weight on approval or above-median performance, and lowers it on rejection, revision notes or manual removal.

## Rules every clip
Hook in 3 s. Headline box from frame 1 (font >= 60 px). 12-30 s default. Hard cut about 1 s after the peak unless the ending tool says otherwise. <= 3 flashes/s. Human approval always.

## Loop
Recipe -> render -> clip-qa -> review (approve / reject / note / manual edit) -> learn -> weights -> next recipe.

## Build status
Hand renderer: `C:\clip-work\renders\d114_render.py` + recipe JSON (segment keys speed/bw/flash_in/bloom_in/fade_out/layout; headline emoji_png; word_captions; sfx). Not yet a pipeline feature.

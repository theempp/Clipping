# Edit Playbook (D114)

Shared by all streamer agents. Per-streamer weights start equal and are tuned by the learn pass.

## Shared core toolbox
| Tool | Use when | Notes |
|---|---|---|
| Hard cut | default | no fades or wipes |
| Black-frame spacer 0.2-0.5 s | compilation, joke-to-joke | |
| Slow-mo + vignette | mock-serious punchline | no zoom |
| Music cue (ducked) | mock-serious or tense beat | under source audio |
| Whoosh / hit / glitch SFX | layout swap, reveal | 1-3 SFX per clip |
| Layout swap (full face / full game) | reaction peak or game punchline | |
| Flashback (VHS rewind + rewind SFX) | agent proposes, zo approves | never automatic (D113) |

Banned everywhere: zooms and punch-ins (D112).

## Per-streamer weights
Lacy, Jynxzi, Stable Ronaldo: each starts with all tools at weight 1 and an empty ban list. The learn skill raises a weight when a combo is approved without notes or performs above the streamer's median, and lowers it on rejection, revision notes, or manual removal. Keep the weights in each streamer's own note under `brain-graph/brain/Streamers/`.

## Rules every clip
Hook in 3 s. Headline box from frame 1 (font >= 60 px). 12-30 s default. Hard cut about 1 s after the peak. <= 3 flashes/s. Human approval always.

## Loop
Recipe -> render -> clip-qa -> review (approve / reject / note / manual edit) -> learn -> weights -> next recipe. 1 clip in 4 explores.

## Open
- Lacy's own playbook file was not found in the project files; merge any streamer-specific rules into her weights note.
- Build work: recipe JSON schema, tool library assets (SFX, music cues), weight store, manual editor page.

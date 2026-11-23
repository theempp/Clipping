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
| GTA stinger (Wasted, Busted, Mission passed/failed, Wanted level) | GTA 6 stream; fail, rage, clutch or funny peak | baked overlay on the peak, max 1 per clip, counts as a transition (D115) |

Banned everywhere: zooms and punch-ins (D112).

IRL / Just Chatting streams render full frame, face-tracked (MediaPipe), never a split layout and never a layout swap (D115). The crop pans with the face; it never zooms.

## Per-streamer weights
Lacy, Jynxzi, Stable Ronaldo: each starts with all tools at weight 1 and an empty ban list. The learn skill raises a weight when a combo is approved without notes or performs above the streamer's median, and lowers it on rejection, revision notes, or manual removal. Keep the weights in each streamer's own note under `brain-graph/brain/Streamers/`.

## Rules every clip
No combo repeats within a streamer's last 6 clips; no single look becomes the default (Zo: every clip different). Hook in 3 s. Headline box from frame 1 (font >= 60 px). 12-30 s default. Hard cut about 1 s after the peak. <= 3 flashes/s. Human approval always.

## Loop
Recipe -> render -> clip-qa -> review (approve / reject / note / manual edit) -> learn -> weights -> next recipe. 1 clip in 4 explores.

## How it runs (built, PR 11)
- `render/recipe.py`: recipe, validation, weighted picker, learn hook. `render/tools.py`: slow-mo plus vignette, black spacer, music duck, SFX mix. `render/sfxlib.py`: synthesized hit, glitch, whoosh, rewind (no licensed audio). `render/flashback.py`: proposal and VHS rewind render. Layout swaps live in `render/ffmpeg.py` (`swap`).
- Turn it on: set `extra.recipe_weights` (weights file path) in the worker config; optional `extra.music_cue_file`. Off by default.
- Learning: `Pipeline.learn_recipes()` runs every 60 s. A clip's final state (approved clean, approved after notes, rejected), negative notes naming a tool, and tools Zo removed in the editor move that streamer's weights. Two notes against a tool ban it for that streamer. Each clip is learned once (`clips.recipe_learned_at`).
- Flashback: the worker only PROPOSES (same streamer, earlier job, 3+ shared content words, source file still on disk). The editor shows the proposal; it renders only after Zo taps Approve. Viral clips from Kick, Twitch or X are never fetched by the tool: download one by hand and it can be named in a proposal.
- Editor: tool toggles (take a tool off a clip) and Approve or Drop flashback. The zoom slider is gone (D112).

## Open
- Licensed music library: the music cue needs a file Zo chooses. SFX are synthesized and need no licence.
- Lacy's own playbook file was not found in the project files; merge any streamer-specific rules into her weights note.
- Per-streamer toolbox notes under `brain/Streamers/` are not auto-written from the weights file yet.

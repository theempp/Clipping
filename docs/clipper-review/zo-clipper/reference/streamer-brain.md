# Streamer Brain (per-streamer learning)
Pro's brain, as seen on screen (4:27-4:50): "what their normal looks like", "words chat spams when it pops off", "which moments viewers actually clip", thumbs up/down, a streams-watched counter. The free engine's `detect.py` shows the mechanism: a small logistic model over per-second features, starting from prior weights, blended toward learned weights as positives accumulate (trust 0.6 -> 0.9 at ~150 positives). We build our own version.

## Files (per streamer, `streamers/<slug>/`)
- `brain.json`: feature weights, bias, baseline stats (median chat rate, loudness, laugh rate), chat-word lift table (token -> lift), counts (streams watched, positives, negatives), `updated`.
- `brain.md`: human-readable view of the same (what normal looks like, top chat words, best/worst clip types). Regenerated, never hand-edited.
- `playbook.md`: rules for this streamer (crop box, hook voice, layouts, banned topics, campaign rules).
- `learning.md`: dated lessons with evidence and keep/kill status.
- `experiments.md`: EXP-G#/EXP-R# with metric, sample size, kill condition, status.
- `scoreboard.csv`, `log.md`, `takedowns.md`.

## Features (all 0..2, vs this streamer's own rolling median/MAD)
chat burst · unique chatters · reaction-emote weight · laugh/shout/cheer sound events · loudness · facecam motion · game change rate · scene cut · chat mood shares (laugh, hype, shock) · chat-word lift. Baseline window 600 s (existing), plus a per-stream baseline stored between streams.

## Training signals (labels)
| Signal | Label | Weight |
|---|---|---|
| Zo approves clip | positive | 1.0 |
| Zo approves after revise | positive | 0.7 |
| Zo rejects | negative | 1.0 (store reason) |
| Viewer clipped within +/-20 s | positive | 0.6 |
| Posted clip beats 3x channel median at 24 h | positive | 1.5 |
| Posted clip < 20% of median at 24 h | negative | 0.8 |
| Zo hits CLIP THAT on a moment we missed | positive + `missed_moment` | 1.5 |
| Detector fired, no one cared (dropped by judge) | weak negative | 0.2 |

## Update rules
- Weekly (or every 25 labels): refit with L2 toward the prior; cap any weight change at +/-25% per update; keep the last 4 versions for rollback.
- Chat-word lift: token frequency in the 8 s after labelled positives / baseline frequency; keep tokens with lift >= 3 and >= 5 occurrences; drop emote spam that appears in every stream.
- Nothing from one streamer's brain ever initialises another (no taste transplant). New streamer = shared prior only.
- Any change to prompts, hooks or edit rules is an experiment with a metric and kill condition, not a silent edit. Zo approves rule changes.
- Cold start: first 3 streams = observe + score only, brain is "learning"; labels still collected.

# Moment scoring (0-100)
Replaces `score_10` in the judge output; keep `score_10 = round(score/10)` for the existing queue sort.
Idea source: Clipper (free) splits the score 50/50 between measured and judged. Ours is re-weighted for streams and for Zo's rules.

## Measured, 50 pts (code, free)
| Part | Pts | How |
|---|---|---|
| Peak intensity vs this stream | 15 | detector score percentile within the stream's own baseline |
| Hook speed | 15 | seconds from clip start to first strong signal (laugh, shout, chat burst, hype word); full marks <= 1.5 s |
| Length fit | 10 | 100% at 12-20 s, linear falloff to 0 at 8 s / 60 s; campaign min/max overrides |
| Reaction density | 10 | words/s plus hype words plus laugh/shout events inside the window |
Add (not in Clipper): `viewers_clipped` +5 (cap 100), `dead_air_ratio` > 0.3 -> -15.

## Judged, 50 pts (model, shortlist only, 0-10 each)
`hook` (stop the scroll in 1 s) · `payoff` (clear climax/punchline) · `standalone` (a stranger gets it cold) · `emotion` (shock, laugh, rage, hype) · `share` (the send test: name who gets it and what they type).
Strict: 9-10 = best of this streamer's month. Typical good clip = 60-80. Under 60 = drop or recut (later start, earlier end).

## Output schema (extends current judge JSON)
`score`, `parts{...}`, `why` (1 line), `hook_type`, `trim_in/out` (snap to word edges), `title`, `post_caption`, `hashtags[3-5]`, `send_test`, `badges[]`, `proof_frame_ts`.

## Calibration
Every approved/rejected clip stores its score. Weekly: compare score rank vs Zo's decisions; if Spearman < 0.3 after 30 decisions, retune weights (clip-detector-tuning) before touching prompts.

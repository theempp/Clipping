---
name: zo-clipper
description: Zo's own stream clipper: find, score, cut, check and hand off moments per streamer. Use when detecting, scoring or tuning clips for a roster streamer.
---
# Zo Clipper
Our own build of the ideas in Clipper Pro (no code copied). Code does detect/render/QA; the model only judges, titles and captions (D026). Never publishes: every clip ends at `pending_review` (D003/D042).
Wiring is behind `[features]` flags in `channels.toml` (score_100, dead_air_gate, brain, viewer_clips, clip_that, dry_run), all off by default. Read the streamer's folder first: `streamers/<slug>/{brain.md,playbook.md,learning.md}`. No folder = stop and ask.

## Loop (event-driven; runs while Wake Up is on)
1. **Watch.** Live poll fires `went_live` -> notify Zo -> start capture (existing `ingest/`, `capture/`).
2. **Gate dead air.** Skip starting-soon, BRB, ad, loading, menu, donation-alert, map-staring frames. Chat hype with idle screen = low score. See `reference/live-mode.md`.
3. **Detect.** Per-second features vs this streamer's own baseline: chat burst, unique chatters, mood shares, chat words from brain, loudness, laugh/shout sound events, facecam motion, game change rate, scene cut. Weights are the streamer's own (`brain.md`).
4. **Add viewer evidence.** Twitch viewer-made clips in the window: badge `viewers_clipped`; if we missed it, cut it. Manual `CLIP THAT` = last 40 s from the buffer.
5. **Judge shortlist only** (text + 3 frames, never full VOD): 0-100 score = 50 measured + 50 judged. See `reference/moment-scoring.md`. Drop < 60 or `standalone=false`.
6. **Cut + edit** per `reference/edit-grammar.md` and standing `edit_rules` (D078). Hook is a headline, not "STREAMER DOES X".
7. **QA** in code, then the checks in `reference/qa-gates.md` (proof frame, freshness, dedupe, send test).
8. **Hand off** to the review queue with score, reasons, badge, proof frame, send-test line.
9. **Learn.** On approve / revise / reject / viewer-clip / platform stats, update that streamer's brain and logs (`reference/streamer-brain.md`).

## Hard rules
- One streamer per run. Never read or write another streamer's folder.
- Skip a slot rather than ship a weak clip. Nothing is posted without Zo's approval.
- No invented words in captions. No leaks, spoilers, sexual content, slurs, real-world logos.
- Cache by content hash; reuse transcripts; delete raw sources > 24 h; stuck ffmpeg > 5 min = kill and log.
- Every number carries source + date. Missing = blank, never guessed.

## Outputs
`clips` row + `candidate_log` features + a line in `streamers/<slug>/log.md`. Report bad news plainly.

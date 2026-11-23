# Wiring plan (apply ONLY after Zo approves; nothing here is applied)
Every step is behind a config flag, off by default, and reversible with `git revert` or flipping the flag. Run from `C:\clip-work\Clipping`. Sizes are relative (S/M/L), not time estimates.

## Phase 0: shared foundations (S-M)
1. Copy `docs/clipper-review/zo-clipper/` -> `.claude/skills/zo-clipper/` (keep SKILL.md <= 60 lines). Add to D027 skill list.
2. Judge schema: add `score` (0-100), `parts`, `send_test`, `badges`, `proof_frame_ts`; keep `score_10 = round(score/10)` (files: `judge/grok.py`, `judge/heuristic.py`, `validate`).
3. Dead-air gate in `detector/` (`show_start`, `quiet` multiplier, frame rejects on shortlist). Replay-test on existing VODs via `detector/replay.py` before enabling.
4. Migration `…_clipper_labels.sql`: `clip_labels(clip_id, streamer, signal, weight, created_at)`, `post_stats(clip_id, platform, read_at, hours_since_post, plays, likes, shares, comments, saves, follows, source)`, `brain_versions(streamer, version, json, created_at)`. RLS owner-only like the rest.

## Phase 1: Lacy end to end (M-L)
5. `channels.toml`: add `agent = "lacy-agent"` and `state_dir = "streamers/lacy"` to Lacy; copy `streamers/_template/` -> `streamers/lacy/`.
6. Detector features per `streamer-brain.md`: laugh/shout/cheer sound events (CPU ONNX, licence checked first), facecam motion, game change rate, scene cut, chat mood shares, chat-word lift. Weights read from `brain.json`; fall back to the current fixed weights (chat 0.45 / unique 0.20 / reaction 0.15 / audio 0.20).
7. Viewer-clip poller: Helix Get Clips for the live window every 60 s (same app token as status poll); store timestamps only; badge + `clip_labels` positive 0.6.
8. CLIP THAT: dashboard button + Discord command -> worker `extract_window(now-40, now)`; labelled `missed_moment`.
9. Install `agents/lacy-agent.md` -> `.claude/agents/`. Dry run on a VOD: nothing posts.
10. New `brain.py` beside `rules.py`: label ingest, weekly refit, version snapshot, `brain.md` regeneration.

## Phase 2: Jynxzi and Stable Ronaldo (S each, after Phase 1 is stable)
11. Same as steps 5 and 9 per streamer. Crop boxes stay `layout_proposed` until Zo approves each.
12. Roster: set the other core streamers `active = false` for everyone except Lacy, Jynxzi and Stable Ronaldo (trio chosen by Zo 2026-11-22; D069 change = new decision, next free D-number). xQc stays on the bench: `bench/xqc-agent.md`. Jynxzi needs per-game baselines in `brain.json` (GTA 6 vs other) because he also streams chess, Siege and other games.

## Phase 3: analytics + learning loop (M)
13. Stats ingest: YouTube Analytics API (own channel), X API post metrics (check tier/cost before enabling, budget D012), TikTok manual entry in the existing panel (D074). Reads at 2 h, 24 h, 72 h into `post_stats`.
14. Scoreboard writer: `post_stats` -> `streamers/<slug>/scoreboard.csv` (share rate first). Stuck-post tripwire (< 20 plays at 1 h) raises a flag only; never auto-deletes.
15. Weekly learn job: one question per streamer; output to `learning.md`; rule changes are proposals that appear in the dashboard for Zo.

## Phase 4: dashboard (M)
16. Score ring with parts, `viewers clipped` badge, hype meter on `/live/[slug]`, CLIP THAT button, thumbs mapped to approve/reject labels, per-streamer brain card, experiments list.

## Not changed
Review gate (D042), 10 posts/day cap (D043), Wake Up (D055), TikTok long-form rules (D079-D083), budget (D012). No Clipper Pro purchase, no third-party code run.

## Decisions needed from Zo
1. ~~Trio~~ settled 2026-11-22: Lacy, Jynxzi, Stable Ronaldo (xQc bench).
2. ~~Approval gate~~ settled 2026-11-22: keep D003, every clip human-approved; no autopilot or trust mode.
3. ~~TikTok scope~~ settled 2026-11-22: manual upload of short clips (D074). Open point: D079-D083 (long-form Zwoclipp) not touched; Zo to say if it is replaced or runs alongside. Dashboard needs a per-clip TikTok handoff (download + caption + stats entry).
4. ~~Hook style~~ settled 2026-11-22: A/B both, headline vs payoff-first teaser, one variable; flash + whoosh stays off (D052). Needs a `hook_style` field per clip and an experiment row per streamer (EXP-G1), judged on share rate at 24 h with the sample size and kill condition written first.
5. ~~Cadence~~ settled 2026-11-22: go heavy to maximise exposure. Plan: ramp, not a switch. Days 1-3 about 4 posts/day/platform to confirm nothing sticks; then up to about 8/day/platform, at least 2.5 h apart, overnight gaps filled first (Kenji's current pace). Raise only if no stuck posts, no originality flags, and share rate holds. D043 cap of 10/day/destination stays unless Zo changes it. Real limits to check: Zo's review time (every clip is approved by hand), clips that pass QA (skip rather than ship weak), YouTube upload quota (UNVERIFIED: default API quota may allow only about 6 uploads/day without a quota increase), X API tier, TikTok manual uploads.

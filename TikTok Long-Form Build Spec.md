# TikTok Long-Form Build Spec

Written 2026-11-22. Implements D079 to D082 from [[TikTok Monetization Plan]]. Built 2026-11-22 for Zwoclipp only (D083); see the PR on branch claude/project-thread-pyo8qb. Run: `clipworker longform-once` on the PC. Build in Claude Code on `C:\clip-work\Clipping` (main), with tests, same approval gate as every platform.

## Goal

Turn judged moments into 60 s plus narrated videos that pass TikTok's originality rules, tag every test variable, and record results so the self-improvement loop can pick winners.

## Flow

```
detector -> judge (existing) -> clips (existing, 8-40 s)
                 |
                 v
        assemble (new) -> script (new, 1 model call) -> voice (new) -> render_long (new) -> qa_long (new) -> review queue -> manual TikTok upload -> stats entry (new)
```

Short clips keep flowing to YouTube Shorts and X unchanged. Long videos reuse the same judged clips; nothing is re-detected or re-transcribed.

## 1. Assemble (`worker/src/clipworker/longform/assemble.py`)

Code only, no model.
- Input: judged clips from the last 24 to 72 h with `score_10 >= 6`.
- Grouping per channel (D079):
  - `zwoclipp` (recap): one streamer, one stream or storyline, 2 to 5 clips, ordered by time.
  - `gta6` (top-N or storyline): game tag GTA 6, any of the 7 streamers, 3 to 5 clips ranked by `score_10`.
- Picks format and pacing from the test schedule (section 7), not at random.
- Target runtime: short-style 61 to 75 s, long-style 120 to 240 s. Raw clip time is 50 to 70% of runtime; the rest is narration, intro and cards. A plan that can't reach 61 s is dropped.
- Never reuses a clip already used in a long video on the same channel.
- Output: `longform_plans` row (see Data).

## 2. Script (`longform/script.py`)

The only model step. One call per video, the cheapest model that passes the check; Grok when the key is in, cached by content hash of the plan.
- Input: per clip the transcript window, judge `post_caption`, streamer name, 20 chat lines. No video, no full VOD.
- Output JSON: `hook` (first line, said in the first 2 s), `beats[]` (one narration line before or over each clip, adding context the clip doesn't show), `outro` (question to drive comments), `title`, `caption`, `hashtags`, `cards[]` (number cards for top-N).
- Code checks: narration covers at least 40% of runtime at 150 words a minute; no line copies the clip transcript; no invented facts (every claim must trace to transcript, chat or judge fields, otherwise the line is cut). Fail = regenerate once, then drop.

## 3. Voice (`longform/voice.py`)

- Mode `ai`: local TTS on the PC (no paid API at first). One fixed voice per channel. Video carries the AI label if TikTok asks for it.
- Mode `zo`: the dashboard shows the script with a record button; zo reads it; the file uploads to the job. Channel one only (cell V).
- Loudness: voice at -16 LUFS, source audio ducked under voice by 8 dB, back to full on the reaction peak.

## 4. Render (`longform/render_long.py`)

ffmpeg, reusing `render/ffmpeg.py`, `render/captions.py`, `render/motion.py`.
- 1080x1920, at least 1080p (CRP rule), source fps rules unchanged.
- Layout switching (cell L): `stacked` all through vs `switch` (full game on setup, stacked on build, full cam on reaction peak). Default `switch` until data says otherwise.
- Intro card 0 to 2 s with the hook as on-screen text; number cards between clips for top-N; end card with the outro question.
- Captions: style A or B per D073, tagged on the video.
- Crop boxes must exclude Twitch/Kick logos, alert boxes and other watermarks (originality rule).
- No music bed. Strip or mute copyrighted music in source where detected; credit the streamer in on-screen text and caption.

## 5. QA (`qa.py` gets `check_long`)

Blocks the queue on any fail:
- Duration over 60.5 s (safety margin over the 1 minute rule).
- Height at least 1920 and width 1080.
- Voice present for at least 40% of runtime (VAD on the voice track).
- Platform logo check: template match for Twitch and Kick logos in the crop area.
- No single clip runs longer than 25 s without narration or a card (avoids "largely repurposed" segments).
- Loudness and caption overflow checks as today.

## 6. Data (new migration)

- `longform_plans`: id, channel (`zwoclipp`/`gta6`), format (`recap`/`topn`/`explainer`/`extended`), pacing (`short`/`long`), caption_style (`A`/`B`), voice (`ai`/`zo`), layout (`stacked`/`switch`), clip_ids[], script jsonb, runtime_s, state.
- `tiktok_stats`: plan_id, posted_at, url, views, for_you_views, avg_watch_s, watched_full_pct, hold_5s_pct, follows, search_views_pct, qualified_views, rewards_usd, notice (`none`/`ineligible`/`unoriginal`), entered_at.
- Campaign clips get `sponsored = true` and the publisher refuses them for both TikTok channels (D081).

## 7. Test schedule (D082)

Code reads a schedule file, not the model.
- Weeks 1 to 2: each channel alternates formats x pacing, 2 posts a day. 6 posts per cell before judging.
- Weeks 3 to 4: lead format only; test caption A/B, then voice (channel one), then layout.
- Kill rule: 2 ineligible or unoriginal notices on a format disables it and alerts zo.
- Winner: follows per 1,000 views before Creator Rewards; RPM after; retention breaks ties.

## 8. Dashboard

- Queue card shows channel, format, pacing, caption, voice, layout tags and the script.
- Record button for voice mode `zo`.
- "Posted" button stores the TikTok URL and starts a 48 h reminder to enter stats.
- Stats form per video (fields from `tiktok_stats`), plus a small results table per cell.

## 9. Build order

1. Migration + `assemble` + tests (no model).
2. `script` with stub model + code checks + tests.
3. `voice` (AI mode) + `render_long` + `check_long`.
4. Dashboard tags, record button, stats form.
5. Dry run: 4 videos per channel into the queue for zo to review before the first post.

## Open items for zo

- Channel two name.
- Confirm both accounts are Personal and whether TikTok lets you enroll two accounts in Creator Rewards.
- Pick the AI voice from 3 samples once step 3 is built.

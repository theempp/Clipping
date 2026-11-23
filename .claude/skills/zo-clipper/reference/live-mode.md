# Live mode (what Clipper Pro does, mapped to what we have)
Pro facts are from the video (Money Mastery Hub, 3:19-5:08) and are tagged V; code-level detail for the free engine is from its public zip, read only (not run).

| Pro behaviour | Tag | We have today | Add |
|---|---|---|---|
| Watches the stream nonstop, clips while live | V | `ingest/status.py` poll 60 s, `capture/buffer.py` 10 s segments, 10 min rolling buffer, `detector/spike.py` | nothing; keep |
| Live dashboard, hype meter, render ETA | V | `heatStrip`, `PipelineTiles` on `/live/[slug]` | hype meter 0-100 per streamer, render ETA tile |
| Skips dead air: starting-soon, ad breaks, map-staring | V | none (chat-only gate: rate floor 0.5 msg/s) | `deadair` gate below |
| Chat hype != screen action | V | none | require 1 non-chat signal (sound event, cam motion, game change, cut) beside chat |
| Viewers clip a moment -> badge, cut if missed | V | none | poll Helix Get Clips for the live window; match to candidates by timestamp (+/-20 s) |
| Streamer Brain (normal, chat words, viewer clips, thumbs) | V | `candidate_log`, `edit_rules` | per-streamer weights + chat-word lift, see `streamer-brain.md` |
| CLIP THAT: last 40 s | V | buffer has 10 min | dashboard button + Discord command -> `extract_window(now-40, now)` |
| "finish my live clips" batch | V | pipeline renders as events arrive | not needed; queue already finishes itself |
| Runs in its own window, 0 Claude usage | V | worker already local | keep model off the hot path |

## Dead-air gate (code, no model)
- `show_start`: first 30 s window with >= 8 s of speech (sound-event classifier, CPU ONNX). Before it: starting-soon, never clip.
- `quiet`: no speech, laugh or shout within -20/+5 s -> multiply score by 0.3 (BRB, ads, menus).
- Frame checks on the shortlist only: loading screen, black frame, donation/alert card, map/inventory. Reject, log reason.
- Pro shows a donation alert and a loading screen being rejected (1:35 frame).

## Viewer-clip signal
Helix `GET /clips?broadcaster_id=&started_at=&ended_at=` (app token, same as status poll). A viewer clip is a vote that this second mattered; store `viewer_clip_ts`, `view_count`, `creator_id` hash. Never copy the viewer's clip file (their clip, not ours): use only the timestamp.

## Open questions
- Sound-event model: pick a permissive-licence ONNX audio tagger; verify licence before adding (the free skill ships YAMNet; we only reference the idea).
- Kick has no clip endpoint we trust (D041); live mode there = chat + audio only.

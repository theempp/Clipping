# QA gates (after render, before review queue)
Code checks stay in `clip-qa` (9:16, loudness -14 LUFS +/-2.5, peak <= -0.5 dBTP, 50 MB, duration, caption safe area). Add these Kenji-derived gates; each is pass/fail with a logged reason.

| Gate | Check | Where |
|---|---|---|
| Fresh | source window < 24 h old (live capture = always true; VOD cut records `vod_created_at`) | code |
| Proof frame | one saved frame with a game-only cue; GTA V is streamed under the GTA 6 tag, so category and title are not proof | model (1 frame) + saved path |
| Dedupe vs market | 3+ pages already posted the same moment on X / TikTok -> skip or new angle; check BEFORE render | code (X search needs API; else manual flag) |
| Send test | one line: who would a viewer send this to, what would they type. Empty = no clip | judge field |
| Facecam | real facecam with visible reaction; no VTuber/tiny cam | frame check |
| Hook frame | frame 0-1 s already shows face or action; text not over face | code + frame |
| End frame | ends on reaction/payoff, not loading screen or black | code |
| Foreign marks | no watermarks, chat overlay, black bars, viewer counters | code (edge/box checks) |
| Caption truth | every caption word traceable to speech or in-game caption | code (align confidence) |
| Banned content | sexual, animal cruelty, slurs, leaks, spoilers (launch week), real-world logos | judge + keyword list |
| Disk | no raw > 24 h; ffmpeg > 5 min = stuck | cron |

Rejects are logged with reason ("no facecam", "tiny cam", "story spoiler") so the scout skips them next time.
Skip rule: if nothing passes, the run produces nothing. No filler.

---
name: clip-qa
description: Automated checks on a rendered clip before it enters the review queue. Use after any render, before review.
---
# Clip QA
Run in code (ffprobe/ffmpeg), zero model tokens. Fail fast, report only failures.
- 9:16, target resolution, duration within the campaign's min/max, audio present and not clipping.
- Hook: first caption on screen within 3 s (`hook_s`). Text: caption font >= 60 px. No flashing: <= 3 flashes/s (WCAG 2.3.1). From video-director, D093.
- Captions: word timing within tolerance, no off-screen text, safe-area respected.
- Rules from the campaign record: required tags/mentions, watermark/source rules, banned content.
- Rights/permission flag present for the streamer; missing = block.
- Output: pass, or list of failed checks with timestamps. Pass sends to `pending_review`.

---
name: clip-render
description: Render a detected window into a 9:16 clip with whisperX word captions via ffmpeg. Use when building or changing the render step.
---
# Clip Render
ffmpeg is the core (D018). No Remotion, no model in this step. Visual values (font, colors, sizes) come only from `references/` (D022); empty = ask Zo.

1. Input: window from the buffer, trim in/out from the Grok judgment, streamer layout template.
2. Layout template per streamer (set once by hand, stored in config): facecam crop box on top, gameplay crop below, 1080x1920. Face tracking deferred.
3. Captions: whisperX word timestamps (cached by audio hash) -> ASS file, word-by-word highlight, inside safe area -> burn with ffmpeg `ass` filter.
4. Audio: loudnorm to about -14 LUFS integrated, true peak <= -1 dBTP.
5. Export: H.264 high, yuv420p, 30 or 60 fps matching source, AAC 48 kHz. Write thumbnail at the hook frame.
6. Output to `C:\clip-work\renders\<clip_id>\` with a manifest (source, window, template, caption version).
7. Always run clip-qa next. Re-render only the changed step on a revise note.

If ffmpeg-skill passed repo-audit, its 9:16, caption, silence and loudness tools may replace steps 2-4; nothing else from it.

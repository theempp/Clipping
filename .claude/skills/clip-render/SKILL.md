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

## Zo's edit rules (every clip, every streamer)
- **No zooms, ever (D112).** No punch-ins, zoom-outs or drift push. `[zoom] scale = 1.0, drift = 0.0` and the standing `edit_rules` row `zoom = false`. Never switch zoom back on unless Zo says so.
- **Tight hook (D113).** Open right before the line that makes the joke land (e.g. "Wait, what does BBL stand for?"), not on the setup.
- **Flashback transition (D113).** Hook first, then a hard rewind into the moment that explains or calls back to it: ~1.2 s fast reversed frames, VHS look (RGB split, noise, tracking bars, camera shake, white flash in/out), and a tape-rewind sound made from the skipped audio reversed and sped up, plus a short noise riser. Loudness-normalise after. Best callback source: the same topic elsewhere in this stream or the streamer's viral clips; fall back to the setup line. Reference build: commit notes for D113 in `Decision Log.md`.
- Keep it short: hook + flashback + payoff, about 12-20 s.

If ffmpeg-skill passed repo-audit, its 9:16, caption, silence and loudness tools may replace steps 2-4; nothing else from it.

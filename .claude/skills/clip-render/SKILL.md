---
name: clip-render
description: Render a detected window into a 9:16 clip from an edit recipe (layout, headline, captions, tools) via ffmpeg. Use when building or changing the render step.
---
# Clip Render
ffmpeg is the core (D018). The model only writes the recipe (D114); code renders it. Visual values (font, colors, sizes) come only from `references/` (D022); empty = ask Zo.

1. Input: window from the buffer, trim in/out from the Grok judgment, streamer template, edit recipe.
2. Recipe (JSON, stored in the manifest): layout, headline, caption_style (headline | headline+words), tools[], music/sfx, flashback, length. The editing agent picks 3-5 tools from the shared toolbox using the streamer's weights and bans, never the same combo twice in a row; 1 clip in 4 explores a lower-weight combo.
3. Layout: split, cam top ~42%, game bottom ~58%, 1080x1920, headline on the seam. May swap to full face or full game at the peak. Face tracking deferred.
4. Headline: white rounded box, bold black text, one emoji, font >= 60 px, on screen the whole clip. Word captions (whisperX word timestamps -> ASS, cached by audio hash) only when caption_style says so (D073 A/B).
5. Tools: hard cuts default; black-frame spacers (compilations); slow-mo plus vignette on a punchline; mock-serious music cue ducked under source; whoosh/hit/glitch/rewind SFX. 1-3 per clip. NO zooms or punch-ins (D112).
6. Flashback is never automatic. Render it only when the recipe has one that zo approved: VHS rewind, heavy effects, rewind SFX (D113), <= 3 flashes/s.
7. Length 12-30 s default. Hook within 3 s. Hard cut about 1 s after the peak.
8. Audio: source primary, loudnorm about -14 LUFS, true peak <= -1 dBTP.
9. Export: H.264 high, yuv420p, 30 or 60 fps matching source, AAC 48 kHz. Thumbnail at the hook frame.
10. Output to `C:\clip-work\renders\<clip_id>\` with a manifest (source, window, template, recipe, caption style).
11. Run clip-qa next, then review. Re-render only the changed step on a revise note.
12. Learning: every approve, reject, revision note and manual editor change is passed to the `learn` skill, which updates that streamer's tool weights. See `Edit Playbook.md` (repo root).

If ffmpeg-skill passed repo-audit, its 9:16, caption, silence and loudness tools may replace steps 3-8; nothing else from it.

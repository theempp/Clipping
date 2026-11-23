---
name: clip-render
description: Render a detected window into a 9:16 clip from an edit recipe (layout, headline, captions, tools) via ffmpeg. Use when building or changing the render step.
---
# Clip Render
ffmpeg is the core (D018). The model only writes the recipe (D114); code renders it. Visual values (font, colors, sizes) come only from `references/` (D022); empty = ask Zo.

1. Input: window from the buffer, trim in/out from the Grok judgment, streamer template, edit recipe.
2. Recipe (JSON, stored in the manifest): layout, headline, caption_style (headline | headline+words), tools[], music/sfx, flashback, length. The editing agent picks 3-5 tools from the shared toolbox using the streamer's weights and bans, never the same combo twice in a row; 1 clip in 4 explores a lower-weight combo.
3. Layout: split, cam top ~42%, game bottom ~58%, 1080x1920, headline on the seam. May swap to full face or full game at the peak. IRL / Just Chatting category = full frame, face-tracked with MediaPipe (pans, never zooms; Haar fallback) (D115).
4. Headline: white rounded box, bold black text, one emoji, font >= 60 px, on screen the whole clip. Word captions (whisperX word timestamps -> ASS, cached by audio hash) only when caption_style says so (D073 A/B).
5. Tools: hard cuts default; black-frame spacers (compilations); slow-mo plus vignette on a punchline; mock-serious music cue ducked under source; whoosh/hit/glitch/rewind SFX; GTA stinger on GTA 6 peaks (baked overlay, `ops/stingers`, D115). 1-3 per clip. NO zooms or punch-ins (D112).
6. Flashback is never automatic. Render it only when the recipe has one that zo approved: VHS rewind, heavy effects, rewind SFX (D113), <= 3 flashes/s.
7. Length 12-30 s default. Hook within 3 s. Hard cut about 1 s after the peak.
8. Audio: source primary, loudnorm about -14 LUFS, true peak <= -1 dBTP.
9. Export: H.264 high, yuv420p, 30 or 60 fps matching source, AAC 48 kHz. Thumbnail at the hook frame.
10. Output to `C:\clip-work\renders\<clip_id>\` with a manifest (source, window, template, recipe, caption style).
11. Run clip-qa next, then review. Re-render only the changed step on a revise note.
12. Layout swap (`swap_full_face` / `swap_full_game`): cropped, never zoomed, at the peak. SFX (hit, glitch, whoosh) are synthesized and mixed last at times remapped for slow-mo and flashback. Flashback renders only after Zo approves the proposal in the editor.
13. Learning: every approve, reject, revision note and manual editor change is passed to the `learn` skill, which updates that streamer's tool weights. See `Edit Playbook.md` (repo root).

## Zo's edit rules (every clip, every streamer)
- **No zooms, ever (D112).** No punch-ins, zoom-outs or drift push. `[zoom] scale = 1.0, drift = 0.0` and the standing `edit_rules` row `zoom = false`. Never switch zoom back on unless Zo says so.
- **Tight hook (D113).** Open right before the line that makes the joke land (e.g. "Wait, what does BBL stand for?"), not on the setup.
- **Flashback transition (D113).** Hook first, then a hard rewind into the moment that explains or calls back to it: ~1.2 s fast reversed frames, VHS look (RGB split, noise, tracking bars, camera shake, white flash in/out), and a tape-rewind sound made from the skipped audio reversed and sped up, plus a short noise riser. Loudness-normalise after. Best callback source: the same topic elsewhere in this stream or the streamer's viral clips; fall back to the setup line. Reference build: `worker/scripts/flashback_bbl_example.py`.

- Length follows D114 (12-30 s default), not a fixed 12-20 s.

If ffmpeg-skill passed repo-audit, its 9:16, caption, silence and loudness tools may replace steps 3-8; nothing else from it.

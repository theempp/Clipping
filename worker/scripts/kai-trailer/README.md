# Kai Cenat movie-stream clips (2026-11-23)

Hand-made clips from zo's screen recording of Kai's scripted crime-movie stream.
Kai = the guy in the #3 CENAT jersey, not the shirtless talker.

- `transcribe.py`: whisperX large-v3 on the audio (set `NLTK_DATA` outside the user folder or alignment fails).
- `render.py clip_<name>.json`: 9:16, letterboxed band (crop 1790:852:0:48 hides viewer count, chat, sub counter, minimap), white headline in the top bar (`|` = line break), optional fade in/out, source audio at -14 LUFS. Source is full range: it converts to TV range, or the fades turn the black bars grey.
- `queue_upload.py`: QA + upload as `pending_review`. Sets `manifest.video`; the publisher needs it (first post failed with `KeyError: 'video'` without it).

Outcome: cold open (v6, "Kai Cenat is really turning his streams into movies") posted to YouTube Shorts as https://youtube.com/shorts/V4R7vBGboPg. On-point rejected. Trailer and bag not queued.

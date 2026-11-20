---
name: clip-detector-tuning
description: Tune chat-spike and audio clip detection thresholds per channel. Use when detector output has too many/few or poor clips.
---
# Clip Detector Tuning
Model: short burst (5s) vs sustained (30s) chat rate against a per-channel rolling baseline (design reference: hamzaskewl/clippy, MIT, unverified in use).
1. Pull stats, not transcripts: precision (approved/flagged), misses (manual clips not flagged), clips/hour, per channel.
2. Change one threshold at a time; replay on stored VOD chat (no live rerun, no model call) and compare.
3. Detector is pure code. The model only classifies the top-N candidate windows, with a ~20s text window plus chat sample, never full VODs. Transcribe locally (faster-whisper).
4. Kick chat/ingest is thin: verify separately before relying on it.
5. Log result via `learn`.

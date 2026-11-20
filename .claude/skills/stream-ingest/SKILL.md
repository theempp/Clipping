---
name: stream-ingest
description: Ingest Twitch and Kick live chat, live video buffer and VOD chat on one clock for the detector. Use when building or debugging capture.
---
# Stream Ingest
Only streamers permitted by an active campaign record (D016). No permission = no capture.

Live video: streamlink -> ffmpeg 10s segments in `C:\clip-work\buffer\<channel>\`, keep last 10 min, delete older.
Audio signal: ffmpeg ebur128 momentary loudness, 1s steps, same clock.

Chat:
- Twitch live: anonymous read-only IRC WebSocket (justinfan nick). No user token.
- Twitch status: EventSub stream.online/offline.
- Kick live: official Kick API chat webhook (verify event name + payload in KickEngineering/KickDevDocs before coding). Fallback: public chat WebSocket, read-only, marked unofficial, may break.
- Twitch VOD: TwitchDownloaderCLI chatdownload -> JSON -> same message table.
- Kick VOD chat: no supported route; V1 is live-only for Kick.

Rules:
1. Every message, loudness sample and segment carries one monotonic timestamp. Log clock drift.
2. Store messages in SQLite (channel, ts, user, text). Never send raw logs to a model.
3. Reconnect with backoff; write gaps as explicit gap rows, not silence.
4. Prevent PC sleep only while monitoring (SetThreadExecutionState).
5. Max 3 channels until CPU/GPU is measured.

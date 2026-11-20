# clipworker (backend)
Runs on Zo's PC while it is on (D013). Code does detection, capture, QA, state and rendering; Grok only judges the shortlist (D026).

```
ingest (Twitch IRC / Kick chat, streamlink+ffmpeg buffer, ebur128 loudness)
  -> detector (5 s burst vs 10 min baseline, unique chatters, reactions, audio)
  -> rights gate (active campaign only, D016)
  -> capture window -> whisperX words (cached) -> Grok judge (cached, text only)
  -> 9:16 render + ASS captions -> clip-qa -> Supabase `pending_review`
  -> Zo approves in dashboard (RPC) -> publisher -> YouTube Shorts + X
  -> posted -> 30-min Content Rewards countdown (DB trigger, D025)
Discord bot (own server, followed channel) -> campaign drafts (D024)
```

## Layout
| Path | What |
| --- | --- |
| `src/clipworker/detector/` | spike scoring, replay/eval on TwitchDownloader chat, dedupe |
| `src/clipworker/ingest/` | Twitch IRC (anonymous), Kick chat, live status polling |
| `src/clipworker/capture/` | segment buffer, window extraction, loudness parse |
| `src/clipworker/render/` | ASS captions, ffmpeg 9:16 graph |
| `src/clipworker/qa.py` | clip-qa checks (ffprobe/ebur128, rules, rights) |
| `src/clipworker/pipeline.py` | restart-safe job stages + revise loop |
| `src/clipworker/publish/` | YouTube resumable upload, X chunked upload, idempotent runner |
| `src/clipworker/campaigns/` | brief parser/scorer, Discord bot |
| `../supabase/migrations/` | schema, state guard, audit, RLS, RPCs, storage, realtime |

## Setup (PC, after Install and Detector Plan Phase 0-2)
1. `cd C:\clip-work\worker` (copy of this folder), `uv venv -p 3.11`, install CUDA 12.8 torch, then `uv pip install -e .[transcribe,discord]`.
2. Copy `.env.example` to `.env`, fill keys. Copy `config/channels.example.toml` to `config/channels.toml`.
3. Apply `supabase/migrations/*.sql` to the Supabase project; add Zo's auth user id to `owners`; add `streamers`, `destinations`.
4. `clipworker check`, then `clipworker replay <chat.json> --labels moments.txt` until the eval passes (recall >= 80%, <= 10 candidates/h). Only then `clipworker live`.

## Tests
`uv pip install -e .[dev] && pytest` (renders real clips with ffmpeg; SQL checks run if a local Postgres exists: `../supabase/tests/run.sh`).

## Blocked on Zo / unverified before going live
- `caption_style`: D048 (locked) from the Stage refs is in the example config. Per-streamer `layout` crop boxes set by hand from a stream frame. Render refuses without a style.
- Kick: official API payload names and the public Pusher chat path are unverified; live-only in V1.
- YouTube/X endpoint shapes, quotas and prices: re-check docs right before the first live post (publish-approval-gate step 5).
- `GROK_MODEL`: choose the cheapest model that passes the labeled eval set.
- D019: real campaign briefs/rules.

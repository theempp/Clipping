# Tools and Repos
Links: [[clipping]] · [[Agent Workflow]] · [[Campaign Intelligence]] · [[Research Agenda]]

Found 2026-11-20 via search. Licenses, stars, maintenance and current behavior are NOT verified; open each repo before adopting. Use as reference or starting parts, not as trusted dependencies.

## Clip detection from live/VOD
- github.com/hamzaskewl/clippy — chat-spike detector (5s burst vs 30s sustained, per-channel baseline) then AI classification. Twitch-focused. Best match for our detector design.
- github.com/nirvagold/stream-clipper — desktop app, audio + chat spike detection (Tauri/Rust/Svelte).
- clipsmith (PyPI clipsmith-ai) — faster-whisper + chat replay + LLM pick + ffmpeg 9:16.
- HotClip (AGPL-3.0) — VOD to vertical clips with captions, resumable.
- Kick support is thin everywhere; verify Kick chat/ingest separately.

## Reframe and captions
- github.com/iyashjayesh/FynCut — WhisperX word timing, face-tracked 9:16, word-by-word captions (uses Gemini + serverless GPU, not fully local).
- github.com/NaufalRizqullah/opensource-clipping — MediaPipe face tracking, karaoke .ASS captions, Whisper + Gemini.
- github.com/r2hu1/skate — fully local: faster-whisper, Ollama, OpenCV, ffmpeg.
- github.com/jurczykpawel/captions-cli (MIT) — word-level karaoke captions via local Whisper + libass.

## Publishing
- Postiz (github.com/gitroomhq/postiz-app, AGPL-3.0) — self-hosted scheduler with API; X, YouTube, TikTok, Instagram. Possible later route for TikTok/Reels.
- TryPost (github.com/trypostit/trypost, AGPL-3.0) — scheduler with MCP server.

## CapCut
- CapCut Mate (github.com/Hommy-master/capcut-mate), pyJianYingDraft/pycapcut — draft generation; export via Windows UI automation. Optional polish only (D018).

## Discord monitoring for Reach campaigns (proposed, not built)
- Do NOT use a user token or self-bot: Discord forbids automating a normal user account and may terminate it. Do not scrape Whop/Content Rewards (Whop guidelines bar bots).
- Allowed routes: (1) Reach admins add a read-only bot to the campaigns channel; (2) if the channel is an announcement channel, follow it into our own private server (Discord delivers it as a webhook; delays reported) and let our bot read our server; (3) manual paste of briefs; (4) monitor @ReachClipping on X via API.
- Proposed agent: "Campaign Scout" (Grok, function calling). Input: messages from our own server/channel. Output: structured campaign record (streamer, CPM, cap, deadline, platforms, rules, source link), score, alert. Never joins or submits anything itself.
- Grok cannot connect to Discord itself; a small discord.py bridge bot is required.

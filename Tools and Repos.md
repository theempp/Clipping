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

## 2026-11-20 — Integration research for the Review Dashboard (research only, nothing built or connected)
V = Verified on official docs, accessed 2026-11-20. A = Assumption or third-party source; check before building. No credentials are stored here.

### Already connected to Claude (checked 2026-11-20)
- Connected: Supabase, Vercel, Figma, Higgsfield/Higgser, Plaud. Not connected: Base44, GoDaddy, Wispr Flow (incomplete).
- Plugins enabled: none. Available in directory: official Supabase plugin, Vercel plugin, Discord plugin (a chat bridge for talking to Claude from Discord, not a campaign monitor; its server failed to connect this session).
- Skill search for clipping/upload/ffmpeg/PWA: nothing new to add.
- Connectors seen but not recommended now: Typefully (X only, no YouTube), Zapier/Windsor.ai (extra paid layer), Cloudflare (keep as fallback), vidIQ (research only).

### Correction to Research Agenda
- YouTube videos.insert now costs 1 unit in a separate "Video Uploads" bucket; default 100 uploads/day plus 10,000 units for other calls. Docs say uploads from unverified projects are NOT forced private. Supersedes the older "1,600 units, ~6 uploads/day" note. (V: developers.google.com/youtube/v3/docs/videos/insert, /determine_quota_cost, updated 2026-11-12)

### Ranked findings
| # | Item | Unlocks | Access Zo grants | Cost | Risk / ToS | Status |
|---|---|---|---|---|---|---|
| 1 | Supabase (connected) | Database, login, realtime sync PC↔phone, storage for approved clips, signed expiring download links | Already connected; later a project + keys kept in env files only | Free: 1 GB storage, 50 MB/file, 5+5 GB egress, pauses after 1 week idle. Pro $25/mo: 100 GB, 250 GB egress, $0.09/GB after | Free pause would break the phone; keep clips under 50 MB or go Pro | V: supabase.com/pricing |
| 2 | Vercel (connected) | Hosts the dashboard web app/PWA at a private URL | Already connected; link GitHub repo | Hobby $0; Pro $20/mo | Hobby is for non-commercial use, and clipping for pay is commercial, so Pro or Cloudflare Pages | A (Vercel fair-use terms not re-read today) |
| 3 | YouTube Data API (direct) | Auto-upload Shorts | Google Cloud project + OAuth consent on Zo's channel | Free; 100 uploads/day default, audit form for more | Must follow YouTube API Services Terms; audit needed only to raise quota | V |
| 4 | X API (direct, pay-per-use) | Auto-post video to X | X developer account, prepaid credits, OAuth on posting account | Post $0.015; post containing a URL $0.20; media upload price not listed | Video up to 20 min / 8 GB (non-Premium); no posting cap listed, 3M reads/mo | V: docs.x.com pricing, media |
| 5 | Twitch EventSub | Instant "streamer went live/offline" for green glow + auto-start; chat events for spike detection | Twitch developer app (free). Chat needs Zo's Twitch account token | Free | stream.online needs no broadcaster consent; chat via app token also needs channel:bot from broadcaster, so use Zo's user token | V: dev.twitch.tv/docs/eventsub |
| 6 | Kick public API | Livestream status + chat message webhooks | Kick developer app | No price stated | Event names/payloads not yet confirmed; Kick support thin in repos | V that API exists (KickEngineering/KickDevDocs); details A |
| 7 | Stream ingest (streamlink + ffmpeg) | Recording the live video on the PC | None | Free | Use only campaign-permitted streamers/footage (D016); platform ToS on recording third-party streams not yet checked | A |
| 8 | Discord campaign monitoring | New Reach campaign alerts → Campaign Scout | Zo's own bot + private server | Free | Self-bots/user tokens forbidden (V: support.discord.com/hc/articles/115002192352). Routes: (a) Reach admins add our read-only bot; (b) "Follow" their announcement channel into our server (needs Manage Webhooks in our server; posts arrive via a Channel Follower webhook; feature still labelled experimental; role mentions stripped); (c) manual paste. Message Content intent is self-toggled under 10,000 users | V: docs.discord.com webhook + intents docs; whether Reach's channel is followable is A |
| 9 | Whop bounties API | Official list of bounties and submitting a post URL | Whop user OAuth with bounty:submission:create (account API keys cannot submit) | Free | Not confirmed that Content Rewards/Reach campaigns are "bounties"; no documented clipper API for Content Rewards. No scraping, no timing bots (Content Rewards rules) | V endpoints exist (docs.whop.com/api-reference/bounty-submissions); fit A |
| 10 | Postiz (later) | One API for X, YouTube, TikTok, Instagram | Self-host still needs Zo's own X/YouTube developer apps; cloud uses theirs | Self-host free (AGPL-3.0); cloud subscription, price not read | 90–100 post requests/hour; adds a layer over the direct APIs | V: docs.postiz.com, repo README |
| 11 | Cloudflare R2 (fallback) | Clip storage with free egress | Cloudflare account | 10 GB free; $0.015/GB-mo; egress free | Needs custom domain for production access | A (Upstash KB summarizing Cloudflare pricing) |

### Phone download (D021)
- Plan: approved clip uploads to private storage, dashboard shows a signed expiring link plus an inline video player.
- iOS caveat still open: WebKit bug 275288 (installed PWA not downloading) remains listed; fallback is open in Safari or long-press the video to save. Must test on Zo's actual phone. (A)

### Proposed minimal starting set (not approved)
Supabase + Vercel (both already connected) for the dashboard, sync and phone download; direct YouTube Data API and X API for posting; Twitch EventSub + Kick API for live status; a small Discord bot in Zo's own server; Content Rewards submission done by Zo by hand with the dashboard's 30-minute countdown. Rough recurring cost: $0–45/mo for hosting/storage plus about $5–60/mo for X posts at 300/mo depending on URLs, leaving most of the $100–250 budget for Grok and transcription.

Sources: developers.google.com/youtube/v3 (videos.insert, determine_quota_cost, quota_and_compliance_audits) · docs.x.com/x-api (pricing, media, post-cap) · dev.twitch.tv/docs/eventsub · github.com/KickEngineering/KickDevDocs · docs.discord.com/developers (webhook, privileged intents) · support.discord.com (channel following, self-bots) · docs.whop.com (content rewards, bounties) · supabase.com/pricing · docs.postiz.com · github.com/gitroomhq/postiz-app · upstash.com/kb (R2) · bugs.webkit.org/show_bug.cgi?id=275288

## Token-saving and skills stack (2026-11-20)
Verified via GitHub API (stars, license, last push only; code not audited).
- Installed project skills (`.claude/skills`): impeccable, apple-design (kes); stageshow (AIA) for video breakdowns; learn (rewritten from Roblox pattern); caveman, investigate-first (JuliusBrussee/caveman, Apache-2.0).
- Custom skills: campaign-scout, clip-detector-tuning, publish-approval-gate, clip-qa, video-breakdown.
- Skipped: caveman-compress (sends file text to model provider).
- rtk 1.2.1 (rtk-ai/rtk, Apache-2.0): installed via winget; global hook `rtk hook claude` confirmed in settings.json; active from next session. Check with `rtk gain`.
- context-mode 2.2.1 (mksglu, Elastic License 2.0, source-available): installed as user plugin.
- Reference only, not installed: supabase/agent-skills (MIT), vercel-labs/agent-skills, anthropics/skills, remotion-dev/skills. Licenses unreported on some; check before copying.
- Token policy lives in `CLAUDE.md`.

## Top 10 newer / more-starred repos and skills (2026-11-20)
Stars, created/last-push dates and license from the GitHub search API on 2026-11-20. "Fit" lines are from READMEs, not code audits (A). Compare: the older list above sits at 0–463 stars (clippy 10, stream-clipper 5, skate 23, captions-cli 0, opensource-clipping 463).

| # | Repo | Stars | Last push | License | What it is / fit |
|---|---|---|---|---|---|
| 1 | [haziqahmedqasmi/PeakCut](https://github.com/haziqahmedqasmi/PeakCut) | 1.4k | 2026-11-17 | MIT | Twitch/Kick/YouTube link or live stream to 9:16 clips; live rolling buffer clipped by loudness + chat + transcript; word captions; Grok supported; posting with daily caps. Closest match to our whole design. Caution: repo created 2026-11-14, star count rose very fast (possible inflation), audit before use. |
| 2 | [zhouxiaoka/autoclip](https://github.com/zhouxiaoka/autoclip) | 11.7k | 2026-11-20 | MIT | Desktop app: one link to clips with subtitles, covers, post copy. Podcast/talk focus, Chinese-first; no chat-spike detection. Reference for pipeline and UI. |
| 3 | [Anil-matcha/AI-Youtube-Shorts-Generator](https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator) | 6.3k | 2026-11-12 | MIT | Long video to Shorts: highlight detection, face auto-crop, captions. Good reference for reframe + caption steps. |
| 4 | [FujiwaraChoki/supoclip](https://github.com/FujiwaraChoki/supoclip) | 3.7k | 2026-11-20 | SupoClip Noncommercial (not OSI) | Scores moments from podcasts/stream VODs, face-centred 9:16, word-synced subtitles, hook titles. License allows individual creators incl. monetized channels; companies/agencies need permission. Reference only unless license fits. |
| 5 | [m-bain/whisperX](https://github.com/m-bain/whisperX) | 25.5k | 2026-11-12 | BSD-2-Clause | Word-level timestamps + diarization. Core caption component (FynCut uses it). |
| 6 | [lay295/TwitchDownloader](https://github.com/lay295/TwitchDownloader) | 4.1k | 2026-11-15 | MIT | Twitch VOD/clip + chat download/render. Chat JSON feeds spike detection on VODs; chat render for overlays. Twitch only. |
| 7 | [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) | 8.5k | 2026-11-20 | MIT | Claude Code skill / MCP: 42 local ffmpeg tools (9:16 fit-crop, karaoke captions, silence removal, loudness check). Fits "code/ffmpeg does rendering + QA". Created 2026-09-03; fast star growth, check. |
| 8 | [ColinGPT9/clips-studio](https://github.com/ColinGPT9/clips-studio) ("Clips Kitty") | 474 | 2026-11-20 | AGPL-3.0 | Local PC clipper for chatting/gaming/sports streams (GTA examples), Windows Store build. Gaming-stream fit; AGPL means reference, not embed. |
| 9 | [AgriciDaniel/claude-shorts](https://github.com/AgriciDaniel/claude-shorts) | 447 | 2026-07-11 | MIT | Claude Code skill: long-form to short-form with Remotion-rendered captions. Skill pattern reference. |
| 10 | [nateherkai/herk-edit-kit](https://github.com/nateherkai/herk-edit-kit) | 3.0k | 2026-10-14 | Not stated (NOASSERTION) | 15 Codex/Claude Code editing skills: silence cut, captions, hooks, short-form rules. Talking-head focus; borrow caption/hook rules. Check license before copying. |

Also seen, not ranked: iamajmeena/neonclipping (736 stars, created 2026-11-19, too new to trust), RafaelGodoyEbert/ViralCutter (505, GPL-3.0), artbyjazi/autoclip (471, MIT, MediaPipe speaker-tracked 9:16, inactive since 2026-08-01), bridge-mind/bridgeclip (476, MIT), OpenMontage (81.8k, AGPL-3.0, general agentic video production, too broad).

## 2026-11-22: Cole Medin edit-video audit
- coleam00/skills `edit-video` at commit `8c30da9`, MIT. Verdict: **fail, reference only**. Not installed or run.
- Blockers: optional torch 2.8.0 (GHSA-63cw-57p8-fm3p, fixed 2.10), `shell=True` string interpolation in render/finalize/export, unpinned `npx hyperframes` and GSAP from CDN without integrity.
- Re-audit only after those are fixed upstream, in an isolated test. Clone deleted; re-clone at the pinned commit if needed.

## 2026-11-22: TwitchDownloaderCLI audit (light mode)
- lay295/TwitchDownloader CLI release `1.56.5` (published 2026-07-20), MIT, repo since 2019-08-26, 4.1k stars. Asset `TwitchDownloaderCLI-1.56.5-Windows-x64.zip` sha256 `8b1b0695f2b1b6bf0d2535fab4b84032951cded8cf4078dfdf4d58e391c813a0` matches GitHub's published digest.
- Verdict: **pass-with-limits**. Allowed: `chatdownload` of public VOD chat only, no credentials passed. Kept in `C:\clip-work\quarantine\TwitchDownloaderCLI-1.56.5\`. Re-audit on any version bump.

## 2026-11-23: gta-components audit (strict mode)
- echris6/gta-components at commit `81181fda29c98b53a0d14659d8d1dafd62d84060`. Code MIT, fonts OFL. Created 2026-11-21, 2 commits, 30 stars, one author: strict mode.
- Read: every package.json (no install hooks; scripts only `npx --yes hyperframes@<pinned>`), setup.sh (copies fonts/kit only), the 3 stinger components' HTML and the shared kit. No eval/Function/atob/child_process, no reads of files, env or tokens in browser code. Glyph and kit JS is long-line data, readable. External loads: GSAP 3.14.2 and three 0.160.0 from jsDelivr, pinned versions but no SRI.
- hyperframes 0.8.162 (npm, Apache-2.0, HeyGen, published by GitHub Actions trusted publisher, no install scripts). Deps use ^ ranges. Sends PostHog telemetry unless HYPERFRAMES_NO_TELEMETRY=1 / DO_NOT_TRACK=1.
- Verdict: **pass-with-limits**. Allowed: bake shorts/09-wasted-stamp (0,1), shorts/10-mission-passed (0,1), shorts/08-wanted-level (0) with bg=none, inside Windows Sandbox only, telemetry off (`ops/stingers/bake-*.ps1`). Not allowed: running it on the host or in the worker, the zoom components, the showcase server. kit motion.js is licensed for in-project use only; do not redistribute it.

## 2026-11-23: MediaPipe light audit
- PyPI `mediapipe==1.2.3` (Google, Apache-2.0, 2026-11-11, win_amd64 wheel). Brings opencv-contrib-python 5.x (cv2 incl. Haar data); do not install opencv-python-headless next to it.
- Model BlazeFace full range, storage.googleapis.com/mediapipe-models/face_detector/blaze_face_full_range/float16/1, sha256 `3698b18f063835bc609069ef052228fbe86d9c9a6dc8dcb7c7c2d69aed2b181b` (checked by `clipworker face-model`).
- Verdict: **pass**. Used only for face detection in the IRL reframe (D115).

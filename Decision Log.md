# Decision Log
Links: [[clipping]] · [[Interview Record]] · [[Channel Strategy]]

| ID | Status | Decision | Source |
| --- | --- | --- | --- |
| D001 | Locked | Planning and research only here; implementation handoff for Claude Code. | Initial user request |
| D002 | Locked | Private tool for Zo first, streamer libraries and flexible publishing destinations (Q1 E). | Interview answer |
| D003 | Locked | Human approval before publishing; revisions supported. | Initial request |
| D004 | Locked | Approval should publish to assigned channel(s), rather than download-only workflow. | Interview answer |
| D005 | Direction locked; details open | Mixed routing supports dedicated streamer accounts and shared accounts; exact lineup/count needs help and research. | Interview answer |
| D006 | Locked objective; strategy open | Broadest practical audience; maximize retention and monetization. No specific audience option selected. | Latest answer |
| D007 | Locked | Create an Obsidian graph/vault named clipping as persistent project knowledge. | Latest request |
| D008 | Locked | Store clipping discussions, decisions and knowledge; design memory, learning, auditing and adaptation around it. | Latest request |
| D009 | Locked | Continue and finish the interview in a new chat after vault creation. | Latest request |

## Unconfirmed
Eight-person roster; channels and platform count; content focus; simultaneous stream capacity; setup costs; verified operating costs within the selected budget; posting frequency; campaign economics; rights/permissions; editor and model; monitoring/publishing API feasibility. Revenue direction, recurring budget and V1 monitoring runtime are now selected below.

### 2026-11-20 — Revenue interview continuation
- D010 — User-selected V1 revenue direction: creator campaigns through Content Rewards. Campaign selection and eligibility remain unverified; this does not select platform payouts, sponsorship/affiliate programs or a final campaign.
- D011 — Requested future capability: repeatedly discover and analyze campaigns, explain which to pursue/avoid and why, and improve recommendations using feedback, editing strengths, streamer familiarity and channel outcomes. Cadence, integrations and adaptation authority remain open. See [[Campaign Intelligence]].
- Clarification to the older Unconfirmed list: revenue direction is now established; its operating details and viability remain open. All prior locked decisions remain in force.
- D012 — Locked planning budget: $100–$250/month for combined recurring monitoring, AI/transcription, editing, storage and hosting. $250 is the planning ceiling; no claim that full eight-stream processing fits. Setup spending remains undecided. Revisit any over-budget proposal with Zo.

## Proposed, not approved
Small initial channel lineup followed by expansion from measured results. Do not treat this as a locked count or a guaranteed winning strategy.

## 2026-11-20 — Reach Clipping focus (new chat)
- D016 — Locked: V1 revenue is **Reach Clipping campaigns only**; maximize earnings, growth and system improvement. Supersedes any "own channels first" idea. Sources limited to campaign-supplied/permitted streamers (Lacy, Clix, Silky first). Realized campaign pay is unverified; see [[Campaign Intelligence]].
- D017 — Locked: V1 auto-publishes approved clips to **X + YouTube Shorts** only. TikTok/Instagram analysis in [[Channel Strategy]]: no evidence X/Shorts outperform; X + Shorts chosen for API feasibility. Proposed (not locked): one-click handoff panel for TikTok/Reels.
- D018 — Locked: ffmpeg is the editing core; CapCut optional polish for top clips only (no official API).
- D019 — Locked gate: Zo joins Reach Discord/Whop and supplies campaign briefs, rules, payout details and the text of the X post before campaign-specific build work. Not yet done.

## 2026-11-20 — Project choice: Review Dashboard (Option 4)
- D020 — Locked: new project focus is Option 4, the Review Dashboard with Wake Up. Zo does NOT want a final plan locked yet; capture all detail in the living brief in [[Dashboard Experience]] and keep it open to refinement. More videos/links will be studied first.
- D021 — Locked direction, details open: dashboard works on phone and computer, synced; after approving a clip on the computer, Zo can download that video from the dashboard on the phone. Hosting/storage method and iOS behavior unvalidated.
- D022 — Locked source of truth: design references come from Zo's Pinterest board, delivered into `references/`; link pending. No design values until then.

## 2026-11-20 — Runtime and dashboard lock; session pause
- D013 — Locked: for V1, Zo's PC watches streams only while the PC is on. No hosted monitoring or coverage while the PC is off is included in this decision. Continuous watching alongside clipping/editing applies during active monitoring sessions. Heavy-work placement, sleep/browser-close behavior and recovery details still need planning.
- D014 — Locked: the web app dashboard has a visible "Wake Up" button/toggle. Switching it on transforms the entire page into a beautiful, polished, fully working clipping-system interface. This is the requested future product experience, not an implemented interface or physical wake-on-LAN command. See [[Dashboard Experience]].
- D015 — Locked session instruction: save and organize the current planning notes, then stop. Zo will move into a new chat to discuss an important topic. Do not automatically resume interview questions before that topic.


## 2026-11-20 — Integration starting set
- D023 — Locked by Zo (decision card): starting tool set is Supabase (database, sync, login, clip storage) + Vercel (dashboard hosting) + direct YouTube Data API and X API for posting. Postiz deferred until TikTok/Reels; Cloudflare Pages/R2 kept as a fallback. Vercel Pro ($20/mo) is likely needed for commercial use (unverified). Nothing set up yet. Research: [[Tools and Repos]].
- D024 — Locked by Zo (decision card): Reach Discord campaigns are watched by "Following" Reach's announcement channel into Zo's own private server, where our own bot reads it. No user token or self-bot. Unverified: whether Reach's campaign channel is an announcement channel. Manual paste stays as fallback.
- D025 — Locked by Zo (decision card): Zo submits clip URLs to Content Rewards by hand; the dashboard shows the post link and a 30-minute countdown. Whop bounty API not used for now.

### 2026-11-20 — Skills and token policy
Renumbered 2026-11-20: these three were first written as D023-D025, which clashed with the integration decisions above. Same content, new IDs.
- D026 — Locked: token usage is a top-level priority without lowering output quality; policy in `CLAUDE.md`. Code/ffmpeg for deterministic work, model only for judgment; skills load on demand.
- D027 — Locked: project skills = impeccable, apple-design, stageshow (video breakdowns), learn, campaign-scout, clip-detector-tuning, publish-approval-gate, clip-qa, caveman, investigate-first. See [[Tools and Repos]].
- D028 — Locked: rtk and context-mode installed for token savings; rtk hook active next session.

## 2026-11-20 — Install plan and next design step
- D029 — Planned, not installed: tool install order, own chat-spike detector (PeakCut as blueprint) and gap list in [[Install and Detector Plan]]. PC checked: RTX 5060 8 GB, driver 617.42, Windows 11 Pro. Phase 0 not started; Zo paused here.
- D030 — Saved skills: repo-audit, stream-ingest, clip-render (added to `.claude/skills`).
- D031 — Next step (main thread): three dashboard variants for Zo to choose from. Brief in [[Dashboard Experience]] under "Next: three dashboard variants". Nothing generated yet; wait for Zo to say go and for Pinterest references.

## 2026-11-20 — Backend build (first slice)
Numbered D040-D047 to avoid a numbering clash with a parallel thread; the dashboard "Stage" choice is D049.
Code lives in `worker/` (Python 3.11 package `clipworker`) and `supabase/migrations/`. 61 tests pass, including real ffmpeg renders and the SQL migration on Postgres. Nothing deployed, no keys used.
- D040 — Locked: Twitch live status by polling Helix every 60 s with an app token. EventSub needs a public URL (webhooks) or a user token (WebSocket); polling is 1 call/min and simpler on a home PC.
- D041 — Locked for V1: Kick chat through Kick's public chat WebSocket (read-only, unofficial, may break). The official webhook path is coded (signature check) but stays off until a public endpoint and the payload are verified.
- D042 — Locked: the review gate is enforced in Postgres, not only in code. A trigger allows only listed state moves per actor; the worker can never approve; a publication row is refused unless a human approved the clip; every state change writes an audit row automatically. The dashboard writes only through `review_clip` and `mark_submitted`.
- D043 — Locked: no double posts. A post interrupted mid-call is never retried automatically (marked failed for Zo to check). Retryable errors retry up to 3 times with 5 min backoff. Default cap 10 posts/day per destination.
- D044 — Locked: render bitrate capped at 6 Mbps so a 60 s clip stays under Supabase's 50 MB free-plan file limit; QA blocks anything larger.
- D045 — Locked: spam guard. One chatter counts at most 2 messages per 5 s burst, so a single spammer cannot trigger a clip.
- D046 — Locked: campaigns parsed from Discord are saved as drafts (or "avoid"). Only Zo activating a campaign opens the rights gate for its streamers.
- D047 — Locked: dashboard access is an `owners` table plus row-level security; clips are private in Storage and reach the phone through signed links (D021).
- D048 — Locked by Zo (decision card, 2026-11-20): caption style from the Stage references (D049): Poppins SemiBold 78 px, white text, mint #60F3BD active word, #000002 outline 6 px, no shadow, 420 px bottom margin, 3 words per line. Set in `worker/config/channels.example.toml`.
- D050 — Locked by Zo (2026-11-20): caption pop. The active word starts at 115% and settles to 100% over 90 ms (`pop_scale`, `pop_ms` in `worker/config/channels.example.toml`). From the Clipper Video Upgrade Plan, P2.
- D051 — Locked by Zo (decision card, 2026-11-20): punch-in zooms at 130%, 0.2 s ramp, 1.2 s hold, at most one every 4 s, at sentence ends and the hype peak. Gaming layouts zoom only the facecam. `[zoom]` in `worker/config/channels.example.toml`.
- D052 — Locked by Zo (decision card, 2026-11-20): whoosh SFX off by default (`[sfx] enabled = false`). Switch on per clip with a revision note; campaigns with `rules.allow_sfx = false` never get it.

## 2026-11-20 — Dashboard v1 build
Code in `dashboard/` (Next.js 15, React 19, `@supabase/ssr`), migration `supabase/migrations/20261120180000_dashboard.sql`, worker change in `worker/src/clipworker/live.py`. Decided in the build thread under Zo's "decide small things yourself" rule; all reversible.
- D053 — Decided: dashboard stack is Next.js 15 App Router in `dashboard/`, plain CSS with every color and font taken from the Stage concept (D049), no UI kit. Deploy on Vercel with Root Directory `dashboard`. Review queue order: `score_10` desc, then confidence desc, then oldest first.
- D054 — Decided: owner-only sign in by email magic link, `shouldCreateUser: false`, sign-ups off in Supabase, owner added by hand to `owners`. Unknown emails get the same "link sent" answer. Middleware blocks every page without a session; RLS and the RPCs check `is_owner()` again.
- D055 — Decided (refines D014): Wake Up writes `control.awake` (new singleton table, `set_awake` RPC, owner only). The worker reads it every 15 s: off = stop watching and capturing, nothing new is detected; clips already rendering, in review or posting still finish. The dashboard shows the PC's own heartbeat (watching / awake / waking up / offline + last seen) next to the switch, so the switch never fakes a running PC. Offline worker runs without Supabase stay awake.
- D056 — Decided: private clip links are Supabase Storage signed URLs, 1 hour, created on demand per play or download, cached client-side for 50 min. Downloads get a safe file name (`streamer-title.mp4`).
- D057 — Decided: demo mode runs with no Supabase keys (or `NEXT_PUBLIC_CLIPP_DEMO=1`, `npm run demo`): sample day with 6 queued clips, a live countdown and 3 small sample videos; all actions work locally and nothing is saved or posted.
- D058 — Decided: Approve and Deny wait 4 s with an Undo button before reaching the database (a stray A or D key can be taken back). Revise sends at once with the typed note (kind `other`, empty payload). Cinema "Stream view" embeds the official Twitch (or Kick) player, muted; demo mode shows the placeholder art instead.

## 2026-11-20 — Supabase wired in
- D059 — Decided: Clipp runs on its own free Supabase project `clipp` (ref `aqmufpztmzsolpanrgsq`, us-east-1, org "theempp's projects"). The older project supabase-cyan-notebook (another app) was paused to free the 2-project free cap; it can be restored from the Supabase dashboard. Migrations core, judge_rubric, dashboard and harden applied by hand through the Supabase connector.
- D060 — Decided: security advisor fixes in `20261120210000_harden.sql`: search_path pinned on the last 4 functions, trigger-only functions no longer callable through the API. Owner-checked RPCs stay callable by signed-in users on purpose.
- D061 — Decided: the owner row is created by a database trigger (`claim_owner` on `auth.users`, kept out of the repo so no email is committed) the moment the owner's login is added. Sign-ups stay off; the owner is added once in Authentication > Users.
- D062 — Decided: three `seed-*` pending clips (Lacy, Clix, Silky) seeded to prove the live queue; reject them from the dashboard or delete rows where `job_id like 'seed-%'` once real clips flow.
- D063 — Decided: login also accepts the 6-digit code from the email (`verifyOtp`, type `email`), because a magic link opened on another device (e.g. the iPhone Mail app) cannot finish a sign-in started on the PC. Needs `{{ .Token }}` in the Supabase Magic Link email template. Supabase's built-in mailer allows about 2 emails an hour; custom SMTP (e.g. Resend) lifts that if it ever matters.

## 2026-11-20 — Dashboard visual direction
- D049 — Locked by Zo: the Review Dashboard uses concept A "Stage" as its base (supersedes the three-variant plan in D031; four concepts were shown). References: `references/pinterest/` (14 board pins + the standout pin, which is board pin 011). Changes Zo asked for: remove the top-center streamer dots and replace them with a left nav rail modeled on concept D "Signal", made flashier (animated live rings, LIVE tags, per-streamer chat-heat strip, Daddys GPU card, glowing Approve button). Cinema (concept C) becomes the per-streamer live page. Previews: Clipp Stage artifact https://claude.ai/artifact/2de8Gdqevauy6awaRMVH4p and the four-way comparison https://claude.ai/artifact/5ytYbJBd6X7fcWADZwkUVm. Colors are sampled from the pins; fonts (Poppins, DM Mono; Inter Tight on the live page) are closest Google Fonts matches. Concept stage only; nothing built.

## 2026-11-21 — Phase 0 done on Daddys (Zo's PC)
- D064 — Phase 0 installed and verified on the PC. Folders `C:\clip-work\{bin,refs,quarantine,buffer,vods,renders,cache,logs}` created. winget: uv 0.13.9, Gyan ffmpeg 9.1 full (ass/subtitles filters and h264/hevc/av1 NVENC present), Streamlink 8.6.3, yt-dlp 2026.10.26; Git and Node 24 were already there. Worker venv `C:\clip-work\Clipping\worker\.venv` on Python 3.11.18 (uv-managed; the system Python 3.13 is untouched).
- D065 — Torch pin: whisperX 3.8.6 requires torch 2.8, so the venv runs torch 2.8.0+cu128 / torchaudio 2.8.0 / torchvision 0.23.0 (cu128 index). PyTorch sees the RTX 5060 (sm_120) and a fp16 matmul runs. Install command: `uv pip install -e ".[transcribe,reframe,dev]" --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match`, otherwise uv pulls CPU torch. Full lock saved to `C:\clip-work\logs\phase0-freeze-2026-11-21.txt` (115 packages).
- D066 — whisperX check passed: large-v3, float16, 60 s English speech clip, 162/162 words with timestamps, transcribe 2.6 s + align 1.7 s warm (target under 15 s), model load 8.5 s, peak VRAM 0.77 GB. Models cached in `C:\clip-work\cache\hf` (3.2 GB); set `HF_HOME=C:\clip-work\cache\hf` when running the worker. Known harmless warnings: torchcodec fails to load (whisperX reads audio via ffmpeg) and Hugging Face cannot symlink without Windows Developer Mode, so it copies files instead.
- D067 — Worker tests on the PC: 92 passed, 1 skipped (local Postgres not installed; not part of Phase 0).
- D068 — The winget ffmpeg lives under the user folder, whose name contains `!`. Copied ffmpeg.exe and ffprobe.exe to `C:\clip-work\bin\` and pointed `FFMPEG_BIN`/`FFPROBE_BIN` there. `worker/.env` created from `.env.example` with paths only; every key is still blank and only Zo fills them in. Re-copy after an ffmpeg upgrade.

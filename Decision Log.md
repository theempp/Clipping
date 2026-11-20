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
Numbered D040-D047 because D032 was taken by the dashboard "Stage" choice in a parallel thread.
Code lives in `worker/` (Python 3.11 package `clipworker`) and `supabase/migrations/`. 61 tests pass, including real ffmpeg renders and the SQL migration on Postgres. Nothing deployed, no keys used.
- D040 — Locked: Twitch live status by polling Helix every 60 s with an app token. EventSub needs a public URL (webhooks) or a user token (WebSocket); polling is 1 call/min and simpler on a home PC.
- D041 — Locked for V1: Kick chat through Kick's public chat WebSocket (read-only, unofficial, may break). The official webhook path is coded (signature check) but stays off until a public endpoint and the payload are verified.
- D042 — Locked: the review gate is enforced in Postgres, not only in code. A trigger allows only listed state moves per actor; the worker can never approve; a publication row is refused unless a human approved the clip; every state change writes an audit row automatically. The dashboard writes only through `review_clip` and `mark_submitted`.
- D043 — Locked: no double posts. A post interrupted mid-call is never retried automatically (marked failed for Zo to check). Retryable errors retry up to 3 times with 5 min backoff. Default cap 10 posts/day per destination.
- D044 — Locked: render bitrate capped at 6 Mbps so a 60 s clip stays under Supabase's 50 MB free-plan file limit; QA blocks anything larger.
- D045 — Locked: spam guard. One chatter counts at most 2 messages per 5 s burst, so a single spammer cannot trigger a clip.
- D046 — Locked: campaigns parsed from Discord are saved as drafts (or "avoid"). Only Zo activating a campaign opens the rights gate for its streamers.
- D047 — Locked: dashboard access is an `owners` table plus row-level security; clips are private in Storage and reach the phone through signed links (D021).
- D048 — Proposed, pending Zo: caption style from the Stage references (D032): Poppins SemiBold 78 px, white text, mint #60F3BD active word, #000002 outline 6 px, no shadow, 420 px bottom margin, 3 words per line. Set in `worker/config/channels.example.toml`.

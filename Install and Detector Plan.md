# Install and Detector Plan
Links: [[clipping]] · [[Decision Log]] · [[Tools and Repos]] · [[Agent Workflow]] · [[Dashboard Experience]]

Written 2026-11-20. Status: PLAN ONLY. Nothing installed, cloned, built or committed. No credentials in this note. Respects D012 (budget $100-250/mo), D013 (PC watches only while on), D016 (Reach campaigns, permitted streamers only), D018 (ffmpeg core), D023-D025.

## 0. Verdict
Build our own pipeline. Use whisperX for captions, TwitchDownloader for Twitch VOD + chat, claude-shorts as a skill pattern, ffmpeg + libass for every render. PeakCut is the blueprint for the detector, but we read it, we do not run it until it passes the audit. AI-Youtube-Shorts-Generator and autoclip are read-only references. SupoClip, Clips Kitty and herk-edit-kit are cut (license or fit).

## 1. Install order (Windows PC)
Do the steps in this order. Each step has a done-check; stop if it fails.

### Phase 0: Base machine (30-60 min)
- Work folder outside the vault: `C:\clip-work\` with `bin\`, `refs\` (read-only clones), `quarantine\` (audit), `buffer\` (live segments), `vods\`, `renders\`, `cache\`, `logs\`, `worker\` (our code). Reason: the vault path contains `!`, which breaks cmd delayed expansion and some ffmpeg filter strings. Media never goes in the vault.
- GPU check: run `nvidia-smi`. NVIDIA with 8 GB+ VRAM = whisperX large-v3 on GPU. Less, or no NVIDIA = whisperX `medium` on CPU int8, and live transcription only on detected windows (it already is).
- Zo's GPU: GeForce RTX 5060 (8 GB, Blackwell, driver 617.42, CUDA 13.4 capable; checked 2026-11-20). Windows 11 Pro: use Windows Sandbox for audits. Needs PyTorch CUDA 12.8 (cu128) wheels or newer; older wheels will not detect the card. whisperX large-v3 on GPU, compute type float16 (int8_float16 if VRAM runs short with 3 channels).
- Installs via winget: Git, Python 3.11 (via `uv`), ffmpeg full build (Gyan.FFmpeg, includes libass), Node LTS (only for claude-shorts helper scripts), streamlink, yt-dlp.
- Enable Windows Sandbox (needs Windows Pro). If the PC is Windows Home, use a throwaway Hyper-V/VirtualBox VM for the audit run instead.
- Power: worker calls SetThreadExecutionState while monitoring so the PC does not sleep mid-stream; normal sleep returns when monitoring stops.
- Done-check: `ffmpeg -filters | findstr ass`, `streamlink --version`, `python --version` all succeed.

### Phase 1: Audit gate (before ANY third-party code runs)
Applies to: PeakCut, ffmpeg-skill, claude-shorts, AI-Youtube-Shorts-Generator, autoclip. whisperX and TwitchDownloader get the light version (verify release source and hash) because they are long-established.
1. Clone into `C:\clip-work\quarantine\<repo>` and pin the commit SHA in [[Tools and Repos]].
2. Read every install path: setup.py/pyproject build hooks, package.json `postinstall`, `.bat/.ps1` scripts, MCP server entry.
3. Grep for red flags: outbound URLs not in the docs, `eval/exec`, base64 blobs, obfuscated JS, reads of browser profiles, `%APPDATA%`, `.env`, SSH keys, Discord tokens, crypto wallets.
4. Check history: account age, contributor count, star-growth curve, whether issues/PRs are real. PeakCut (created 2026-11-14) and ffmpeg-skill (fast growth) get the strict version.
5. First run only inside Windows Sandbox / VM with no credentials present.
6. Result written to [[Tools and Repos]]: pass, pass-with-limits, or fail. Fail = we keep reading it as a reference only and never execute it.
This becomes the `repo-audit` skill (section 4).

### Phase 2: whisperX (core captions)
- `uv venv` in `C:\clip-work\worker\.venv`, install CUDA-matched torch first, then whisperX.
- Model: large-v3 on GPU; medium int8 on CPU fallback. English only for V1 (all three streamers are English).
- Use: transcribe only the candidate window (about 40-60 s), word-level align, cache by audio hash in `cache\`. Never transcribe whole VODs.
- Windows trap: cuDNN/CUDA version mismatch is the usual failure. Pin versions in a lock file once it works.
- Done-check: 60 s test clip returns word timestamps in under 15 s on GPU.

### Phase 3: TwitchDownloader (Twitch VOD + chat)
- Download TwitchDownloaderCLI.exe from the official GitHub release into `bin\`, check the hash.
- Use: `chatdownload` gives chat JSON for any Twitch VOD. This is the backtest and tuning data for the detector (clip-detector-tuning step 2). `videodownload` with time ranges for VOD clipping.
- Twitch only. Kick needs its own path (section 3, gap 1).
- Done-check: chat JSON for one recent Lacy/Clix/Silky VOD parses into our message table.

### Phase 4: claude-shorts (skill)
- After audit, copy into `.claude/skills/claude-shorts/`. Trim its SKILL.md to our token policy (body 60 lines or less, detail in references).
- What we keep: its segmentation and hook/caption workflow. What we drop: Remotion rendering. Captions render with ffmpeg + ASS (D018). Remotion stays off unless ASS captions fail Zo's look test.

### Phase 5: Reference-only clones (never executed in V1)
Shallow clone into `refs\`, read-only. Write a short "what we borrow" note per repo.
- PeakCut: rolling live buffer, loudness + chat + transcript fusion, Grok prompt shape, daily posting caps. Borrow the design, write our own code.
- AI-Youtube-Shorts-Generator: face auto-crop and caption steps. Borrow only if we need face tracking later.
- autoclip: job pipeline and UI flow (link in, clips out, post copy). Borrow structure for the dashboard handoff.

### Phase 6: ffmpeg-skill (last)
- Strict audit first. If it passes: install the skill, but do NOT enable its MCP server until each of its tools is reviewed; allow only the 9:16 crop, caption burn, silence trim and loudness tools we need.
- If it fails: we write the five ffmpeg recipes ourselves into the `clip-render` skill. We lose nothing important.

### Cut
- SupoClip: noncommercial license. Clips Kitty: AGPL. herk-edit-kit: no license, talking-head focus. Do not clone.

## 2. Our chat-spike detector (PeakCut as blueprint)
Pure code. The model sees only the shortlist.

### Inputs
- Twitch live chat: anonymous read-only IRC over WebSocket (`wss://irc-ws.chat.twitch.tv`, `justinfan` nick). No account token needed for reading. EventSub stays for live/offline status (D023 research).
- Kick live chat: official Kick API chat webhook (KickEngineering/KickDevDocs) as primary. Payload names unverified; confirm before building. Fallback: Kick's public chat WebSocket, read-only, one connection per channel, treated as unofficial and allowed to break.
- Twitch VOD chat: TwitchDownloader JSON (backtests).
- Audio: loudness from the live buffer via ffmpeg `ebur128` (momentary LUFS, 1 s steps).

### Live buffer
streamlink pulls the stream (Twitch and Kick), ffmpeg writes 10 s segments to `buffer\<channel>\`, keep the last 10 minutes, delete older. Every chat message and loudness sample is stamped on the same clock as the segments.

### Scoring (per channel, every 1 s)
- Chat rate: messages/s in a 5 s burst window vs a baseline = rolling median of the last 10 min (robust to one-off spam). Burst ratio = burst / max(baseline, floor).
- Unique chatters in the burst (stops one spammer from triggering).
- Reaction tokens weighted: KEKW, LUL, OMEGALUL, "??", "W", "L", "CLIP IT", "no way", per-channel emotes. Weights live in a per-channel config.
- Audio: momentary loudness vs its 10 min median.
- Score = 0.45 chat burst z + 0.20 unique-chatter z + 0.15 reaction weight + 0.20 audio z. Starting values only; clip-detector-tuning owns changes.
- Trigger when score stays above threshold for 2 s or more. Cooldown 45 s per channel. Merge triggers within 20 s into one moment.

### Window
Chat lags the moment by roughly 5-15 s. Clip window = trigger start minus 25 s to trigger start plus 15 s (40 s), then the model may trim. Keep the lead-in and payoff (Agent Workflow rule).

### Grok check
- Cut the window from the buffer, whisperX it, send Grok only: the transcript (about 40 s of words), a 30-message chat sample from the burst, the scores, the campaign rules summary.
- Grok returns JSON: keep/drop, category, trim in/out (seconds), hook line, title, caption emphasis words, confidence.
- Cheapest Grok model that passes our labeled eval set. Cache by window hash. Expected volume about 10-30 calls per stream-hour, so text-only cost stays small inside D012.
- Drop = logged with reason (feeds tuning). Keep = render job.

### Evaluation before going live
Label 20-30 real moments from 3-5 past VODs per streamer (TwitchDownloader chat + Zo's picks). Replay detector offline. Target: catch 80% of labeled moments with 10 candidates/hour or fewer before Grok. Only then turn on live.

## 3. Gaps the earlier ranking missed
1. Kick ingest. No ready tool. Kick live chat via official webhook (verify) or WebSocket fallback; Kick VOD chat replay has no supported route, so Kick is live-only in V1.
2. Windows/GPU setup. Handled in Phase 0; GPU model and VRAM still unknown. Zo to run `nvidia-smi` once.
3. ffmpeg 9:16 + captions pipeline. Our own: per-streamer layout template (facecam crop box on top, gameplay below, stored per streamer, set once by hand), ASS word-by-word captions from whisperX, loudness normalize to about -14 LUFS, H.264 1080x1920. Face tracking deferred: Lacy/Clix/Silky use fixed facecams. Design values (font, colors) wait for `references/` (D022).
4. Review queue handoff. Worker uploads render + thumbnail + metadata to Supabase Storage, inserts a `clips` row at `pending_review` (after clip-qa), and writes a `worker_heartbeat` row every 15 s so the dashboard's Wake Up view shows live status. Service key lives only in `C:\clip-work\worker\.env`, never in the vault or the repo.
5. Local job queue. SQLite in `C:\clip-work\worker\`. Stages: detected, captured, transcribed, judged, rendered, qa_passed, uploaded. Restart-safe; a PC shutdown resumes where it stopped.
6. Dedupe. Same moment from two triggers or two streamers in one squad (Lacy/Clix often stream together) = keep one; hash of transcript + time.
7. Rights gate. Only streamers permitted by the active Reach campaign record (D016). Missing permission = no capture.
8. Disk and cost meters. Buffer cap, renders older than 14 days after publish deleted locally (kept in Supabase), monthly Grok + storage spend shown on the dashboard.
9. Concurrency. Start with 3 channels at once on one PC. Raise only after measuring CPU/GPU.

## 4. Skills
Existing and kept: clip-detector-tuning, clip-qa, publish-approval-gate, campaign-scout, learn, investigate-first, caveman, impeccable, apple-design, stageshow, video-breakdown.

New, proposed now (review cards in the project thread):
- `repo-audit`: Phase 1 gate before any third-party code runs.
- `stream-ingest`: Twitch + Kick live chat, live buffer, VOD chat download, one clock.
- `clip-render`: 9:16 layout, whisperX ASS captions, loudness, export spec.

Next batch, drafted here, propose after the first three are used:
- `review-handoff`: Supabase upload, `clips` row at `pending_review`, heartbeat, retry. Must call clip-qa first and never set any state past `pending_review` (publish-approval-gate owns the rest).
- `worker-setup-windows`: Phase 0 checklist, version pins, GPU check, common CUDA/cuDNN fixes.
- `grok-judge`: prompt, JSON schema, eval set run, cache rules, model-choice check.

## 5. Build order after install
1. Detector offline on TwitchDownloader chat (no video, no model). 2. Eval against labeled moments. 3. Live buffer + Twitch chat for one streamer. 4. whisperX + Grok on candidates. 5. clip-render + clip-qa. 6. Review handoff to Supabase. 7. Add Kick. 8. Add channels 2 and 3.

## Open items for Zo
- D019 still open: campaign briefs needed before campaign-specific rules go in.

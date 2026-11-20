# Clipper Video Upgrade Plan

Source: "Claude Code Can Now Clip ANY Video (Free Skill)", Eddie | AI, youtu.be/IY08-3TS2o8 (8:20, published 2026-10-22, 172k views). Studied 2026-11-20 via full transcript, description and a frame-level watch-through.
Tags: **[V]** = Verified from the video (said or shown on screen). **[A]** = Assumption / our inference.
Fits: [[Decision Log]] (D013, D023, D026, D029, D049), [[Install and Detector Plan]], skills clip-render, clip-qa, publish-approval-gate.

## 0. Verdict
The video's tool is a transcript-first podcast clipper. Its value for us is the **editing layer and the judge rubric**, not its moment finder. Our chat-spike + audio detector stays (streams have moments with no speech; a transcript-only picker misses them) [A]. Steal: hook-first trims, 1-10 scoring, title + post caption per clip, 2-3 word captions with keyword highlight, face-aware punch-in zooms at sentence ends, reframe on camera cuts, optional whoosh SFX, plain-English revision requests. All of it is code/ffmpeg except ranking and captions, which matches D026.

## 1. What the skill is (facts)
- Runs inside Claude Code on your own PC; one prompt: "Run the clipper skill for this video <link>" [V].
- Folder shown: `claude/`, `clipper/`, `output/`, `remotion/`, `CLAUDE.md`, `install.py`, `run.py`, `requirements.txt`, `README.md`, `LICENSE`; zip `Claude.Video-Clipper-main.zip` (1.4 MB) [V].
- Setup: open folder in Claude Code, "set up this full repository for me", allow `python install.py`; one-time [V]. First run downloads Whisper, so slower [V].
- Pipeline, four steps: transcribe (Whisper, word timestamps) -> pick moments -> cut vertical -> edit [V]. Edit scripts: `cut.py`, `reframe.py`, `edit.py`, `sfx.py` [V]. SFX assets: `click.wav`, `whoosh-cinematic.mp3`, `whoosh-heavy.mp3` [V].
- `remotion/` folder means captions/edit likely rendered with Remotion, not pure ffmpeg [A].
- Output: `out/<video-slug>/edited/NN-<clip-title-slug>.mp4`, 1080p (1080x1920) [V].
- Speed: 2 h podcast -> 7 clips in ~30 min total; editing all 7 took ~7 min; short video 2-4 min [V].
- Cost: only moment picking uses the model, on the Claude Pro plan; download/Whisper/cut/edit are local and free [V].
- Distribution: the skill is behind a paid Skool community (aibc), not linked publicly [V]. A public GitHub repo `Plextrang/Claude-Video-Clipper` (pushed 2026-10-19, 2 stars) matches the name [V], but that it is the same code is [A]. Not opened or run. **repo-audit must pass before any of its code touches the PC.** Do not pay for Skool; we can build every piece ourselves.

## 2. How it picks moments (judge rubric)
- Reads the whole transcript start to finish [V].
- Standalone test: "a total stranger could watch with zero context and fully understand" [V].
- Starts the clip **exactly on the hook**, skipping the ramble before it [V]. Ends **on the payoff** so it feels finished [V].
- Every clip must open with an approved hook type: surprising fact, bold claim, or start of a story [V].
- Scores each clip out of 10 and ranks best first [V]. Example output: scores 10, 9, 9, 8, 8, 8, 7; durations 38-47 s [V].
- Each clip gets a title ("Billionaire On Paper, Broke In The Bank") and a ready-to-post caption, often a quote + 2-3 hashtags [V].

## 3. How it edits (render spec)
- **Captions:** from word timestamps, 2-3 words on screen at a time, popping on time [V]. Key words ("billionaire", "million") highlighted [V]. Bold sans, white with dark outline/shadow, lower-middle of frame, yellow highlight, scale pop on the active word [V, from frames; exact font/size unreadable].
- **Caption color:** tries the creator's brand color first; if unsure, samples a color from the video [V].
- **Zooms:** model reads the transcript to place zooms where a point lands (end of sentence, every few seconds) [V]; face detection finds the face in each shot and zooms around it so nothing important is cut [V].
- **Reframe:** on every camera cut it re-centers on whoever is on screen [V]; framing changes on each cut so the jump is not harsh [V].
- **SFX:** whoosh on each zoom, from 3 bundled sounds [V].
- **Revisions in plain English:** "extract only the best clip, under 30 seconds, no sound effects, blue captions" -> full re-edit [V].

## 4. Gap vs Clipp today
| Area | Clipp now (PR #1 / plans) | Video technique | Action |
|---|---|---|---|
| Moment finding | Chat-spike + audio detector, Grok judge on 40 s window | Transcript-only LLM pick | Keep ours; add their rubric to Grok |
| Trim | -25 s/+15 s window, model may trim | Start on hook, end on payoff | Make hook/payoff trim mandatory |
| Scoring | keep/drop + confidence | 1-10 score, ranked | Add score_10 + rank to queue |
| Metadata | hook line, title | title + post caption + hashtags | Add post_caption, hashtags, slug filename |
| Captions | whisperX ASS word-by-word | 2-3 word chunks, highlight, pop | Upgrade ASS generator |
| Framing | Fixed per-streamer crop boxes | Face-tracked, re-center per cut | Keep boxes for gaming; add face/scene mode for IRL |
| Zooms | none | Punch-in at sentence ends | Add |
| SFX | none | Whoosh on zoom | Add, per-campaign toggle |
| Revisions | Review queue revision loop (planned) | Natural-language re-edit | Revision box -> edit-params JSON |

## 5. Prioritized plan
**P1 — Judge rubric (biggest win, ~1 h, text only)** [A on effort]
1. Extend the Grok prompt + JSON schema: `score_10`, `hook_type` (surprising_fact | bold_claim | story_start | reaction_peak | play_peak), `standalone` (bool), `trim_in` = first hook word, `trim_out` = last payoff word, `title`, `post_caption`, `hashtags[]`, `emphasis_words[]`. `reaction_peak` and `play_peak` are our additions for streams [A].
2. Hard rules: drop if `standalone=false` or no hook in first 2 s; snap trims to whisperX word boundaries; length 15-60 s per campaign rules.
3. Queue sorts by `score_10` desc. Label set (Install plan §2 eval) gains a score column so we can check Grok's ranking against Zo's picks.

**P2 — Caption upgrade in clip-render (~half day)**
4. Chunk whisperX words into 2-3 word groups (break on punctuation/pauses > 0.3 s) [V for 2-3 words; break rule A].
5. Active-word highlight + 110% scale pop via ASS `\t` transforms; emphasis words from Grok in highlight color [A on values].
6. Safe-zone guard (the Silky bug): captions must sit inside the platform UI safe zone and never clip at the frame bottom; clip-qa checks caption bbox vs frame [A]. Font, size, colors come from `references/` per CLAUDE.md design rule, else ask Zo.
7. Per-streamer caption color in streamer config (brand color first, sampled fallback, mirrors the video) [V technique / A for our config].

**P3 — Zooms + reframe (~1 day)**
8. Zoom points = sentence ends from whisperX, min 3-5 s apart, plus detector peak second; ease-in 1.0 -> 1.12-1.2 over ~0.2 s, hold, ease back [values A].
9. Gaming layout: zoom only the facecam or gameplay panel, anchored inside its crop box (keeps Lacy/Clix boxes intact).
10. IRL layout (Silky driving): scene-cut detection (ffmpeg `scdet`) + face detection (MediaPipe/OpenCV, local) to re-center per shot; smooth the path so it does not jitter [A].
11. All local, no model calls (D026).

**P4 — SFX + revisions (~half day)**
12. Whoosh on zoom, -18 dB under voice, toggle per campaign (some campaigns may ban added audio; check rules in campaign-scout) [A]. Source license-free sounds ourselves.
13. Dashboard revision box: Zo types "under 30 s, no SFX, blue captions"; cheap model maps it to edit-params JSON (`max_len`, `sfx`, `caption_color`, `trim_in/out`, `zoom`) -> re-render. Passes through publish-approval-gate as a new version [A].

**P5 — Ops polish**
14. Output naming `<streamer>/<date>/NN-<title-slug>.mp4`, 1080x1920 export [V pattern].
15. Benchmarks to beat: edit ≤ 1 min per clip on the RTX 5060 [V baseline ~1 min/clip].
16. One-command installer idea -> `worker-setup-windows` skill (`install.py` equivalent) when Phase 0 starts.
17. Optional: repo-audit `Plextrang/Claude-Video-Clipper` as a reference only; never run it unaudited.

## 6. Attached video check (2026-11-20, 3:15 AM file)
- 576x1024, 2:26, 30 fps; a reposted TikTok talking-head (@kaylumai watermark), no burned captions, no Clipp dashboard or Clipp output on screen [V, frames sampled every 4 s].
- Speech not transcribed: the cloud box cannot download Whisper weights. Run whisperX on the PC once Phase 0 is done, or Zo says what it is for.
- Lessons for clip-qa: reject sources under 1080 px tall and visible platform watermarks before render [A].

## 7. Pitfalls
- Transcript-only picking misses non-verbal stream moments; keep chat-spike detector [A].
- Face tracking on gameplay frames can grab in-game faces; restrict face search to the facecam box [A].
- Constant zoom + whoosh gets tiring; cap density and let Zo toggle [A].
- Don't buy the Skool course for the skill; everything above is buildable from what was shown [A].

## 8. Where we left off (2026-11-20, 12:15 PM ET)
- Built: P1 judge rubric, P2 captions, P3 zooms + IRL reframe, P4 SFX + revision note parsing. All in PR #2 (branch `claude/project-thread-0fq7m4`), stacked on PR #1 (backend, `claude/project-thread-zf79sa`), which sits on `claude/project-thread-v3f8qp` (vault). CI passing, 87 tests.
- Locked: D050 caption pop 115%/90 ms, D051 zooms 130%, D052 SFX off by default. Next free ID D053.
- Not started: P5 ops (file naming, speed benchmark on the RTX 5060).
- Dashboard v1 built (2026-11-20, D053-D058) in `dashboard/`, stacked on PR #2. Items 5 and 6 below are done in code; they need the Supabase project and keys to go live.

### Left to do before Zo can review and test the dashboard on the PC
1. Review and merge PRs in order: vault branch -> #1 backend -> #2 clipper upgrades.
2. Phase 0 on the PC: Python 3.11, ffmpeg, CUDA 12.8 torch, whisperX, Poppins SemiBold, `pip install -e worker[transcribe,reframe]`.
3. Supabase project: run migrations, create owners row, storage bucket.
4. Keys in the PC `.env` only: XAI (Grok), Twitch app, Supabase service key. GROK_MODEL chosen by the eval set.
5. Build the Stage dashboard (Next.js on Vercel): left rail, review queue sorted by score, clip player, approve/revise with revision text box, 30-min Content Rewards countdown, Wake Up toggle, per-streamer Cinema live page.
6. Wire the dashboard to Supabase (login, RLS, signed clip links).
7. End-to-end test on one Lacy VOD: detector -> Grok -> render -> QA -> review queue -> revise -> approve.
8. Then: P5 benchmark, labeled eval set for detector thresholds and Grok scoring, posting to YouTube/X.

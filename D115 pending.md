# D115 pending: paste-a-link clip creation (built 2026-11-23, needs zo's OK)

Not yet in Decision Log.md. Paste as D115 when zo says (renumber if D112-D114 land first and take it).

**D115.** zo can paste a link into the dashboard (Review page, "Clips from a link") and the PC makes clips from it.

1. **Links.** Twitch VOD or clip, Kick VOD or clip, YouTube video/live/short, X post. https only. One live request per link + time range; pasting it again shows the existing one. Failed or canceled links can be pasted again.
2. **Streamer.** Picked in the box, or detected from the link (URL login, then the uploader name) against the roster. Not on the roster = fails with "pick a streamer".
3. **Range.** Optional From/To (h:mm:ss). Over 8 hours without a range is refused. Still-live streams are refused (use CLIP THAT).
4. **Detection.** Twitch VOD with TwitchDownloaderCLI installed: chat + audio (same detector as live). Everything else: audio-only loudness spikes. A source of 90 s or less is one moment, kept (zo picked it); the judge only trims and titles.
5. **Same pipeline.** whisperX -> Grok judge -> render (recipes/D114 once merged) -> clip-qa -> pending_review. No zooms (D112). Every clip human-approved; nothing posts without per-batch approval.
6. **Cost.** "Most clips" (default 6, max 20) caps Grok calls; the box shows the estimate (count x $0.0025) and each finished link shows actual Grok spend.
7. **Duplicates with live.** Moments within 45 s of a clip already made from the live stream are skipped.
8. **Full frame.** Checkbox renders the face-tracked full frame (no split). The MediaPipe tracker upgrade plugs into render/, not into the link flow.
9. **Runs** inside `clipworker live` with `[features] links = true`, or alone with `clipworker links`. `clipworker link URL` queues from the PC.

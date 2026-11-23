# Zwoclippe dashboard: final design (Halo Pro) build handoff

Locked by Zo on 2026-11-23 (D116). This folder is the design source of truth for the new dashboard. It replaces the Broadcast look in `dashboard/`. Build it over the existing dashboard and keep its data wiring (Supabase, auth, live stats, queue, review actions).

Open `index.html` in a browser (it plays the sample clips from this folder). All numbers and clips in it are sample data.

## Files
- `index.html`: the final Review page (finalist A, "Halo Pro"). All CSS tokens are in its `:root` block.
- `app.js`: mock behavior for the queue, popup, editor, post confirmation and toasts. Treat it as a spec of the interactions, not production code.
- `a-final-1440.png`, `a-final-1920.png`, `a-final-phone.png`, `a-popup.png`, `a-editor.png`: reference screenshots.
- `finalist-b-aurora.html`: the rejected finalist, kept for the record only. Do not build it.
- Media (`*.mp4`, `*.jpg`): sample Lacy footage and avatars from the old concept.

## What Zo asked for (all in the design)
1. **Whole screen, no frame.** On desktop the dashboard fills the viewport (`height:100%`, no page scroll at 1181 px wide and up, 701 px tall and up). The page dots (Live, Review, Pods & ledger, Stats) sit in the top bar and the action dock sits in the bottom bar, both flush. Nothing sticks out of the console. Below that size the page stacks and scrolls.
2. **No Wake Up.** Wake Up is removed completely. The dashboard and worker are always on, and an "Always on · 3 agents" badge sits in its place. The old `control` / `set_awake` switch (D055) should no longer gate the worker. The page plays a one-time light-up sweep on load (`body.waking`) and nothing else.
3. **Hero clip (top pick)** shows a 9:16 player with a chat-heat strip under it, the title and source line, a status tag, a Grok score ring with Hook/Payoff/Trend bars and est. views, a Grok "why" note, clip facts (hook time, caption px, flashes/s, best slot; hidden below 1000 px of height), an editable headline, Approve / Revise / Reject, **Edit clip**, and the post row (YouTube, TikTok, X toggles + Post).
4. **Edit clip** opens the editor inside the main area (top bar and dock stay). It has tools on the left (Trim, Captions, Headline, Crop, Flashback, Audio; **no zoom tool**, D112), a 9:16 preview, an inspector on the right, and a timeline (video with drag trim handles, caption words, audio wave, playhead). Save returns to the dashboard with the clip as the hero, an "Edited by you · saved" tag, and the post buttons pulsing. Manual edits get logged for learning (D114).
5. **Queue** is a vertical list on the right where Checks used to be (Checks are no longer shown on the dashboard; clip-qa still runs before review). Each row has a thumbnail (plays on hover), a streamer color, NEW for under 15 min, title, hook and est. views, and a score ring. A summary row (waiting, avg score, new) and streamer filters sit on top. **Clicking a clip opens a popup** with player controls, score, headline, Approve / Revise / Reject, Edit clip, post toggles and Post now.
6. **Posting always asks first.** Post needs the clip approved and at least one platform picked, then a confirm dialog. Nothing posts without that (D088 and the approval gate).
7. **Streamer cards (left)**: the live stream as a dimmed background, a per-streamer color stripe, an avatar ring, a platform icon (Twitch or Kick), a pulsing LIVE timer, current game, viewer count, a chat-heat sparkline and clips found today. Offline streamers turn grey and show "last live" and an expected return time. A "3 agents watching" pill sits below.
8. **Bottom widgets** (replace Last posted, PC specs, Next post): **AI spend** (kept; month total vs budget, split by model, month-pace marker, 14-day sparkline, today), **Today's pipeline** funnel (Found, Judged, Passed 60, Okayed, Posted), **Next 24 h** release lane (YouTube/TikTok/X rows, clip thumbs at their slot times, a now line), and **Channels · 7 days** (views and growth per platform).
9. Brighter and flashier but tidy: graphite glass, a permanent cold halo floor light, one color per streamer, pink only for chat heat, mint for approved and growth.

## Data each widget needs
- Streamer cards: live state, uptime, viewers, game/category, chat rate series (about 10 points), clips found today, last live time.
- Hero and queue: clip id, streamer, source, length, found at, Grok score + sub-scores, est. views, Grok reason, headline, status, scheduled slot, chat-heat series for the clip.
- AI spend: month spend by model, budget, today, daily series, projection.
- Pipeline: today's counts per stage.
- Next 24 h: scheduled posts (platform, time, clip thumb).
- Channels: 7-day views and growth per platform.

## Out of scope for this design
Live, Pods & ledger and Stats pages keep their current content and should take this page's tokens. The bell (notifications) and search are visual only so far.

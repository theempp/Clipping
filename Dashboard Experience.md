# Dashboard Experience
Links: [[clipping]] | [[Vision and Requirements]] | [[Agent Workflow]] | [[Decision Log]]

## Locked user direction — 2026-11-20
Inside the web app dashboard, include a "Wake Up" button/toggle. When Zo switches it on, the entire page transforms into the polished, fully functional clipping-system interface.

The active interface carries the existing requirements: streamer avatar navigation with green live glow; dedicated livestream pages; visible concurrent agent activity, analytics and review queues; approval, denial and revision; publishing approved versions to assigned destinations. Eight sources remain the eventual target, not a verified V1 simultaneous processing capacity.

V1 stream monitoring runs on Zo's PC only while it is on. The Wake Up interaction is an in-app activation experience; physical PC wake, hosted fallback or monitoring during PC shutdown has not been requested. Precise activation semantics still need design.

## Proposed behavior to refine — not yet locked
- Show starting, active, unavailable and error states based on actual local worker status; visual transformation alone must not imply monitoring is running.
- Preserve review items and settings across activation; repeated clicks should not duplicate workers or jobs.
- Use a clear page-wide transition with accessible reduced-motion behavior.
- An off/asleep/disconnected PC cannot provide live local monitoring. Show the last known state and observation time rather than a false active indicator.

## Open details for later
Visual design, inactive dashboard appearance, animation, whether activation starts all enabled sources, switch-off effects on in-flight jobs, whether workers continue when the browser closes, sleep/restart behavior and local-to-web connection/security. These are future interview topics, not blockers to recording this direction now.

## Living brief — Option 4, started 2026-11-20 (OPEN, deliberately not locked)
Zo chose the Review Dashboard as the working project and wants all detail captured here while staying refinable. More videos/links will be studied and may change the backend and this brief; nothing below is a final plan. Dashboard must be viewable on phone and synced with the PC.

### Zo's requirements (user direction)
- Same dashboard on computer and phone, linked and in sync.
- Approve a clip on the computer, then on the phone download that video straight from the dashboard.
- Design comes from Zo's Pinterest board of references (link not yet supplied). Per global rule, nothing is designed until references are in `references/`; no defaults.

### Proposed approach — to validate, not decided
- Responsive web app, installable to phone home screen (PWA), private login (it controls publishing, so it must not be open).
- Sync model: the PC worker is the only place footage lives while it runs (D013). For phone access when away from the PC or when it is off, approved clips would have to be uploaded to reachable storage. Options: (A) hosted dashboard + hosted database/storage, approved clips only uploaded; (B) private tunnel to the PC, works only while the PC is on; (C) hybrid. Leaning A for phone download; cost and size limits not decided.
- Supabase Storage free plan caps files at 50 MB and low egress (docs: 5 GB; a third-party guide says 10 GB; conflicting) — short vertical clips may fit; check supabase.com/pricing before choosing. Signed expiring download URLs are the standard way to keep clips private.
- Phone download caveat (unconfirmed, must test on Zo's actual iPhone/Android and OS version): iOS has had gaps — "Save to Photos" missing from programmatic share sheets in iOS 16.2+ (WebKit bug 255544), and downloads from installed home-screen PWAs reported unreliable (bug 275288). Fallbacks: plain download link, or show the video so it can be long-pressed and saved.
- Wake Up from the phone only changes dashboard state; it cannot power on a sleeping PC (D014 unchanged). Show last-known state and time.

### Open questions
Hosting choice and monthly cost within $100–250; phone type/OS; login method; whether the phone can approve/deny as well as download; clip retention and storage cleanup; notifications when a clip is ready; offline behavior; what the Pinterest references show.

### Inputs pending from Zo
Pinterest board link or exported images into `references/`; additional videos/links to analyze (reference videos aaTqimE1J9w and -jFLlQSVA1c still NOT ANALYZED).

## Next: three dashboard variants (Zo's request, 2026-11-20)
Handoff for the main thread. Do NOT generate until Zo says go; Zo is adding a few references to the Pinterest board first.

What Zo asked for, in Zo's words summarized:
- Three visual dashboard variants to review and choose from, as the start of the overall dashboard design and layout (mood-board concepts).
- Completely different from each other in layout, colors, widgets, buttons, components and overall feel. Creative, unique, and clearly standing apart.

What each variant must show (from requirements already in this note and the plan):
- Wake Up toggle and the transformed "active" state (D014), with true worker status, not just a visual change.
- Streamer avatars with a green live glow; a per-stream page.
- Live agent activity running at the same time (watching, detecting, transcribing, rendering), not one status.
- Review queue: clip preview, approve, deny, revise (typed note: caption, trim, crop); then publish to X + YouTube Shorts (D017).
- Content Rewards post link with the 30-minute submit countdown (D025).
- Campaign panel from campaign-scout (pursue/avoid with reasons).
- Analytics, Grok and storage spend against the $100-250/mo budget, PC/GPU status.
- Works on phone and computer, synced; download an approved clip on the phone (D021).

Constraints:
- D022 and CLAUDE.md: visual values come only from Zo's Pinterest references in `references/`. If the folder is still empty when Zo says go, ask Zo for the board link or images first.
- Use the impeccable and apple-design skills for the UI work; stageshow if a demo animation is wanted.
- Present the three side by side so Zo can pick or mix; record the choice here and in the Decision Log.

## Status
2026-11-20: Dashboard v1 built in `dashboard/` (see its README for running it on Windows, demo mode included). Wake Up semantics locked as D055; build decisions D053-D058 in [[Decision Log]]. Not yet connected to a real Supabase project.

## Chosen direction — 2026-11-20 (D049)
Zo reviewed four moodboard concepts built from the Pinterest board (references/pinterest/, 14 pins plus the standout pin, which is board pin 011) and chose concept A "Stage" as the base. Zo's changes: the top-center streamer dots are replaced by a left nav rail modeled on concept D "Signal" but flashier (animated live rings, LIVE tags, a chat-heat strip per streamer, a Daddys GPU card, a glowing Approve button). Concept C "Cinema" becomes the per-streamer live page. The dock under the frame becomes Deny / Revise / Approve with keyboard keys, and on the phone the rail folds into an avatar strip. Palette (sampled from the pins): #000002, #16181A, #262A2D, #3C4E5A, #D9D9D9, live mint #60F3BD, with Cinema's sun #FF8962 on the live page. Type: Poppins + DM Mono (Inter Tight on the live page). These are the closest Google Fonts matches, since the pins don't name their fonts. Previews: https://claude.ai/artifact/2de8Gdqevauy6awaRMVH4p (chosen) and https://claude.ai/artifact/5ytYbJBd6X7fcWADZwkUVm (four-way comparison). Concept stage only; nothing built yet. Proposed caption style (backend PR #1, D048, pending zo): Poppins SemiBold 78px at 1080x1920, white text, #60F3BD active word, #000002 outline 6px, 420px bottom margin, 3 words per line.

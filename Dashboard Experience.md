# Dashboard Experience
Links: [[clipping]] | [[Vision and Requirements]] | [[Agent Workflow]] | [[Decision Log]]

## Locked user direction - 2026-11-20
Inside the web app dashboard, include a "Wake Up" button/toggle. When Zo switches it on, the entire page transforms into the polished, fully functional clipping-system interface.

The active interface carries the existing requirements: streamer avatar navigation with green live glow; dedicated livestream pages; visible concurrent agent activity, analytics and review queues; approval, denial and revision; publishing approved versions to assigned destinations. Eight sources remain the eventual target, not a verified V1 simultaneous processing capacity.

V1 stream monitoring runs on Zo's PC only while it is on. The Wake Up interaction is an in-app activation experience; physical PC wake, hosted fallback or monitoring during PC shutdown has not been requested. Precise activation semantics still need design.

## Proposed behavior to refine - not yet locked
- Show starting, active, unavailable and error states based on actual local worker status; visual transformation alone must not imply monitoring is running.
- Preserve review items and settings across activation; repeated clicks should not duplicate workers or jobs.
- Use a clear page-wide transition with accessible reduced-motion behavior.
- An off/asleep/disconnected PC cannot provide live local monitoring. Show the last known state and observation time rather than a false active indicator.

## Open details for later
Visual design, inactive dashboard appearance, animation, whether activation starts all enabled sources, switch-off effects on in-flight jobs, whether workers continue when the browser closes, sleep/restart behavior and local-to-web connection/security. These are future interview topics, not blockers to recording this direction now.

## Status
Planning only. No dashboard, local worker or Wake Up control has been implemented.

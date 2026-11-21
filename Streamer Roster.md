# Streamer Roster
Links: [[clipping]] · [[Research Agenda]] · [[Channel Strategy]] · [[Decision Log]] (D069)

Active roster set by Zo on 2026-11-21. Config: `worker/config/channels.example.toml` (copy to `channels.toml`).
Platforms checked 2026-11-21 against Twitch Helix (users, channels, latest VODs) and kick.com channel pages.

## Core (every stream; GTA 6 boosted x1.25)
| Streamer | Channel | Status |
|---|---|---|
| xQc | twitch.tv/xqc | Confirmed. VOD 2026-11-20 on GTA VI. Also has a Kick channel (multistreams); Twitch used. |
| Adin Ross | kick.com/adinross | Zo wrote "Aiden Ross"; assumed Adin Ross. Daily "PLAYING GTA 6" VODs on Kick; Twitch idle since 2026-10-16. Confirm. |
| Stable Ronaldo | twitch.tv/stableronaldo | Confirmed. Live on GTA VI 2026-11-21. |
| Jynxzi | twitch.tv/jynxzi | Zo's "Jinxie", confirmed. Live on GTA VI 2026-11-21. Crop box proposed, pending Zo. |
| Lacy (he/him) | twitch.tv/lacy | Zo's "Lisi", confirmed. GTA 6 marathons; crop box approved earlier. |

## GTA 6 only (captured only while the stream category is GTA 6)
| Streamer | Channel | Status |
|---|---|---|
| Kai Cenat | twitch.tv/kaicenat | Confirmed. VOD 2026-11-21 on GTA VI. |
| IShowSpeed | twitch.tv/ishowspeed | Twitch VOD 2026-11-20 (GTA 6 day 3). His main home is YouTube, which the worker can't capture. |

## Archived (off the roster, crop boxes kept)
Clix, Silky: `active = false` in the channel config.

## Open items
- Crop boxes for the five new channels are proposals (`layout_proposed`) until Zo approves; renders use the tracked full-frame crop meanwhile.
- At most 3 channels are captured at once until CPU/GPU load is measured: GTA 6 streams first, then core, then most viewers.
- D070: roster streamers are always tracked for Zo's own channels; a campaign is an extra. The worker adds missing `streamers` rows at live start.

## Selection evidence needed (for future changes)
Current audience and watch time; trend direction; streaming hours; frequency of usable moments; audience overlap; GTA 6 relevance; engagement and retention of comparable clips; source access; clipping policies/permissions; monetization suitability; language/regions; cost per usable clip.

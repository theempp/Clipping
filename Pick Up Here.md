# Pick up here (2026-11-21, evening)

## Where things stand
- Everything is committed and pushed to `main` on GitHub. No open PRs. Both clones (this vault and `C:\clip-work\Clipping`) match `origin/main`.
- Dashboard redesign (Stage v2) is in place, but Zo wants more visual revisions. Continue from there next session.
- Decisions run through D072 in [[Decision Log]]. Next free ID: D073.

## Open items
1. **Dashboard visual revisions**: Zo's next focus. Visual values come only from `references/` via Atlas.
2. **Grok key**: `XAI_API_KEY` (plus `GROK_MODEL` and the two price fields) is still empty in the worker `.env`. Until it is set, the worker uses the code-only stand-in judge (D071).
3. **Crop box approvals**: the proposed per-streamer crop boxes for the roster are still pending Zo's approval.
4. **Lacy UNJUDGED clips**: review the Lacy clips the stand-in judge left UNJUDGED.

## Worker status
- Not running right now (no worker process on the PC as of 2026-11-21 evening).
- `.env` at `C:\clip-work\Clipping\worker\.env` has Supabase, Twitch, Kick, YouTube, X, Discord and ffmpeg/streamlink paths set. Only the Grok fields are empty.

## Running the dashboard on the PC
- PowerShell: `cd C:\clip-work\Clipping\dashboard`, `npm run dev`, then open http://localhost:3000. Closing that window stops it.
- Log in from the same Chrome on the PC (magic link links fail on the phone, since localhost is the phone there).

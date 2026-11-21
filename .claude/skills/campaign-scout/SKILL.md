---
name: campaign-scout
description: Turn pasted Reach/Content Rewards campaign briefs into a scored record and pursue/avoid call. Use when a campaign brief or Discord/X post is given.
---
# Campaign Scout
Input: brief text from our own server, manual paste, or @ReachClipping on X. Never user-token/self-bot Discord; never scrape Whop.
1. Extract: streamer, platforms, CPM, cap, per-clip cap, min views, deadline, GTA 6 mention, payout proof, and EVERY rule line verbatim; flag risky rules (review, account reqs, original edits, watermark, AI/bots, exclusivity, views window, payout threshold).
2. Zo's hard rules (D072): roster streamers only (else avoid, grow own channels); pay must be MORE than $1 per 1K views (else avoid; unknown = ask). Kai/Speed campaigns must allow GTA 6 clips.
3. Score 0-5 each: pay (CPM above the floor), effort, familiarity, rights clarity, platform fit, rule risk. Unknown field = "unverified", never guessed.
4. Output one record + verdict (pursue/avoid/ask) + one-line why; rank all campaigns (`rank_campaigns`). Append to `Campaign Intelligence.md`.
5. Cheap-first: regex/parse fields in code; use the model only for ambiguous rules text. Batch several briefs per call.
6. After outcomes arrive, call `learn` to adjust scoring weights.

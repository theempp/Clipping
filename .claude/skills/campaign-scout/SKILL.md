---
name: campaign-scout
description: Turn pasted Reach/Content Rewards campaign briefs into a scored record and pursue/avoid call. Use when a campaign brief or Discord/X post is given.
---
# Campaign Scout
Input: brief text from our own server, manual paste, or @ReachClipping on X. Never user-token/self-bot Discord; never scrape Whop.
1. Extract only: streamer, platforms, CPM, cap, deadline, rules (length, tags, source allowed), payout proof.
2. Score 0-5 each: pay (CPM x realistic views), effort, streamer familiarity, rights clarity, deadline fit. Unknown field = "unverified", never guessed.
3. Output one record + verdict (pursue/avoid/ask) + one-line why. Append to `Campaign Intelligence.md`.
4. Cheap-first: regex/parse fields in code; use the model only for ambiguous rules text. Batch several briefs per call.
5. After outcomes arrive, call `learn` to adjust scoring weights.

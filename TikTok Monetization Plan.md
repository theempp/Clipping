# TikTok Monetization Plan

Written 2026-11-22 for zo's ask: two TikTok channels, 1 minute plus only, built to get paid by the Creator Rewards Program (CRP). Status: decided by zo 2026-11-22 (D075 to D078). Links: [[Decision Log]], [[Reference Clip Style]], [[Channel Strategy]], [[Streamer Roster]].

## The hard truth first

Raw stream clips will not get paid. TikTok's own pages (read 2026-11-22):

- Originality policy (updated Sep 25, 2026) calls unoriginal: content "largely repurposed from another source without adding any creative edits", content "combined from multiple sources with little or no additional information and/or content value", and content "with someone else's visible watermark or superimposed logo". Unoriginal content "is also be ineligible" for CRP, which uses originality "as a key metric in its rewards formula".
- CRP page (updated Sep 10, 2026) lists as ineligible: "minimal original input or edits", and as low quality: "split screens, meaningless reactions".

So the money is in transformation: our own narration, story, structure and graphics around the clip. The clip is the evidence; the video is ours.

Two real risks to our current style:
1. Split screen. Our reference layout (cam top, game bottom) is a stacked stream layout, not a filler split screen, but TikTok's wording is blunt. Mitigate by switching between full cam, full game and stacked by beat, never stacked for the whole video. Test it (cell L below).
2. Watermarks. Twitch/Kick logos, streamer overlays and alert boxes in the frame can count as "someone else's visible watermark". Crop boxes must exclude platform logos; clip-qa adds a check.

## CRP rules (official, 2026)

- Account: personal account (not Business), 18+, based and registered in US/UK/DE/JP/KR/FR/MX/BR, good standing.
- Gate: 10,000 followers and 100,000 video views in the last 30 days. Apply in TikTok Studio > Creator Rewards Program; answer within 3 days.
- Video: original, over 1 minute, at least 1,000 For You views, 1080p or higher, not a Duet/Stitch/Photo Mode, not ads, paid promotion or sponsored.
- Qualified view: 5 s+ watch, unique per account, no "Not interested", no paid or fraud views, viewer in a CRP country. Search views count only at 30 s+ watch.
- Pay = Standard Reward + Additional Reward (for well-crafted, engaging, niche-expert content).
- Penalties: 5 video violations in 30 days blocks the account; 5 total account violations = permanently out. Appeals: 80 days per video, 30 days per account.
- Unverified: whether one person can enroll two accounts in CRP. zo checks in TikTok Studio on account two before investing in it.

## Money: CRP vs campaigns

- CRP gaming RPM: about $0.40 to $1.00 per 1,000 qualified views, gaming median around $0.55 (third-party 2026 data; TikTok publishes no rate). Only qualified views from CRP countries count, so per raw view it is lower.
- Rough math: 1M qualified views a month is about $550. 5M is about $2,750.
- Campaigns: our rule is more than $1 per 1,000 views (D070); nothing qualifies right now.
- Rule: campaign clips never go on the CRP channels. A paid campaign clip is "sponsored content", which is excluded, and mixing it in risks flags. Campaign clips stay on YouTube/X, or a third account later.
- Verdict: CRP is the base income that needs no campaign; campaigns are bonus when one clears $1/1K.

## The two channels (ranked)

Update 2026-11-22 (D079): Zwoclipp only for now. Channel two waits until zo brings the second account.

1. **Zwoclipp: streamer story recaps (core 5).** "What happened on Jynxzi's stream" style. 65 to 100 s. Narrated hook, setup, the moment, the fallout. Jynxzi, xQc, Adin Ross, Lacy, Stable Ronaldo. GTA 6 moments get the 1.25x priority but the channel is about the people.
2. **Channel two: GTA 6 streamer channel (all 7).** Kai Cenat and IShowSpeed join here. GTA 6 launch search demand is the edge (search views pay at 30 s+). Formats: ranked "Top 5 GTA 6 streamer moments today" and storyline recaps. Name for zo to pick.

Why this split: channel one owns personality, channel two owns a searchable game niche. Each has a clear "specialized" angle for Additional Reward. Cut: a generic mixed clip channel (no niche, weakest originality case).

## Formats (all over 60 s)

Ranked by expected payout and originality safety:
1. **Narrated story recap** (65 to 100 s). Voiceover carries it; clips are cut in as proof. Strongest originality case.
2. **Ranked compilation** (70 to 120 s). 3 to 5 moments, number cards, our own commentary line between each. Must add info, or it is "combined with little or no additional value".
3. **Explainer / context** (90 to 180 s). "Why chat turned on xQc": timeline, receipts, on-screen text. Highest watch time, more script work.
4. **Extended single moment** (61 to 75 s) with a context intro and outro commentary. Riskiest; only as a test cell.

Pacing (zo's "long vs short style"), applied inside any format:
- **Short-style:** hook in the first second, cuts every 1 to 2 s, 61 to 75 s total.
- **Long-style:** slower build, chapter cards, 2 to 4 min.

Voice: start with one consistent AI voice, labelled as AI if TikTok's setting applies. Test zo's own voice as one cell; a real voice is the strongest originality signal.

## Test matrix (4 weeks)

Cells, each needs 6 posts before judging:
- F1 to F4: the four formats above.
- P: short-style vs long-style pacing.
- C: caption style A (headline only) vs B (headline + word captions), per D073.
- V: AI voice vs zo's voice (channel one only).
- L: stacked layout all through vs switching layouts by beat.

Do not cross every cell. Week 1 to 2: formats x pacing. Week 3 to 4: winner format, then caption, voice and layout tests.

Metrics per video (from TikTok Studio, entered by hand until the API audit):
- Retention: 5 s hold rate (the qualified-view gate), average watch time, % watched to end.
- Growth: For You views (must pass 1,000), follows per 1,000 views, search view share.
- Money after CRP: RPM, Additional Reward hits.
- Safety: any "unoriginal" or "ineligible" notice.

Decision rules:
- Kill a format after 2 ineligible or unoriginal notices. Appeal each one.
- Winner = highest follows per 1,000 views before CRP, highest RPM after. Retention breaks ties.
- Stop and rethink if a channel is under 1,000 average For You views after 20 posts.

## Cadence

- 2 posts a day per channel: one from the leading format, one test cell. 28 posts per channel in 2 weeks.
- Post near peak US evening hours (CRP pays on US-heavy audiences).
- Upload by hand until TikTok's app audit (D074). Use TikTok web for scheduling and bulk upload.
- Target: 10K followers and 100K views in 30 days on channel one by about week 6 to 8. Honest: 60 s+ only grows slower than short clips; this is the cost of earning from day one of eligibility.

## How it plugs into our system

1. Detector (existing) finds moments; nothing changes.
2. New **assemble** step: groups 3 to 6 judged moments by streamer or storyline into a 60 to 180 s plan.
3. Model writes the narration script from text windows and transcripts only (CLAUDE.md token rules). One cheap call per video.
4. Voice: TTS render on the PC, or zo records into the dashboard.
5. Render: ffmpeg cuts clips under the voice, layout switches by beat, number cards, captions tagged A or B.
6. clip-qa adds: duration over 60 s, 1080p, no platform logo or overlay in frame, voice present for at least 40% of runtime, no copyrighted music bed.
7. Dashboard: each video records channel, format, pacing, caption style, voice, layout. Stats entered by hand per video so the self-improvement loop can rank cells.
8. Same approval gate as every platform. Nothing posts without zo.

## Risks

- Originality flags (biggest). Mitigation: voice plus structure on every video, no bare clips.
- Split-screen wording: tested in cell L.
- Copyright: streamers' own music and DMCA. Strip music beds; credit the streamer in text and caption.
- Two-account CRP enrollment unverified.
- Slow growth to 10K with long-form only.
- RPM is low and moves; TikTok publishes no rate.
- Business account by mistake: both must be personal accounts.

## Decisions (logged 2026-11-22)

- D075: Zwoclipp = narrated story recaps for the core 5; channel two = GTA 6 streamer channel for all 7.
- D076: No bare stream clips on CRP channels; every video carries our narration and structure.
- D077: Campaign or sponsored clips never post on CRP channels.
- D078: 4-week test matrix as above, 2 posts a day per channel.

Sources: TikTok Creator Academy, "Understanding TikTok's Originality Policy" and "Creator Rewards Program" (read in the browser 2026-11-22); RPM ranges from ttcalculator.net and influencermarketinghub.com (third party).

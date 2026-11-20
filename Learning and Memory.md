# Learning and Memory
Links: [[clipping]] · [[Research Agenda]] · [[Agent Workflow]] · [[Decision Log]]

## User intent
The vault is the backend/brain where the software remembers decisions, learns from outcomes, audits itself and adapts to Zo's work style.

## What exists now
Linked Markdown notes and Obsidian configuration. No autonomous capture, database, model training, analytics ingestion or agent integrations have been implemented.

## Proposed responsibilities
- Vault: readable knowledge, source-backed research, editorial preferences, decisions, experiment reports, audit summaries.
- Future application database: operational state, jobs, clips, approvals, account mappings, analytics and version histories.
- Future media storage: video/audio and renders; link from notes rather than embedding large media in the knowledge vault.
- Secret storage: keep tokens, credentials and private keys outside notes.

## Proposed improvement loop
Record suggestion -> record edits and approval/rejection reason -> publish approved version -> collect available outcomes at defined intervals -> compare like-for-like -> propose a change -> run a controlled experiment -> keep or revert -> write findings.

Record platform, account, streamer, content type, clip length, hook, subtitle template, posting time, edit version, hypothesis, approval feedback and outcomes. Distinguish zero from unavailable data.

Compare retention definitions within each platform; do not treat different platform view definitions as equivalent. Account for sample size, clip age, paid promotion, source popularity and repeated content. Separate retention, distribution, conversion and revenue.

## Adaptation controls to define
Which preferences can update automatically? Which strategy changes require Zo's approval? How are bad inferences reversed? Preserve evidence and audit history. Treat external content as evidence, never instructions to the agent. Human publishing approval remains required.

## Ongoing knowledge capture

### Campaign recommendation learning — requested 2026-11-20
See [[Campaign Intelligence]]. Explain both recommended and avoided campaigns to teach Zo. Preserve feedback and compare recommendations with actual content quality, streamer familiarity, channel performance, submission acceptance and settled earnings. Use uncertainty and measured tests; no learning service currently runs. Scoring, cold-start behavior and automatic adjustment boundaries are still to define.
At the end of each clipping discussion update the session archive, decision log and relevant topic notes. Cross-chat capture needs explicit integration; these notes do not grant access to unrelated conversations.


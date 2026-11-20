# Agent Workflow
Links: [[clipping]] � [[Vision and Requirements]] � [[Learning and Memory]]

## Requested behavior
Monitor streams continuously; clip moments and edit in parallel; send results to Zo; publish approved content to assigned destinations.

### Locked V1 runtime - 2026-11-20
Zo's PC monitors streams only while it is on. Continuous monitoring during clipping/editing means within active sessions, not 24/7 hosted coverage. The web dashboard's "Wake Up" control transforms the page into the operational interface; see [[Dashboard Experience]]. Local worker connection, start/stop semantics, browser-close behavior, sleep handling and recovery remain to specify. Other processing placement is not newly locked by the monitoring decision.

## Proposed architecture topics to validate
Independent monitoring, capture and render jobs; durable queues; stream reconnects; bounded concurrency; rolling source buffers; timestamps and detection evidence; deduplication; versioned edits; publishing retries with duplicate prevention; explicit failed/unknown states; cost and storage limits.

Show concurrent statuses instead of a single agent status that incorrectly suggests watching stops while editing.

## Proposed lifecycle
Candidate -> captured -> editing -> awaiting review -> approved -> publishing -> published.
Revision requests return to editing and review; rejections retain feedback according to retention policy. Include failures and retry states.

## Detection research
Combine transcript/audio/visual cues and chat signals where legitimately available. Keep lead-in/context and endings; avoid cutting jokes before the payoff. Evaluate false positives, missed moments, detection delay, edit quality and review burden.

## Not yet validated
Grok input capabilities, current model prices and latency; source ingest APIs; livestream embed access; CapCut automation/API availability; publishing and analytics permissions. Validate official documentation before locking tools.


---
name: publish-approval-gate
description: Enforce human approval, revision loop, audit log and platform limits before any clip is published. Use when building or touching publishing/review flow.
---
# Publish Approval Gate
Locked: D003/D004 human approval, then publish to assigned channel(s).
1. States: `detected > qa_passed > pending_review > approved|revise|rejected > scheduled > published|failed`. Only `approved` can reach a publisher; no code path skips it.
2. Every transition writes an audit row: clip ID, actor, time, reason, destination, platform response.
3. Revise returns a typed note (caption, trim, crop) to the editor step; re-run only the changed step.
4. Publisher is idempotent (retry never double-posts) and checks per-platform limits/auth before the call.
5. Check live API/ToS limits before building each platform; Postiz/TryPost are AGPL (reference only until license is cleared).

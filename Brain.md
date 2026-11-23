---
type: hub
tags: [brain, hub]
updated: 2026-11-23
---
# Brain
The system's memory. Agents read it before work and append lessons after. Source of truth for decisions stays [[Decision Log]].

## Hubs
[[Streamers]] · [[Pipeline]] · [[Platforms]] · [[Stack]] · [[Decisions]] · [[Plans]] · [[Lessons]]

## Self-improvement loop
1. **Read**: before a run, an agent reads its streamer note, that streamer's `brain.md`/`playbook.md` (see [[Streamer Brain]]) and the newest [[Lessons]].
2. **Act**: detect, judge, render, QA, queue for review. Zo approves every clip (D003, D085).
3. **Measure**: approvals, rejects + reasons, revision notes, 24 h post stats ([[Post Stats]]).
4. **Append**: one dated line per proven lesson in [[Lessons]] (evidence + keep/kill). Use the `learn` skill.
5. **Adapt**: weights/baselines update in code (`brain.json`, capped ±25%/update). Any rule, prompt or hook change = an experiment with a kill condition; Zo approves.

## Rules for new notes
- One subject per note, under ~25 lines. No credentials. No copies of other notes; link instead.
- Frontmatter `type` + `tags`; put the note in the matching `brain/` folder so it gets its graph colour.
- Link up to its hub and across to every entity it names (streamer, platform, stage, tool, decision ID).
- New decision: add to [[Decision Log]] with the next ID, then list it in the right Decisions note.
- Outdated note: fix or delete it; never leave two versions.

Related: [[Learning and Memory]] · [[Agent Workflow]] · [[Agency Blueprint]] · [[clipping]]

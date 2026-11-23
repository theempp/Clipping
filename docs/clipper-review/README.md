# Clipper review pack (2026-11-22)
Review pack. Phase 0 and Phase 1 (Lacy) are now installed behind `[features]` flags, all off by default (see `.claude/skills/zo-clipper/`, `streamers/lacy/`, worker code); these files stay as the reference drafts.

| File | What it is |
|---|---|
| `Clipper-Breakdown.pdf` | Visual study: Clipper Free vs Pro, Kenji system, gap analysis, streamer trio, agent design. Source: `index.html` + `style.css` + `assets/` |
| `zo-clipper/` | Our own Clipper skill (draft): `SKILL.md` + 5 reference files |
| `agents/` | `lacy-agent`, `jynxzi-agent`, `stableronaldo-agent` (drafts); `bench/xqc-agent.md` held in reserve |
| `streamers/_template/` | State files each agent owns: brain, playbook, learning, experiments, scoreboard, log, takedowns |
| `streamer-shortlist.md` | Evidence table and rubric for the trio |
| `wiring-plan.md` | Phased, flagged, reversible steps + decisions needed |

Evidence tags: **verified** (seen/read), **proposal** (ours), **unverified**. Clipper Pro's internals were not seen: only its video and the free engine's public zip (read as text, never run). Free-skill licence forbids re-uploading it, so we reimplement ideas and copy no code.
Build the PDF: Edge headless (`msedge --headless --print-to-pdf`) on `index.html`.

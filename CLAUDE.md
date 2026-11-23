# Clipping project
Private clip tool (Zo first). Vault notes (`*.md`) hold decisions; read `Decision Log.md` first. Code: `worker/`, `dashboard/`, `supabase/`; run from `C:\clip-work\Clipping`.

## Token policy (top priority; quality never traded away)
- Terse output; answer first; invoke `caveman` skill. Plain prose for security, irreversible actions, and anything written to files/commits.
- Search before reading; read line ranges, not whole files. Never reread what is in context.
- Skills load on demand. Keep skill descriptions <=1 line and bodies <=60 lines; push detail to reference files.
- Model only where code can't: detection, QA, parsing, state, rendering = code/ffmpeg. Model = ranking, classification, captions, campaign judgment.
- Feed models text windows and summaries, never full VODs or raw logs. Cache by content hash; batch small calls; cheapest model that passes the check.
- Subagents only for broad searches or parallel independent work; give exact files and return a short summary.
- Reuse stored artifacts (transcripts, stats) instead of regenerating. Stop at the verified result.
- Weekly: `learn` pass, prune unused skills, check `/context` for bloat.

## Design
No default style. All visual values come from `references/` via Atlas. Empty = ask the user.

## Working rule
Claude does as much of every process as it can itself (connectors, browser pane). It hands back only secret entry and decisions; approval gates stay.

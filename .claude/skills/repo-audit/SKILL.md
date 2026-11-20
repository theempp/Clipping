---
name: repo-audit
description: Audit a third-party repo or skill before any of its code runs on Zo's PC. Use before installing or executing any cloned tool.
---
# Repo Audit
No third-party code runs until this passes. Plan: vault note Install and Detector Plan, Phase 1.

1. Clone to `C:\clip-work\quarantine\<repo>`. Record commit SHA, license, created date, stars in Tools and Repos.
2. Read install paths only: pyproject/setup.py hooks, package.json scripts (postinstall), .bat/.ps1, MCP server entry, SKILL.md.
3. Grep (code, not model): undocumented URLs, eval/exec, base64 blobs, minified/obfuscated JS, reads of %APPDATA%, browser profiles, .env, ~/.ssh, Discord tokens, wallets.
4. History: account age, contributor count, star curve, real issues/PRs. Created <90 days or fast star growth = strict mode (read every file in the run path).
5. First run only in Windows Sandbox/VM with no credentials present.
6. Verdict: pass | pass-with-limits (list allowed parts) | fail (reference-only, never executed). Write verdict + SHA to Tools and Repos.
7. Re-audit on any version bump.

Light mode (long-established: whisperX, TwitchDownloader): official release source + hash check only.

---
name: pods-design-intel
description: Where pod-screen design intel lives and open Atlas gaps; recurring pod UI mistakes found 2026-11-22
metadata:
  type: project
---
Pod screens are judged against docs/design/atlas-pods.md (extrapolated from concept C Broadcast, D099; no reference for finance screens, GAP 9). Tokens in dashboard/app/globals.css.
Open GAPs at 2026-11-22: paid pill colour, section loading, destructive button, money icon, right-aligned td.n, pod colour, modal.
Recurring mistakes: `cents()` in lib/pods.ts uses Math.abs, so tiles drop the minus sign; `$` mixed prefix (usd) vs suffix (.num small) on one screen.
**How to apply:** check sign handling and $ placement first on any money UI.

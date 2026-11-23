---
name: pods-design-intel
description: Where pod-screen design intel lives and open Atlas gaps; recurring pod UI mistakes found 2026-11-22/23
metadata:
  type: project
---
Pod screens are judged against docs/design/atlas-pods.md (extrapolated from concept C Broadcast, D099; no reference for finance screens, GAP 9). Tokens in dashboard/app/globals.css.
Settled by Zo D110 (2026-11-23, atlas "Settled by Zo" section): "$" prefix (`.num small.pre`), oldest-waiting warn after 6h, inline add-entry row atop ledger card, phone pod switcher = sideways-scrolling `.seg`.
Open GAPs at 2026-11-23: paid pill colour, section loading, destructive button, money icon, right-aligned td.n, pod colour, modal, top-bar dropdown.
Recurring mistakes: `cents()` uses Math.abs so sign must be added by caller; inline `style={{color:"var(--warn)"}}` instead of existing text classes (`.st-revise`, `.chip.warn`); `.top` flex row at 375px squeezes `.seg.pods` to one visible button (brand+2 `.icb`+gaps eat ~285px of 343px).
**How to apply:** check sign handling, $ placement, and 375px `.top` fit first on any pod UI.

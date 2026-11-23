# Atlas: Pod screens (design intelligence)

Source: concept C Broadcast (D099), `dashboard-concepts/zwoclippe-moodboards/concept-c.html` + `c-overview.png` / `c-editor.png`, from `references/pinterest/`. Implemented tokens: `dashboard/app/globals.css`; fonts `dashboard/app/layout.tsx` (Sora = `--fd`, Inter = `--fb`).
Concept C has no pod, ledger or statement screen. Everything below re-uses existing classes; no new values. Where a need has no existing class it is listed under GAPS, not invented.

## Tokens in play (existing, do not add)
- Surfaces: `--bg`, `.glass` (`--glass`/`--glass2`, `--edge`, `--r-lg`), inset tiles `#00000030` via `.metrics div` / `.kv div` / `.camp dl div`.
- Text: `--tx`, `--mut`; numbers `.num` / `.num.sm` (Sora 300, tabular), `.tnum` for table cells, unit via `.num small`.
- Semantic: `--acc` (run/active), `--c2` (ok/approved), `--warn` (waiting/deadline), `--bad` (error/negative), `--c3` (scheduled).
- Status classes: `.pill.run|.warn|.ok|.bad`, `.dotst.run|.warn|.ok`, `.st-*` text colours, `.sc` (count badge).

## 1. Pod switcher + pod chip
- **Admin:** `.seg` placed in `header.top` right after `.brand` (Shell.tsx). Buttons: `All`, then one per pod; active = `.seg button.on`. `.seg` already scrolls horizontally (`overflow-x:auto`), so many pods do not break the bar.
- **Member:** no switcher. Show the pinned pod as the existing `.brand small` badge (same as the `demo` badge): `zwoclippe [Pod 1]`. Read-only, not a button.
- **Pod chip on clips:** `.pill` (neutral, `--mut`), admin only and only when `All` is selected. Placement: ClipCard `.qt` next to `.sc`; library `.clip figcaption small`; ledger/statements use plain text in a column instead.
- Phone (<=860px `.pillnav` hides): `.seg` stays in `.top`; `.brand`/`.sp` let it shrink. At <=720px if it crowds `.icb` buttons, move `.seg` to the first line of the page inside `.filters`.
- States: loading = `.seg button:disabled` (opacity .45); error loading pods = `.banner-line.err`; one pod only = hide the switcher.

## 2. Pod home action list (Overview)
Layout, top to bottom:
1. `.hero` (existing h1 + p).
2. `.glass` > `.hd` (`h3` "Needs you", `.r` count) > `ul.nextlist.rows`. One `li` per action row, ordered: stuck posts, to-approve, campaigns to join, earnings.
   - Row anatomy: `.dotst` (state) + `.tx` (`b` title, `span` detail) + right-side control.
   - To-approve: `.sc` count; span "oldest 3h 12m" (warn colour via `.chip.warn` if past deadline); control `.b.ok` "Review" -> `/review`.
   - Campaign to join (one row each): `.tx` b = campaign, span = payout/rule line; controls `.b.ok` "Join", `.b` "Decline". Declining uses `UndoToast` (existing undo pattern).
   - Stuck post: `.dotst.warn`; span = stuck reason + age; control `.b` "Open".
   - Earnings: row links to Statements; span "owed $X · paid $Y".
3. Earnings tiles: `.row2e` of `.glass.stat` > `.lab` ("Owed" / "Paid this month") + `.num.sm` with `.num small` for "$". Owed tile may use `.stat.hot` (the moodboard's highlighted stat).
4. `.sec` + `h2` "Trends", then charts: `LineChart` / `Bars` from `components/Charts.tsx` inside `.glass .ch`, using existing `.row2` / `.row2e` grids.
- Empty: `li` replaced by `.quiet` "Nothing needs you right now."; charts use `LineChart`'s `empty` prop (`.ch .empty`).
- Loading: Shell's `.loading` covers first paint; section-level, see GAPS.
- Error: `.banner-line.err` above the list; keep last-known rows.
- Phone: `.row2e`/`.row2` collapse to 1 col (existing media queries). `.nextlist.rows li` stays one line; long `.tx` truncates (ellipsis already set). Two-button rows (Join/Decline) keep `.b` size; `.tx` shrinks.

## 3. Ledger (admin)
Layout:
1. `.hero` h1 "Ledger".
2. Totals: `.row4` of `.glass.stat` > `.lab` + `.num.sm`: Gross, 15% cut, Pod net, Unpaid. Unpaid lab may carry `.lab em` / `em.down` for change.
3. `.filters`: `.seg` status (All / Pending / Cleared / Approved / Paid), pod `select.in`, search `.in`.
4. `.glass` > `.scroll-x` > `table.tbl`. Columns: Pod, Campaign, Source ref, Gross, Cut 15%, Pod net, Status, Actions. Money cells `.tnum`.
- Status chips (existing tokens only):
  - pending = `.pill.warn` (waiting; same meaning as agent ticker)
  - cleared = `.pill.run` (`--acc`)
  - approved = `.pill.ok` (`--c2`, matches `.st-approved`)
  - paid = `.pill.st-scheduled` (`--c3`). Note: decision needed, see GAPS #1.
  - reversal row: amounts in `td.bad` (`--bad`), with a leading minus; status `.pill.bad` "reversal"; source ref cell shows "reverses #id".
- Actions (one primary per row by status): pending -> `.b` "Mark cleared"; cleared -> `.b.ok` "Approve"; approved -> `.b.acc` "Mark paid"; any non-reversal -> `.b` "Reverse".
- Required input: open the `.revise` panel under the row (the existing "explain before submit" pattern): `.in` for transfer ref (Mark paid) or `textarea` for reason (Reverse), `.revise .ft` holds hint + confirm `.b.acc`. Confirm stays `disabled` (`button:disabled`) until the field is non-empty.
- After action: `UndoToast` message only for Mark cleared / Approve; Mark paid and Reverse are not undoable (reverse is the correction), so no undo button there.
- Empty: `.quiet` inside `.glass` "No entries for this filter."; Error: `.banner-line.err`; per-action failure: `.fixing.bad` under the row.
- Phone (<=720px): swap the table for `ul.tt-list` of `.tt-row`: `.tt-top` (`.tx` b = campaign, span = pod · source ref) + status `.pill`; then `dl.metrics` (Gross / Cut / Net, `dd.bad` for reversals); then `.tt-post` with the action `.b` and inline `.in`. Totals `.row4` already go 1 col.

## 4. Statements (pod, read-only)
Layout:
1. `.hero` h1 "Statements"; month picker = `.seg` (recent months) in `.hero`.
2. `.row3` of `.glass.stat` > `.lab` + `.num`: Pending, Owed, Paid (use `.pill` colour words in `.stat .sub` to tie to ledger states).
3. `.sec` h2 "Items" + `.glass` > `.scroll-x` > `table.tbl`: Date, Campaign, Source ref, Gross, Cut, Net, Status `.pill` (same mapping as Ledger). Reversals `td.bad`. No action column.
4. `.sec` h2 "Audit log" + `.glass` > `ul.nextlist.rows`: `.tx` b = what changed ("Marked paid · ref T-123"), span = who · when; right side the resulting status `.pill`.
- Empty month: stat cards show `.num` "0" with `.stat .sub` "No activity"; items table replaced by `.quiet`. Audit empty: `.quiet` "No changes yet."
- Error: `.banner-line.err`. Loading: see GAPS.
- Phone: `.row3` -> 1 col (existing). Items: same `.tt-list` / `.tt-row` swap as Ledger, no `.tt-post`. Audit list unchanged.

## Nav
Add to `PAGES` (Shell.tsx) with `main:false` so they live under the dock / "More" menu: Ledger (admin only), Statements. Icons: see GAPS #4.

## Settled by Zo (D110, 2026-11-23)
- Money: "$" before the number. Oldest-waiting warn after 6h. Add-entry: inline row atop the ledger card. Phone pod switcher: sideways-scrolling `.seg`.

## GAPS (no traceable value; do not invent, decide or add a reference)
1. **Five ledger states, four pill colours.** `.pill` only has run/warn/ok/bad. Paid mapped to `.pill.st-scheduled` (`--c3`) is a reuse of a colour that means "scheduled" elsewhere. Alternatives: paid = plain `.pill` (muted, "done, no attention"). Needs a call.
2. **No section-level loading/skeleton class.** Only `.loading` (40vh block). Interim: `.quiet` "Loading..." inside the `.glass`; a real skeleton needs a reference.
3. **No destructive button variant** (`.b.bad` does not exist). Reverse uses plain `.b`; the required-reason `.revise` step is the safeguard.
4. **No money / ledger / receipt icon** in `Icon.tsx`. Nav entries need an icon path from the icon set's source, not drawn ad hoc.
5. **No right-aligned numeric cell** in `.tbl`; money columns stay left-aligned until a `td.n` rule is approved.
6. **No top-bar dropdown.** `.menu` is positioned for the dock (`left:70px`). If pods outgrow `.seg`, a dropdown needs placement rules.
7. **No pod identity colour.** `--h` hues belong to streamers; do not reuse them for pods.
8. **No modal/dialog style.** Confirmation is inline `.revise`; if a blocking confirm is wanted for Mark paid, it needs a reference.
9. **No reference for tables/finance screens** in concept C; these layouts are extrapolated from Analytics (`.tbl`) and TikTok (`.tt-row`) patterns. design-reviewer should check them against those screens.

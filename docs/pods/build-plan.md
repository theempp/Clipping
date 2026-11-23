# Pods build plan (D091-D097)
Plan only. Order is D097 (tool-first, D094). Every step behind a flag, off by default. Human approval on every clip stays (D085). The dashboard never moves money (D092).

Schema for all four phases: `supabase/migrations/20261124000000_pods.sql` (NOT applied). Checks: `supabase/tests/pods_test.sql` (wired into `tests/run.sh`).

## Built vs missing (branch claude/pods)
| Area | Built | Missing |
|---|---|---|
| Access | `owners` + `is_owner()`, owner_read RLS on all tables, `review_clip`/`mark_submitted` RPCs, middleware session gate | pods, pod members, per-pod RLS (in new migration) |
| Clips | state machine + `clip_events` audit trigger, publish gate, `revise_failed`, `fixing` | `pod_id` tag (new migration) |
| Brain | `streamer_brain` + `set_brain_weights`, detector reads it every 60 s (D101) | `clip_labels`, `brain_versions`, viewer-clip poller, refit (D089 Phase 0/1; not on this branch) |
| Gates | render QA | dead-air gate, dedupe, proof frame, send test (D089) |
| Posting | `publish/runner.py`, per-destination `daily_cap` (D043) | D088 ramp (4/day d1-3, then ~8, >=2.5 h gap, overnight first) |
| Stats | `live_stats`, `stat_snapshots` (channel level) | `post_stats` 2h/24h/72h per post, stuck-post flag |
| Campaigns | shared `campaigns`, `campaigns/scout.py`, Discord intake | per-pod participation `pod_campaigns` (new migration), per-pod scout |
| Ledger | nothing | `ledger_entries`, `ledger_events`, `pod_statements`, RPCs (new migration) |
| Worker queue | local queue in `pipeline.py`; no jobs table | pod tag on jobs; lands on `clips.pod_id`, `candidate_log.pod_id` |

## Phase 1 - agents doing the pod's work
Flags (worker `config.toml` / `channels.toml`): `[pods] enabled`, `[gates] dead_air`, `[gates] dedupe`, `[posting] ramp`, `[stats] post_stats`, `[scout] per_pod`.
Tasks
1. Pod tag on every job: `channels.toml` gets `pod = "pod-1"` per channel; worker resolves pod id once, writes `pod_id` on `clips` and `candidate_log` inserts (`store.py`, `pipeline.py`, `live.py`). Trigger `clips_pod_tag` is only the fallback. One shared GPU queue, round-robin by pod (D096); log queue wait per pod in `worker_heartbeat.status`.
2. Per-streamer brain: land D089 Phase 0/1 (`clip_labels`, `brain_versions`, `brain.py`, viewer-clip poller) from `docs/clipper-review/wiring-plan.md`; brain stays keyed by streamer, pod comes through `streamers.pod_id`.
3. QA + dead-air gates: `detector/` dead-air gate (replay-tested first), dedupe + proof frame in QA. Fails go to `candidate_log` with outcome `qa_failed`.
4. Scheduled posting on D088 ramp: `publish/runner.py` reads a ramp table (day index per destination -> cap), min gap 2.5 h, overnight slots first; never above `daily_cap` 10. Raise step only when no stuck posts or originality flags (manual switch, not auto).
5. Post stats: new `post_stats` (per wiring plan) read at 2h/24h/72h; stuck flag (< 20 plays at 1 h, wiring plan step 14) raises a flag, never deletes.
6. Per-pod scout: `campaigns/scout.py` scores each active campaign per pod (pod's streamers vs `streamer_slugs`, D072 floor > $1 CPM) and upserts `pod_campaigns` rows `suggested` with `scout` json.
Data: `clips.pod_id`, `candidate_log.pod_id`, `pod_campaigns`, new `post_stats`, `clip_labels`.
Done when: Pod 1 runs dry with `[pods] enabled` and every new clip/candidate has `pod_id`; a Pod 2 test streamer's clip lands in Pod 2 only; ramp never posts 2 clips < 2.5 h apart on one destination (unit test); stats rows at 2h/24h/72h for one real post; stuck flag fires on a seeded low-play post; no clip publishes without `approved` (existing core_test still green); D096 load test (Pod 1 + one Pod 2 streamer live) logged.

## Phase 2 - per-pod review queue with RLS logins
Flag: `NEXT_PUBLIC_CLIPP_PODS=1` (dashboard), migration applied.
Files: `dashboard/middleware.ts` (unchanged gate: session required), `dashboard/lib/store.tsx` (replace `rpc("is_owner")` gate at ~L169 with `rpc("my_access")`; add `pod` filter state; admin gets a pod switcher, members are pinned), `dashboard/lib/types.ts` (Pod, PodRole, Access), `app/(app)/review/page.tsx` (queue already RLS-scoped; show pod chip for admin), `app/(app)/settings/page.tsx` (admin-only: invite member = add auth user by hand + `pod_members` row), `dashboard/README.md` (access model).
Auth: magic link stays invite-only (`shouldCreateUser: false`, sign-ups off, D054/D063). New member = Zo adds the user in Supabase Auth + a `pod_members` row. `claim_owner` trigger must NOT fire for pod members (it is outside the repo; check it only claims Zo's email).
DB (in migration): `is_admin()` (= `is_owner()`), `my_pod_ids()`, `my_access()`, `pod_read` policies on pods, pod_members, streamers, destinations, clips, clip_events, revisions, publications, submissions, streamer_brain, candidate_log, campaigns (via `pod_campaigns`), storage `clips` objects. `review_clip` / `mark_submitted` allow admin or a member of the clip's pod.
Still admin-only after this phase: `control` (Wake Up), `edit_rules`, `set_brain_weights`, `live_stats`, `stat_snapshots`, `spend`, `longform_*`, `worker_heartbeat`.
Done when: `supabase/tests/run.sh` passes (pods_test: Pod 2 owner sees only Pod 2, cannot approve or reject a Pod 1 clip even with its id, stranger sees nothing, admin sees both); a Pod 2 test login on a preview deploy sees only its queue and can play its clips (signed URLs pass the storage policy); Zo's view unchanged.

## Phase 3 - pod home as an action list
Flag: `NEXT_PUBLIC_CLIPP_POD_HOME=1`.
Route: `app/(app)/page.tsx` (Overview) renders `PodHome` for members and for admin with a pod picked; charts move below the list.
Components (built by component-builder from Atlas tokens; concept C Broadcast, D099): `ActionList`, `ActionRow` kinds: to approve (`clips` pending_review count + oldest), campaigns to join (`pod_campaigns` suggested), stuck posts (`post_stats` flags), earnings (`pod_statements` owed/paid this month). Each row links to its page.
Data: read-only views plus one new RPC `set_pod_campaign(pod, campaign, joined|declined)` (writes `decided_by/at`) - add in a follow-up migration once OPEN Q3 is answered.
Done when: each action row count matches a SQL query for that pod; empty states for zero; admin sees per-pod home via switcher; no chart loads before the list (perf-budget skill check).

## Phase 4 - ledger
Flag: `NEXT_PUBLIC_CLIPP_LEDGER=1`.
Routes: `app/(app)/analytics` Money tab (D098) -> `LedgerTable` (itemized, per pod) + `StatementCard` (`pod_statements` by month). Admin-only controls: `AddPayoutForm` (`ledger_add`), `StatusButton` (`ledger_set_status`: clear / approve / mark paid + transfer ref). Members see the same table read-only, no buttons. Audit drawer reads `ledger_events`.
DB (in migration): `ledger_entries` (gross_cents bigint, `agency_rate` default 0.15 recorded per row, `agency_cut_cents` and `pod_net_cents` generated, status `pending -> cleared -> approved -> paid`), `ledger_guard` trigger (admin-only updates, only forward one step, amounts lock after pending, paid is final and needs a transfer ref, no delete/truncate), `ledger_audit` trigger -> `ledger_events` (append-only: update/delete/truncate refused), `pod_statements` view (security invoker).
Done when: pods_test ledger block passes (split 10001 -> 1500 / 8501, skips refused, worker cannot move status, member cannot write, Pod 1 member sees no Pod 2 money, 4 audit rows); UI hides admin controls for members and the RPCs refuse them anyway; no code path calls a payment API (grep check).

## Folder and naming
- `docs/pods/` plans only. Dashboard: components in the existing `dashboard/app/(app)/<route>/` pattern; shared pod pieces in `dashboard/components/pods/` only if 2+ routes use them. Worker: no new package; pod logic lives in `store.py` + `config.py`.
- SQL names: `pod_*` tables, `ledger_*` tables, `*_guard` / `*_audit` triggers, `pod_read` / `owner_read` policies (matches core).
- Drift risk: `is_owner()` and `is_admin()` mean the same today. New code uses `is_admin()`; do not add a second admins table.

## OPEN questions (need Zo)
1. Can Zo (admin, also Pod 1 owner) approve Pod 2's clips? Migration keeps admin approval on all pods (current behaviour); "pod owners can't approve each other's clips" may mean Zo too.
2. Can role `member` approve, or only pod `owner`? Migration lets any member of the pod approve.
3. Who joins a campaign for a pod: pod owner, any member, or Zo only?
4. Ledger corrections: a wrong pending amount or a refunded/clawed-back payout has no path (no void, no edit RPC). Add `void` status or reversing entries?
5. One payout covering several pods (shared account per D095): who splits gross per pod, and on what basis (views per pod's posts?).
6. Ledger money is gross before the ~10% Content Rewards fee (D095) or after? 15% applies to which number?
7. D093 exit: when membership is removed, should the ex-pod still read its statements (ledger) until the final payout?
8. Should Pod 2 see/tune its own brain weights, edit rules, Wake Up and live stats, or stay admin-only (current)?
9. Streamers/destinations default to Pod 1 when inserted without a pod (worker auto-insert, D070). OK, or must the worker always state the pod?
10. Pod 2 streamers and channels vs D069/D084 roster rules: does each pod have its own roster and caps (`max_channels` 3 is GPU-wide)?

## First task for component-builder
Blocked until Phase 1 worker tasks land and Atlas has intel for the pod switcher. First UI task once unblocked: Phase 2 `store.tsx` access gate - swap `rpc("is_owner")` for `rpc("my_access")`, add `pod` filter state and the admin pod switcher on Review, using Atlas tokens only.

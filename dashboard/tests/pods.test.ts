import assert from "node:assert/strict";
import { test } from "node:test";
import { DEMO_PODS, demoAccess, demoEntry, demoSnapshot } from "../lib/demo.ts";
import { NEXT_STEP, canReview, cents, eventText, hasAccess, isAdminView, isMemberOnly, monthOf, parseAccess, parseCents, podSnapshot, reversedIds, scopedPod, stuckPosts,
  usd } from "../lib/pods.ts";
import type { Pod } from "../lib/types.ts";

const ZO = parseAccess({ admin: true, pods: [{ id: "pod-1", slug: "pod-1", name: "Pod 1", role: "owner" }] });
const P2_OWNER = parseAccess({ admin: false, pods: [{ id: "pod-2", slug: "pod-2", name: "Pod 2", role: "owner" }] });
const P2_MEMBER = parseAccess({ admin: false, pods: [{ id: "pod-2", slug: "pod-2", name: "Pod 2", role: "member" }] });

test("parseAccess: junk reads as no access", () => {
  assert.equal(hasAccess(parseAccess(null)), false);
  assert.equal(hasAccess(parseAccess({ admin: "yes", pods: [{}] })), false);
  assert.equal(hasAccess(ZO), true);
  assert.equal(hasAccess(P2_MEMBER), true);
});

test("canReview mirrors review_clip (D102, D103)", () => {
  const pods = DEMO_PODS;
  assert.equal(canReview({ pod_id: "pod-1" }, ZO, pods), true, "admin owns Pod 1");
  assert.equal(canReview({ pod_id: "pod-2" }, ZO, pods), false, "admin does not approve Pod 2");
  assert.equal(canReview({ pod_id: null }, ZO, pods), true, "untagged = admin");
  assert.equal(canReview({ pod_id: null }, P2_OWNER, pods), false);
  assert.equal(canReview({ pod_id: "pod-2" }, P2_OWNER, pods), true);
  assert.equal(canReview({ pod_id: "pod-1" }, P2_OWNER, pods), false);
  assert.equal(canReview({ pod_id: "pod-2" }, P2_MEMBER, pods), false, "members are read-only");
  const ended: Pod[] = pods.map((p) => (p.id === "pod-2" ? { ...p, status: "ended" } : p));
  assert.equal(canReview({ pod_id: "pod-2" }, P2_OWNER, ended), false, "ended pod loses tool access");
});

test("isMemberOnly / isAdminView gate brain tuning and Wake Up (D108)", () => {
  assert.equal(isMemberOnly(true, P2_MEMBER), true);
  assert.equal(isMemberOnly(true, P2_OWNER), false);
  assert.equal(isMemberOnly(true, ZO), false);
  assert.equal(isMemberOnly(false, P2_MEMBER), false, "pods off");
  assert.equal(isMemberOnly(true, null), false, "no access loaded");
  assert.equal(isMemberOnly(true, parseAccess(null)), false, "no access");
  assert.equal(isAdminView(true, ZO), true);
  assert.equal(isAdminView(true, P2_OWNER), false);
  assert.equal(isAdminView(true, P2_MEMBER), false);
  assert.equal(isAdminView(true, null), false);
  assert.equal(isAdminView(false, null), true, "pods off = single owner");
});

test("scope: admin picks, members are pinned", () => {
  assert.equal(scopedPod(ZO, null), null);
  assert.equal(scopedPod(ZO, "pod-2"), "pod-2");
  assert.equal(scopedPod(P2_MEMBER, null), "pod-2");
  assert.equal(scopedPod(P2_MEMBER, "pod-1"), "pod-2");
});

test("podSnapshot keeps one pod's clips and streamers", () => {
  const s = demoSnapshot(Date.parse("2026-11-20T18:00:00Z"));
  const p2 = podSnapshot(s, "pod-2");
  assert.ok(p2.clips.length > 0 && p2.clips.every((c) => c.pod_id === "pod-2"));
  assert.ok(p2.streamers.every((x) => x.pod_id === "pod-2"));
  assert.equal(podSnapshot(s, null), s);
  assert.ok(s.clips.some((c) => c.pod_id == null), "demo has an untagged clip");
});

test("stuckPosts matches the worker rule (< 20 plays at ~1 h, else ~2 h)", () => {
  const r = (clip_id: string, h: number, plays: number | null, platform: "youtube" | "x" = "youtube") =>
    ({ clip_id, platform, read_at: "2026-11-20T18:00:00Z", hours_since_post: h, plays });
  const flags = stuckPosts([r("a", 1.0, 12), r("a", 2.0, 400), r("b", 1.1, 25), r("c", 2.0, 5), r("d", 0.2, 1), r("e", 1.0, null), r("a", 1.0, 900, "x")]);
  assert.deepEqual(flags.map((f) => `${f.clip_id}:${f.platform}`).sort(), ["a:youtube", "c:youtube"]);
});

test("money is display formatting only", () => {
  assert.equal(usd(150050), "$1,500.50");
  assert.equal(usd(-8501), "-$85.01");
  assert.equal(cents(0), "0.00");
  assert.equal(monthOf(Date.parse("2026-11-30T23:59:00Z")), "2026-11-01");
});

test("ledger input and steps", () => {
  assert.equal(parseCents("1,234.5"), 123450);
  assert.equal(parseCents("$100.01"), 10001);
  for (const bad of ["", "0", "-5", "1.234", "abc", "1e3"]) assert.equal(parseCents(bad), null, bad);
  assert.equal(NEXT_STEP.pending, "cleared");
  assert.equal(NEXT_STEP.approved, "paid");
  assert.equal(NEXT_STEP.paid, null, "paid is final");
});

test("demo ledger mirrors the database split and statement view", () => {
  const e = demoEntry({ id: "x", pod_id: "pod-1", source_ref: "r", campaign_id: null, gross_cents: 10001, created_at: "2026-11-20T00:00:00Z" });
  assert.equal(e.agency_cut_cents, 1500);
  assert.equal(e.pod_net_cents, 8501);
  const s = demoSnapshot(Date.parse("2026-11-20T18:00:00Z"));
  const p1 = s.statements.filter((r) => r.pod_id === "pod-1");
  const net = p1.reduce((a, r) => a + r.pod_net_cents, 0);
  assert.equal(net, s.ledger.filter((r) => r.pod_id === "pod-1").reduce((a, r) => a + r.pod_net_cents, 0));
  for (const r of p1) assert.equal(r.pending_net_cents + r.owed_net_cents + r.paid_net_cents, r.pod_net_cents);
  assert.ok(reversedIds(s.ledger).has("le-4"));
  assert.ok(s.ledgerEvents.some((ev) => eventText(ev) === "Marked paid · ref T-881"));
  assert.equal(podSnapshot(s, "pod-2").ledger.every((r) => r.pod_id === "pod-2"), true);
});

test("demo login switch", () => {
  assert.equal(demoAccess("").admin, true);
  assert.deepEqual(demoAccess("?as=pod-2&role=member").pods[0].role, "member");
});

import assert from "node:assert/strict";
import { test } from "node:test";
import { DEMO_PODS, demoAccess, demoSnapshot } from "../lib/demo.ts";
import { canReview, hasAccess, parseAccess, podSnapshot, scopedPod } from "../lib/pods.ts";
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

test("demo login switch", () => {
  assert.equal(demoAccess("").admin, true);
  assert.deepEqual(demoAccess("?as=pod-2&role=member").pods[0].role, "member");
});

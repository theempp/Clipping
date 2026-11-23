// Halo Pro review page data (D116): every number comes from real rows; missing data is null, never invented.
import assert from "node:assert/strict";
import test from "node:test";
import { demoSnapshot } from "../lib/demo.ts";
import {
  basePlan, channels7d, clipHeat, clipScore, hookStart, pipelineToday, postablePlatforms, queueSummary, spendView,
  streamerColor, subScores, upcomingPosts,
} from "../lib/halo.ts";
import { editPayload } from "../lib/logic.ts";
import type { Clip, Snapshot } from "../lib/types.ts";

const NOW = Date.parse("2026-11-23T18:00:00Z");
const clip = (p: Partial<Clip> = {}): Clip => ({
  id: "c1", job_id: "j1", streamer_id: "s1", channel_key: "twitch:lacy", state: "pending_review", title: "Lacy wins",
  hook: "HE DID IT", description: null, category: "gaming", confidence: 0.8, detector_score: 3, score_10: 8, hook_type: null,
  moment_at: new Date(NOW - 10 * 60_000).toISOString(), duration_s: 20, storage_path: null, thumb_path: null, qa: {}, judge: {},
  revision: 0, reviewed_at: null, created_at: new Date(NOW - 5 * 60_000).toISOString(), ...p,
});

test("score: judge 0-100 first, else score_10 x10, else null", () => {
  assert.equal(clipScore(clip({ judge: { score: 91.4 } })), 91);
  assert.equal(clipScore(clip({ judge: {} })), 80);
  assert.equal(clipScore(clip({ judge: {}, score_10: null })), null);
});

test("sub-scores come from the judge's parts; trend and est. views stay empty until the judge sends them", () => {
  const s = subScores(clip({ judge: { parts: { judged: { hook: 9.4, payoff: 8.8 } } } }));
  assert.deepEqual(s, { hook: 94, payoff: 88, trend: null, views: null });
  assert.deepEqual(subScores(clip()), { hook: null, payoff: null, trend: null, views: null });
});

test("queue summary counts new clips (under 15 min) and averages real scores only", () => {
  const q = [clip({ id: "a" }), clip({ id: "b", score_10: null, created_at: new Date(NOW - 40 * 60_000).toISOString() })];
  assert.deepEqual(queueSummary(q, NOW), { waiting: 2, avg: 80, fresh: 1 });
  assert.deepEqual(queueSummary([], NOW), { waiting: 0, avg: null, fresh: 0 });
});

test("chat heat needs readings around the moment, else null", () => {
  const c = clip();
  assert.equal(clipHeat([], c), null);
  const t = Date.parse(c.moment_at);
  const cands = [1, 2, 3, 4].map((i) => ({ channel_key: "twitch:lacy", moment_at: new Date(t - i * 60_000).toISOString(), score: i === 1 ? 4 : 1, outcome: "kept" }));
  const h = clipHeat(cands, c)!;
  assert.equal(h.h.length, 18);
  assert.ok(h.ratio >= 2);
  assert.ok(h.spike.some(Boolean));
});

test("today's funnel uses only today's rows", () => {
  const s = demoSnapshot(NOW);
  const f = pipelineToday(s, NOW);
  assert.ok(f.found >= f.judged);
  const empty = { ...s, candidates: [], clips: [], publications: [] } as Snapshot;
  assert.deepEqual(pipelineToday(empty, NOW), { found: 0, judged: 0, passed: 0, okayed: 0, posted: 0 });
});

test("spend: no daily rows means no sparkline and no 'today' number", () => {
  const s = { ...demoSnapshot(NOW), spend: [{ kind: "grok", usd: 10 }] } as Snapshot;
  const v = spendView(s, [], NOW);
  assert.equal(v.total, 10);
  assert.equal(v.series, null);
  assert.equal(v.today, null);
  assert.ok(v.pace != null && v.pace > 10);
});

test("channels: 7-day gain and growth from snapshots, null without data", () => {
  const s = demoSnapshot(NOW);
  const c = channels7d(s, NOW);
  assert.ok(c.youtube.views != null && c.youtube.gained != null);
  const none = channels7d({ ...s, history: [], live: [] } as Snapshot, NOW);
  assert.deepEqual(none.x, { views: null, gained: null, growth: null });
});

test("posting goes only to platforms with an active account; long-form never counts as an upcoming post", () => {
  assert.deepEqual(postablePlatforms([{ id: "1", platform: "youtube", label: "a", active: true, streamer_id: null },
    { id: "2", platform: "x", label: "b", active: false, streamer_id: null }]), ["youtube"]);
  const up = upcomingPosts([clip({ id: "a", state: "approved" }), clip({ id: "b", state: "approved", category: "longform" }), clip({ id: "c", state: "scheduled" })],
    [{ id: "p", clip_id: "c", status: "posted", url: null, posted_at: null, created_at: "", platform: "x", label: null }]);
  assert.deepEqual(up.map((c) => c.id), ["a"]);
});

test("editor base plan: no zoom (D112), unchanged plan sends nothing", () => {
  const b = basePlan(clip({ judge: { hook_window: "0:02-0:05", emphasis_words: ["WIN"] } }));
  assert.equal(b.zoom, 1);
  assert.equal(b.headline, "HE DID IT");
  assert.deepEqual(b.emphasis_words, ["win"]);
  assert.deepEqual(editPayload(b, b), {});
  assert.equal(hookStart(clip({ judge: { hook_window: "0:02-0:05" } })), 2);
  assert.equal(hookStart(clip()), null);
});

test("streamer colours: fixed for the roster, a token for everyone else", () => {
  assert.equal(streamerColor("lacy"), "#ff7a59");
  assert.match(streamerColor("someone"), /^var\(--/);
});

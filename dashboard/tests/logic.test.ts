import assert from "node:assert/strict";
import { test } from "node:test";
import { cleanNote, downloadName, editNote, mmss, openSubmissions, pcState, rankQueue, secondsLeft, weekStats } from "../lib/logic.ts";
import { demoSnapshot } from "../lib/demo.ts";
import { heatStrip } from "../lib/view.ts";
import type { Clip, EditPlan, Heartbeat, Submission } from "../lib/types.ts";

const NOW = Date.parse("2026-11-20T18:00:00Z");
const clip = (p: Partial<Clip>): Clip => ({
  id: "x", job_id: "j", streamer_id: null, channel_key: "twitch:lacy", state: "pending_review", title: null, hook: null,
  description: null, category: null, confidence: null, detector_score: null, score_10: null, hook_type: null,
  moment_at: "2026-11-20T17:00:00Z", duration_s: null, storage_path: null, thumb_path: null, qa: {}, judge: {},
  revision: 0, reviewed_at: null, created_at: "2026-11-20T17:00:00Z", ...p,
});

test("queue: only pending_review, score desc, then confidence, then oldest", () => {
  const q = rankQueue([
    clip({ id: "a", score_10: 7, confidence: 0.9 }),
    clip({ id: "b", score_10: 9, confidence: 0.5 }),
    clip({ id: "c", score_10: 7, confidence: 0.95 }),
    clip({ id: "d", score_10: null, confidence: 0.99 }),
    clip({ id: "e", score_10: 10, state: "approved" }),
    clip({ id: "f", score_10: 7, confidence: 0.9, created_at: "2026-11-20T16:00:00Z" }),
  ]);
  assert.deepEqual(q.map((c) => c.id), ["b", "c", "f", "a", "d"]);
});

test("week stats: 7 days, approve streak, approval rate, average score", () => {
  const at = (daysAgo: number) => new Date(NOW - daysAgo * 86400_000).toISOString();
  const w = weekStats([
    clip({ id: "1", state: "approved", reviewed_at: at(0), created_at: at(0), score_10: 8 }),
    clip({ id: "2", state: "published", reviewed_at: at(1), created_at: at(1), score_10: 6 }),
    clip({ id: "3", state: "rejected", created_at: at(1), score_10: 4 }),
    clip({ id: "4", state: "approved", reviewed_at: at(3), created_at: at(3) }),
    clip({ id: "5", state: "pending_review", created_at: at(0) }),
  ], NOW);
  assert.equal(w.days.length, 7);
  assert.equal(w.days[6].today, true);
  assert.equal(w.days[6].made, 2);
  assert.equal(w.streak, 2);
  assert.equal(w.approved7, 3);
  assert.equal(w.approvalRate, 0.75);
  assert.equal(w.avgScore, 6);
});

const hb = (secAgo: number, status: Heartbeat["status"]): Heartbeat =>
  ({ worker_id: "pc", seen_at: new Date(NOW - secAgo * 1000).toISOString(), status });

test("pc state comes from the heartbeat, never from the switch alone", () => {
  assert.equal(pcState(null, true, NOW), "offline");
  assert.equal(pcState(hb(120, { awake: true, live: ["twitch:lacy"] }), true, NOW), "offline");
  assert.equal(pcState(hb(5, { awake: false }), true, NOW), "waking");
  assert.equal(pcState(hb(5, { awake: true, live: [] }), false, NOW), "sleeping");
  assert.equal(pcState(hb(5, { awake: true, live: ["twitch:lacy"] }), true, NOW), "watching");
  assert.equal(pcState(hb(5, { awake: true, live: [] }), true, NOW), "idle");
  assert.equal(pcState(hb(5, { awake: false }), false, NOW), "asleep");
});

test("30-minute countdown runs from the deadline and closes at zero", () => {
  const s = { deadline_at: new Date(NOW + 18 * 60_000 + 42_000).toISOString(), submitted_at: null };
  assert.equal(mmss(secondsLeft(s, NOW)), "18:42");
  assert.equal(secondsLeft({ ...s, submitted_at: "x" }, NOW), 0);
  assert.equal(secondsLeft(s, NOW + 31 * 60_000), 0);
  const sub = (id: string, minLeft: number, submitted: string | null = null): Submission => ({
    id, publication_id: id, campaign_id: null, post_url: "https://x.com/a", posted_at: "", submitted_at: submitted,
    deadline_at: new Date(NOW + minLeft * 60_000).toISOString(), status: "open", seconds_left: 0,
  });
  assert.deepEqual(openSubmissions([sub("late", 20), sub("soon", 3), sub("done", 10, "y"), sub("gone", -1)], NOW).map((s) => s.id),
    ["soon", "late"]);
});

test("revision box text is trimmed and bounded", () => {
  assert.equal(cleanNote("  cut   the first 2 s \n"), "cut the first 2 s");
  assert.equal(cleanNote("ok"), null);
  assert.equal(cleanNote("x".repeat(501)), null);
});

test("download names are safe on Windows and phones", () => {
  const c = clip({ title: 'Lacy loses it: 1v4 "clutch"?' });
  assert.equal(downloadName(c, { id: "s", slug: "lacy", display_name: "Lacy", twitch_login: "lacy", kick_slug: null, avatar_url: null }),
    "lacy-lacy-loses-it-1v4-clutch.mp4");
});

test("heat strip buckets the last hour into 12 levels", () => {
  const h = heatStrip([
    { channel_key: "twitch:lacy", moment_at: new Date(NOW - 2 * 60_000).toISOString(), score: 3.4, outcome: "kept" },
    { channel_key: "twitch:lacy", moment_at: new Date(NOW - 59 * 60_000).toISOString(), score: 1.2, outcome: "dropped" },
    { channel_key: "twitch:clix", moment_at: new Date(NOW - 2 * 60_000).toISOString(), score: 9, outcome: "kept" },
  ], ["twitch:lacy"], NOW);
  assert.equal(h.length, 12);
  assert.equal(h[11], 3);
  assert.equal(h[0], 1);
});

test("demo data has a live queue, an open countdown and a heartbeat", () => {
  const d = demoSnapshot(NOW);
  assert.ok(rankQueue(d.clips).length >= 5);
  assert.equal(openSubmissions(d.submissions, NOW).length, 1);
  assert.equal(pcState(d.heartbeat, d.control.awake, NOW), "watching");
});

test("editor note lists only what changed (untouched zoom and headline are left out)", () => {
  const base: EditPlan = { trim_in: 0, trim_out: 30, crop_x: 0.5, zoom: 1.12, headline: "He did it", caption_style: "words", splits: [], emphasis_words: ["no"] };
  assert.equal(editNote(base, base), "Editor: no changes yet");
  assert.equal(editNote({ ...base, trim_in: 2 }, base), "Editor: trim 2.0s-30.0s");
  assert.equal(editNote({ ...base, zoom: 1.3, headline: "New one" }, base), 'Editor: zoom 130% · headline "New one"');
});

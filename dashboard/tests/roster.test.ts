import assert from "node:assert/strict";
import { test } from "node:test";
import { demoSnapshot } from "../lib/demo.ts";
import { rosterSections, streamerViews } from "../lib/view.ts";

const NOW = Date.parse("2026-11-21T18:00:00Z");

test("rail splits the core roster from the GTA-6-only streamers (D069)", () => {
  const snap = demoSnapshot(NOW);
  const { core, gta6 } = rosterSections(streamerViews(snap, NOW), true);
  assert.deepEqual(core.map((v) => v.s.slug).sort(), ["adinross", "stableronaldo", "xqc"]);
  assert.deepEqual(gta6.map((v) => v.s.slug).sort(), ["ishowspeed", "kaicenat"]);
});

test("streamers off the roster (archived) are hidden; no roster = everyone in core", () => {
  const snap = demoSnapshot(NOW);
  snap.streamers.push({ id: "s-lacy", slug: "lacy", display_name: "Lacy", twitch_login: "lacy", kick_slug: null, avatar_url: null });
  const views = streamerViews(snap, NOW);
  assert.ok(!rosterSections(views, true).core.some((v) => v.s.slug === "lacy"));
  const old = rosterSections(streamerViews({ ...snap, heartbeat: { ...snap.heartbeat!, status: {} } }, NOW), false);
  assert.equal(old.core.length, 6);
  assert.equal(old.gta6.length, 0);
});

import assert from "node:assert/strict";
import { test } from "node:test";
import { demoSnapshot } from "../lib/demo.ts";
import { rosterSections, streamerViews } from "../lib/view.ts";

const NOW = Date.parse("2026-11-21T18:00:00Z");

test("rail splits the core roster from the GTA-6-only streamers (D069)", () => {
  const snap = demoSnapshot(NOW);
  const { core, gta6 } = rosterSections(streamerViews(snap, NOW), true);
  assert.deepEqual(core.map((v) => v.s.slug).sort(), ["adinross", "jynxzi", "lacy", "stableronaldo", "xqc"]);
  assert.deepEqual(gta6.map((v) => v.s.slug).sort(), ["ishowspeed", "kaicenat"]);
});

test("streamers off the roster (archived) are hidden; no roster = everyone in core", () => {
  const snap = demoSnapshot(NOW);
  snap.streamers.push({ id: "s-clix", slug: "clix", display_name: "Clix", twitch_login: "clix", kick_slug: null, avatar_url: null });
  const views = streamerViews(snap, NOW);
  assert.ok(!rosterSections(views, true).core.some((v) => v.s.slug === "clix"));
  const old = rosterSections(streamerViews({ ...snap, heartbeat: { ...snap.heartbeat!, status: {} } }, NOW), false);
  assert.equal(old.core.length, 8);
  assert.equal(old.gta6.length, 0);
});

test("live player: live platform wins, Twitch needs the page host as parent, Kick has no chat", async () => {
  const { livePlayer } = await import("../lib/view.ts");
  const s = { id: "s", slug: "xqc", display_name: "xQc", twitch_login: "xqc", kick_slug: "xqc", avatar_url: null };
  const tw = livePlayer(s, null, "localhost")!;
  assert.equal(tw.platform, "twitch");
  assert.match(tw.src, /parent=localhost/);
  assert.match(tw.src, /muted=true/);
  const kk = livePlayer(s, "kick:xqc", "localhost")!;
  assert.equal(kk.platform, "kick");
  assert.equal(kk.chat, null);
  assert.equal(livePlayer({ ...s, kick_slug: null }, null, ""), null);
});

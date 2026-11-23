import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { parseKick, parseTwitch, parseX, parseYouTube, pollAll, sourcesConfigured } from "../lib/live/sources.ts";
import { editPayload, emphasisWords } from "../lib/logic.ts";
import { demoSnapshot } from "../lib/demo.ts";
import { LIVE_FRESH_S, streamerViews } from "../lib/view.ts";
import type { EditPlan, LiveStat } from "../lib/types.ts";

const NOW = Date.parse("2026-11-20T18:00:00Z");
const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

test("twitch: live and offline logins, avatars, case-insensitive", () => {
  const rows = parseTwitch(["Lacy", "xqc"],
    { data: [{ user_login: "lacy", viewer_count: 41200, title: "GTA", game_name: "Grand Theft Auto VI", started_at: "2026-11-20T16:00:00Z" }] },
    { data: [{ login: "lacy", profile_image_url: "https://img/lacy.png" }, { login: "xqc", profile_image_url: "" }] });
  assert.equal(rows[0].key, "twitch:lacy");
  assert.equal(rows[0].is_live, true);
  assert.equal(rows[0].viewers, 41200);
  assert.equal(rows[0].avatar_url, "https://img/lacy.png");
  assert.deepEqual([rows[1].is_live, rows[1].viewers, rows[1].avatar_url, rows[1].title], [false, null, null, null]);
});

test("twitch/kick parsers survive junk bodies", () => {
  assert.equal(parseTwitch(["a"], null, undefined)[0].is_live, false);
  const k = parseKick(["adinross"], { nope: 1 }, "x");
  assert.equal(k[0].is_live, null); // unknown channel: not "offline"
});

test("kick: live viewers only while live, picture by broadcaster id", () => {
  const ch = { data: [
    { slug: "adinross", broadcaster_user_id: 7, stream_title: "IRL", category: { name: "Just Chatting" }, stream: { is_live: true, viewer_count: "9000", start_time: "2026-11-20T17:00:00Z" } },
    { slug: "other", broadcaster_user_id: 8, stream: { is_live: false, viewer_count: 50 } },
  ] };
  const [a, b] = parseKick(["AdinRoss", "other"], ch, { data: [{ user_id: 7, profile_picture: "https://img/a.png" }] });
  assert.deepEqual([a.is_live, a.viewers, a.game, a.avatar_url], [true, 9000, "Just Chatting", "https://img/a.png"]);
  assert.deepEqual([b.is_live, b.viewers, b.started_at], [false, null, null]);
});

test("youtube: hidden subscribers stay unknown, empty body is null", () => {
  const r = parseYouTube({ items: [{ statistics: { subscriberCount: "1200", hiddenSubscriberCount: true, viewCount: "50000", videoCount: "31" }, snippet: { title: "Own" } }] });
  assert.deepEqual([r?.followers, r?.views, r?.posts], [null, 50000, 31]);
  assert.equal(parseYouTube({ items: [] }), null);
  assert.equal(parseX({ errors: [{}] }), null);
  assert.equal(parseX({ data: { username: "own", public_metrics: { followers_count: 88, tweet_count: 4 } } })?.followers, 88);
});

test("a source is on only when every key it needs is set; TikTok stays manual", () => {
  assert.deepEqual(sourcesConfigured({ TWITCH_CLIENT_ID: "a" }), { twitch: false, kick: false, youtube: false, x: false, tiktok: "manual" });
  assert.equal(sourcesConfigured({ X_BEARER_TOKEN: "t", X_USERNAME: "u" }).x, true);
});

test("pollAll: missing keys make no requests", async () => {
  let calls = 0;
  globalThis.fetch = (async () => { calls++; throw new Error("no"); }) as typeof fetch;
  const r = await pollAll([{ twitch_login: "lacy", kick_slug: null }], {});
  assert.deepEqual(r, { rows: [], errors: {} });
  assert.equal(calls, 0);
});

test("pollAll: one failing source is reported without blanking the others or leaking keys", async () => {
  globalThis.fetch = (async (input: string | URL | Request) => {
    const u = String(input);
    if (u.includes("googleapis")) return new Response("{}", { status: 403 });
    if (u.includes("api.x.com")) return Response.json({ data: { username: "own", public_metrics: { followers_count: 5, tweet_count: 1 } } });
    throw new Error(`unexpected ${u}`);
  }) as typeof fetch;
  const env = { YOUTUBE_API_KEY: "SECRET-KEY", YOUTUBE_CHANNEL_ID: "c", X_BEARER_TOKEN: "t", X_USERNAME: "own" };
  const r = await pollAll([], env);
  assert.equal(r.rows.length, 1);
  assert.equal(r.rows[0].key, "x:own");
  assert.equal(r.errors.youtube, "www.googleapis.com 403");
  assert.ok(!JSON.stringify(r).includes("SECRET-KEY"));
});

test("streamer views: fresh API rows win, stale rows are ignored", () => {
  const snap = demoSnapshot(NOW);
  const row = (updatedAgoS: number): LiveStat => ({
    key: "twitch:xqc", kind: "streamer", platform: "twitch", is_live: true, viewers: 77777, followers: null, views: null,
    posts: null, title: "api title", game: null, started_at: null, avatar_url: "https://img/x.png",
    updated_at: new Date(NOW - updatedAgoS * 1000).toISOString(),
  });
  const xqc = (live: LiveStat[]) => streamerViews({ ...snap, live, heartbeat: null }, NOW).find((v) => v.s.slug === "xqc")!;
  const fresh = xqc([row(10)]);
  assert.deepEqual([fresh.live, fresh.viewers, fresh.title], [true, 77777, "api title"]);
  const stale = xqc([row(LIVE_FRESH_S + 5)]);
  assert.deepEqual([stale.live, stale.viewers], [false, null]);
});

const BASE: EditPlan = { trim_in: 0, trim_out: 30, crop_x: 0.5, zoom: 1.12, headline: "Old", caption_style: "words", splits: [], emphasis_words: ["he", "hit"] };

test("editor payload: untouched plan sends nothing the worker would apply", () => {
  assert.deepEqual(editPayload(BASE, BASE), {});
});

test("editor payload: changed fields only, in the worker's names and clip seconds", () => {
  const p = editPayload({ ...BASE, trim_in: 2, trim_out: 20, crop_x: 0.3, zoom: 1, caption_style: "line",
    headline: "  New  ", emphasis_words: ["map"], splits: [5] }, BASE);
  assert.deepEqual(p, { trim_in: 2, trim_out: 20, crop_x: 0.3, zoom: 1, caption_style: "line",
    emphasis_words: ["map"], headline: "New", splits: [5] });
  assert.deepEqual(editPayload({ ...BASE, headline: "   " }, BASE), {}); // blank headline never wipes the title
});

test("emphasis words: typed caption box -> clean worker list", () => {
  assert.deepEqual(emphasisWords("  NO WAY!  \"HE\" "), ["no", "way", "he"]);
  assert.equal(emphasisWords("a b c d e f g h i j k l m n").length, 12);
});

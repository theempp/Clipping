import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { estimateUsd, findDuplicate, linkKey, linkLabel, parseTime } from "../lib/links.ts";
import type { LinkJob } from "../lib/links.ts";

// Shared with public.link_key (supabase/tests/links_test.sql) and clipworker/links.py.
const CASES: [string, string | null][] = JSON.parse(readFileSync(new URL("../../docs/link_cases.json", import.meta.url), "utf8"));

test("link keys match the shared cases", () => {
  for (const [url, want] of CASES) assert.equal(linkKey(url), want, url);
});

test("labels, times, estimate", () => {
  assert.equal(linkLabel("twitch:vod:1"), "Twitch VOD");
  assert.equal(linkLabel("kick:clip:a"), "Kick clip");
  assert.equal(linkLabel("youtube:dQw4w9WgXcQ"), "YouTube video");
  assert.equal(linkLabel(null), null);
  assert.equal(parseTime("1:02:03"), 3723);
  assert.equal(parseTime("90"), 90);
  assert.equal(parseTime(""), null);
  assert.ok(Number.isNaN(parseTime("1h")));
  assert.equal(estimateUsd(6), 0.015);
  assert.equal(estimateUsd(99), 0.05);
});

test("duplicate = same key and range, not failed or canceled", () => {
  const j = (p: Partial<LinkJob>) => ({ url_key: "twitch:vod:1", start_s: null, end_s: null, status: "done", ...p }) as LinkJob;
  assert.ok(findDuplicate([j({})], "twitch:vod:1", null, null));
  assert.equal(findDuplicate([j({ status: "failed" })], "twitch:vod:1", null, null), null);
  assert.equal(findDuplicate([j({})], "twitch:vod:1", 60, null), null);
});

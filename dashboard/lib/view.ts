// Derived view data used by more than one screen.
import { liveKeys, rankQueue, streamerKeys } from "./logic.ts";
import type { Candidate, Snapshot, Streamer } from "./types.ts";

export type StreamerView = {
  s: Streamer;
  live: boolean;
  key: string | null;           // channel key that is live (or the first known one)
  viewers: number | null;
  since: string | null;
  heat: number[];               // 12 buckets x 5 min, levels 0-3
  queued: number;
};

/** 12-step heat strip: best detector score per 5-minute bucket over the last hour. */
export function heatStrip(cands: Candidate[], keys: string[], now: number, steps = 12, bucketMin = 5): number[] {
  const out = new Array(steps).fill(0) as number[];
  const start = now - steps * bucketMin * 60_000;
  for (const c of cands) {
    if (!keys.includes(c.channel_key)) continue;
    const t = Date.parse(c.moment_at);
    if (t < start || t > now) continue;
    const i = Math.min(steps - 1, Math.floor((t - start) / (bucketMin * 60_000)));
    const lvl = c.score >= 3 ? 3 : c.score >= 2 ? 2 : c.score >= 1 ? 1 : 0;
    out[i] = Math.max(out[i], lvl);
  }
  return out;
}

export function streamerViews(snap: Snapshot, now: number): StreamerView[] {
  const live = liveKeys(snap.heartbeat, now);
  const queue = rankQueue(snap.clips);
  return snap.streamers
    .map((s) => {
      const keys = streamerKeys(s);
      const k = keys.find((x) => live.has(x)) ?? null;
      return {
        s,
        live: k !== null,
        key: k ?? keys[0] ?? null,
        viewers: k ? snap.heartbeat?.status.viewers?.[k] ?? null : null,
        since: k ? snap.heartbeat?.status.live_since?.[k] ?? null : null,
        heat: heatStrip(snap.candidates, keys, now),
        queued: queue.filter((c) => c.streamer_id === s.id).length,
      };
    })
    .sort((a, b) => Number(b.live) - Number(a.live) || a.s.display_name.localeCompare(b.s.display_name));
}

export function fmtViewers(n: number | null): string {
  if (n == null) return "";
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

export function liveClock(since: string | null, now: number): string {
  if (!since) return "";
  const s = Math.max(0, Math.floor((now - Date.parse(since)) / 1000));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}`;
}

export function monthSpend(snap: Snapshot): { total: number; grok: number } {
  const total = snap.spend.reduce((a, r) => a + r.usd, 0);
  const grok = snap.spend.filter((r) => r.kind === "grok").reduce((a, r) => a + r.usd, 0);
  return { total, grok };
}

/** Avatar background: a fixed gradient per streamer from the Stage palette. */
export function avatarBg(slug: string): string {
  const g = [
    "linear-gradient(135deg,#ff8962,#7f5e4d)",
    "linear-gradient(135deg,#415a6a,#262a2d)",
    "linear-gradient(135deg,#60f3bd,#2f6e58)",
    "linear-gradient(135deg,#9aa6ad,#3a3f43)",
  ];
  let h = 0;
  for (const ch of slug) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return g[h % g.length];
}

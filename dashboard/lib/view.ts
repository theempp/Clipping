// Derived view data used by more than one screen.
import { liveKeys, rankQueue, streamerKeys } from "./logic.ts";
import type { Candidate, LiveStat, Snapshot, StatPoint, Streamer } from "./types.ts";

export type StreamerView = {
  s: Streamer;
  live: boolean;
  key: string | null;           // channel key that is live (or the first known one)
  viewers: number | null;
  since: string | null;
  game: string | null;
  title: string | null;
  heat: number[];               // 12 buckets x 5 min, levels 0-3
  queued: number;
  group: "core" | "gta6_only";
  inRoster: boolean;
};

/** Rail sections (D069): the core roster, then the GTA-6-only streamers. With a roster in
 * the heartbeat, streamers not on it (archived) are left out; older workers show everyone as core. */
export function rosterSections(views: StreamerView[], hasRoster: boolean) {
  const on = hasRoster ? views.filter((v) => v.inRoster) : views;
  return { core: on.filter((v) => v.group === "core"), gta6: on.filter((v) => v.group === "gta6_only") };
}

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

/** A platform row counts as current for this long; older rows fall back to the PC heartbeat. */
export const LIVE_FRESH_S = 300;

/** Lacy leads every streamer list (D091), then live first, then A-Z. */
export const FIRST_SLUG = "lacy";

export function streamerViews(snap: Snapshot, now: number): StreamerView[] {
  const live = liveKeys(snap.heartbeat, now);
  const queue = rankQueue(snap.clips);
  const roster = snap.heartbeat?.status.roster ?? {};
  const rows = new Map((snap.live ?? [])
    .filter((r) => r.kind === "streamer" && (now - Date.parse(r.updated_at)) / 1000 < LIVE_FRESH_S)
    .map((r) => [r.key, r]));
  return snap.streamers
    .map((s): StreamerView => {
      const keys = streamerKeys(s);
      // Platform API (Realtime) wins over the PC heartbeat: it works even when the PC is asleep.
      const kApi = keys.find((x) => rows.get(x)?.is_live) ?? null;
      const k = kApi ?? keys.find((x) => live.has(x)) ?? null;
      const row = k ? rows.get(k) : rows.get(keys[0] ?? "");
      const rk = keys.find((x) => x in roster);
      const pic = s.avatar_url ?? keys.map((x) => rows.get(x)?.avatar_url).find(Boolean) ?? null;
      return {
        group: rk ? roster[rk] : "core",
        inRoster: rk !== undefined,
        s: pic === s.avatar_url ? s : { ...s, avatar_url: pic },
        live: k !== null,
        key: k ?? keys[0] ?? null,
        viewers: k ? (kApi ? row?.viewers : null) ?? snap.heartbeat?.status.viewers?.[k] ?? null : null,
        since: k ? (kApi ? row?.started_at : null) ?? snap.heartbeat?.status.live_since?.[k] ?? null : null,
        game: k ? (kApi ? row?.game : null) ?? snap.heartbeat?.status.games?.[k] ?? null : null,
        title: k && kApi ? row?.title ?? null : null,
        heat: heatStrip(snap.candidates, keys, now),
        queued: queue.filter((c) => c.streamer_id === s.id).length,
      };
    })
    .sort((a, b) => Number(b.s.slug === FIRST_SLUG) - Number(a.s.slug === FIRST_SLUG)
      || Number(b.live) - Number(a.live) || a.s.display_name.localeCompare(b.s.display_name));
}

/** Zo's own channels (YouTube, X, TikTok) from live_stats. */
export function ownChannels(snap: Snapshot): Record<"youtube" | "x" | "tiktok", LiveStat | null> {
  const get = (p: string) => snap.live.find((r) => r.kind === "own" && r.platform === p) ?? null;
  return { youtube: get("youtube"), x: get("x"), tiktok: get("tiktok") };
}

/** Series for one metric of one key, oldest first. */
export function series(snap: Snapshot, key: string, metric: string): StatPoint[] {
  return snap.history.filter((p) => p.key === key && p.metric === metric).sort((a, b) => a.at.localeCompare(b.at));
}

/** Fallback picture when the platform has not given one yet: a public avatar mirror keyed by the channel name. */
export function avatarFallback(s: Streamer): string | null {
  if (s.twitch_login) return `https://unavatar.io/twitch/${encodeURIComponent(s.twitch_login)}?fallback=false`;
  return null;
}

export type LivePlayer = {
  platform: "twitch" | "kick";
  src: string;            // embeddable player, muted autoplay
  chat: string | null;    // embeddable chat (Twitch only; Kick blocks framing its chat)
  watch: string;          // the channel page, for "open in a new tab"
};

/** Live player for a streamer. Uses the platform that is live right now, else Twitch, else Kick.
 * Twitch needs `parent` = the page's hostname or it refuses to play. */
export function livePlayer(s: Streamer, liveKey: string | null, host: string): LivePlayer | null {
  const want = liveKey?.split(":")[0];
  const tw = s.twitch_login, kk = s.kick_slug;
  const useKick = kk && (want === "kick" || !tw);
  if (useKick) {
    const k = encodeURIComponent(kk);
    return { platform: "kick", src: `https://player.kick.com/${k}?autoplay=true&muted=true`, chat: null, watch: `https://kick.com/${k}` };
  }
  if (!tw || !host) return null;
  const c = encodeURIComponent(tw), p = encodeURIComponent(host);
  return {
    platform: "twitch",
    src: `https://player.twitch.tv/?channel=${c}&parent=${p}&muted=true&autoplay=true`,
    chat: `https://www.twitch.tv/embed/${c}/chat?parent=${p}&darkpopout`,
    watch: `https://www.twitch.tv/${c}`,
  };
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

/** D012: $100-$250 a month all-in; $250 is the ceiling the rings and meters measure against. */
export const BUDGET_USD = 250;

/** "2h 14m" / "48m" since a start time; "" when unknown. */
export function liveFor(since: string | null, now: number): string {
  if (!since) return "";
  const m = Math.max(0, Math.floor((now - Date.parse(since)) / 60_000));
  return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m`;
}

export function monthSpend(snap: Snapshot): { total: number; grok: number } {
  const total = snap.spend.reduce((a, r) => a + r.usd, 0);
  const grok = snap.spend.filter((r) => r.kind === "grok").reduce((a, r) => a + r.usd, 0);
  return { total, grok };
}

/** Per-streamer hue for card glows, from the Broadcast moodboard's card range (concept C: 165-265). */
export function streamerHue(slug: string): number {
  const fixed: Record<string, number> = { lacy: 225, jynxzi: 265, stableronaldo: 165 };
  if (slug in fixed) return fixed[slug];
  let h = 0;
  for (const ch of slug) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return 165 + (h % 101);
}

/** Avatar background (shown under the picture and when there is none): concept C avatar gradient, per-streamer hue. */
export function avatarBg(slug: string): string {
  const h = streamerHue(slug);
  return `linear-gradient(135deg,hsl(${h} 90% 78%),hsl(${h} 56% 51%))`;
}

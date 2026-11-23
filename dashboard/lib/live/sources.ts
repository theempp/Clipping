// Live numbers from the platforms. Server-only: every key comes from the server env, never the browser.
// Each source is optional; a missing key just means that source is skipped and reported as "not set".
import type { LiveStat } from "../types.ts";

type Env = Record<string, string | undefined>;
type Row = Omit<LiveStat, "updated_at">;

const blank = (key: string, kind: LiveStat["kind"], platform: LiveStat["platform"]): Row => ({
  key, kind, platform, is_live: null, viewers: null, followers: null, views: null, posts: null,
  title: null, game: null, started_at: null, avatar_url: null,
});

const num = (v: unknown): number | null => {
  const n = typeof v === "string" ? Number(v) : typeof v === "number" ? v : NaN;
  return Number.isFinite(n) ? n : null;
};

export type SourceState = { twitch: boolean; kick: boolean; youtube: boolean; x: boolean; tiktok: "manual" };

export function sourcesConfigured(env: Env): SourceState {
  return {
    twitch: !!(env.TWITCH_CLIENT_ID && env.TWITCH_CLIENT_SECRET),
    kick: !!(env.KICK_CLIENT_ID && env.KICK_CLIENT_SECRET),
    youtube: !!(env.YOUTUBE_API_KEY && env.YOUTUBE_CHANNEL_ID),
    x: !!(env.X_BEARER_TOKEN && env.X_USERNAME),
    tiktok: "manual",
  };
}

// ---------- parsers (pure, unit-tested) ----------

/** Helix /streams + /users -> one row per requested login. Offline logins come back with is_live=false. */
export function parseTwitch(logins: string[], streams: unknown, users: unknown): Row[] {
  const live = new Map<string, Record<string, unknown>>();
  for (const s of (streams as { data?: Record<string, unknown>[] })?.data ?? []) {
    live.set(String(s.user_login ?? "").toLowerCase(), s);
  }
  const pics = new Map<string, string>();
  for (const u of (users as { data?: Record<string, unknown>[] })?.data ?? []) {
    pics.set(String(u.login ?? "").toLowerCase(), String(u.profile_image_url ?? ""));
  }
  return logins.map((l) => {
    const k = l.toLowerCase(), s = live.get(k);
    return {
      ...blank(`twitch:${k}`, "streamer", "twitch"),
      is_live: !!s,
      viewers: s ? num(s.viewer_count) : null,
      title: s ? String(s.title ?? "") || null : null,
      game: s ? String(s.game_name ?? "") || null : null,
      started_at: s ? String(s.started_at ?? "") || null : null,
      avatar_url: pics.get(k) || null,
    };
  });
}

/** Kick public API /channels (+ /users for pictures). */
export function parseKick(slugs: string[], channels: unknown, users: unknown): Row[] {
  const bySlug = new Map<string, Record<string, unknown>>();
  for (const c of (channels as { data?: Record<string, unknown>[] })?.data ?? []) {
    bySlug.set(String(c.slug ?? "").toLowerCase(), c);
  }
  const pics = new Map<string, string>();
  for (const u of (users as { data?: Record<string, unknown>[] })?.data ?? []) {
    pics.set(String(u.user_id ?? ""), String(u.profile_picture ?? ""));
  }
  return slugs.map((sl) => {
    const k = sl.toLowerCase(), c = bySlug.get(k);
    const st = (c?.stream ?? {}) as Record<string, unknown>;
    const live = !!st.is_live;
    return {
      ...blank(`kick:${k}`, "streamer", "kick"),
      is_live: c ? live : null,
      viewers: live ? num(st.viewer_count) : null,
      title: c ? String(c.stream_title ?? "") || null : null,
      game: c ? String((c.category as Record<string, unknown> | undefined)?.name ?? "") || null : null,
      started_at: live ? String(st.start_time ?? "") || null : null,
      avatar_url: c ? pics.get(String(c.broadcaster_user_id ?? "")) || null : null,
    };
  });
}

export function parseYouTube(body: unknown): Row | null {
  const it = (body as { items?: Record<string, unknown>[] })?.items?.[0];
  if (!it) return null;
  const st = (it.statistics ?? {}) as Record<string, unknown>;
  const th = ((it.snippet as Record<string, unknown> | undefined)?.thumbnails ?? {}) as Record<string, { url?: string }>;
  return {
    ...blank("youtube:own", "own", "youtube"),
    followers: st.hiddenSubscriberCount ? null : num(st.subscriberCount),
    views: num(st.viewCount), posts: num(st.videoCount),
    title: String((it.snippet as Record<string, unknown> | undefined)?.title ?? "") || null,
    avatar_url: th.default?.url ?? null,
  };
}

export function parseX(body: unknown): Row | null {
  const d = (body as { data?: Record<string, unknown> })?.data;
  if (!d) return null;
  const m = (d.public_metrics ?? {}) as Record<string, unknown>;
  return {
    ...blank("x:own", "own", "x"),
    followers: num(m.followers_count), posts: num(m.tweet_count),
    title: String(d.username ?? "") || null,
    avatar_url: String(d.profile_image_url ?? "") || null,
  };
}

// ---------- fetchers ----------

const tokens = new Map<string, { token: string; exp: number }>();

async function appToken(name: "twitch" | "kick", env: Env): Promise<string> {
  const hit = tokens.get(name);
  if (hit && hit.exp > Date.now()) return hit.token;
  const url = name === "twitch" ? "https://id.twitch.tv/oauth2/token" : "https://id.kick.com/oauth/token";
  const id = name === "twitch" ? env.TWITCH_CLIENT_ID : env.KICK_CLIENT_ID;
  const secret = name === "twitch" ? env.TWITCH_CLIENT_SECRET : env.KICK_CLIENT_SECRET;
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: id ?? "", client_secret: secret ?? "", grant_type: "client_credentials" }),
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`${name} token ${r.status}`);
  const j = (await r.json()) as { access_token: string; expires_in: number };
  tokens.set(name, { token: j.access_token, exp: Date.now() + (j.expires_in - 300) * 1000 });
  return j.access_token;
}

async function getJson(url: string, headers: Record<string, string>, token?: "twitch" | "kick"): Promise<unknown> {
  const r = await fetch(url, { headers, cache: "no-store" });
  if (r.status === 401 && token) tokens.delete(token); // revoked/expired app token: fetch a new one next poll
  if (!r.ok) throw new Error(`${new URL(url).hostname} ${r.status}`); // never echo the URL: it can hold a key
  return r.json();
}

export async function fetchTwitch(logins: string[], env: Env): Promise<Row[]> {
  if (!logins.length) return [];
  const t = await appToken("twitch", env);
  const h = { "Client-Id": env.TWITCH_CLIENT_ID ?? "", Authorization: `Bearer ${t}` };
  const q = logins.slice(0, 100).map((l) => `user_login=${encodeURIComponent(l)}`).join("&");
  const qu = logins.slice(0, 100).map((l) => `login=${encodeURIComponent(l)}`).join("&");
  const [streams, users] = await Promise.all([
    getJson(`https://api.twitch.tv/helix/streams?first=100&${q}`, h, "twitch"),
    getJson(`https://api.twitch.tv/helix/users?${qu}`, h, "twitch"),
  ]);
  return parseTwitch(logins, streams, users);
}

export async function fetchKick(slugs: string[], env: Env): Promise<Row[]> {
  if (!slugs.length) return [];
  const t = await appToken("kick", env);
  const h = { Authorization: `Bearer ${t}`, Accept: "application/json" };
  const channels = await getJson(`https://api.kick.com/public/v1/channels?${slugs.map((s) => `slug=${encodeURIComponent(s)}`).join("&")}`, h, "kick");
  const ids = ((channels as { data?: Record<string, unknown>[] }).data ?? []).map((c) => c.broadcaster_user_id).filter(Boolean);
  const users = ids.length
    ? await getJson(`https://api.kick.com/public/v1/users?${ids.map((i) => `id=${encodeURIComponent(String(i))}`).join("&")}`, h).catch(() => ({}))
    : {};
  return parseKick(slugs, channels, users);
}

export async function fetchYouTube(env: Env): Promise<Row | null> {
  const u = `https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&id=${encodeURIComponent(env.YOUTUBE_CHANNEL_ID ?? "")}&key=${encodeURIComponent(env.YOUTUBE_API_KEY ?? "")}`;
  return parseYouTube(await getJson(u, {}));
}

export async function fetchX(env: Env): Promise<Row | null> {
  const u = `https://api.x.com/2/users/by/username/${encodeURIComponent(env.X_USERNAME ?? "")}?user.fields=public_metrics,profile_image_url`;
  return parseX(await getJson(u, { Authorization: `Bearer ${env.X_BEARER_TOKEN}` }));
}

/** Poll every configured source. Errors are collected per source, never thrown, so one outage cannot blank the rest. */
export async function pollAll(
  streamers: { twitch_login: string | null; kick_slug: string | null }[], env: Env,
): Promise<{ rows: Row[]; errors: Record<string, string> }> {
  const on = sourcesConfigured(env);
  const tw = streamers.map((s) => s.twitch_login).filter((x): x is string => !!x);
  const kk = streamers.map((s) => s.kick_slug).filter((x): x is string => !!x);
  const errors: Record<string, string> = {};
  const jobs: [string, Promise<Row[] | Row | null>][] = [];
  if (on.twitch) jobs.push(["twitch", fetchTwitch(tw, env)]);
  if (on.kick) jobs.push(["kick", fetchKick(kk, env)]);
  if (on.youtube) jobs.push(["youtube", fetchYouTube(env)]);
  if (on.x) jobs.push(["x", fetchX(env)]);
  const rows: Row[] = [];
  const out = await Promise.allSettled(jobs.map((j) => j[1]));
  out.forEach((r, i) => {
    if (r.status === "rejected") { errors[jobs[i][0]] = String(r.reason instanceof Error ? r.reason.message : r.reason); return; }
    const v = r.value;
    if (Array.isArray(v)) rows.push(...v); else if (v) rows.push(v);
  });
  return { rows, errors };
}

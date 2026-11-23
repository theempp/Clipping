// Paste-a-link (D115): the same canonical key rules as public.link_key (SQL) and clipworker/links.py.
// The database is the authority (it rejects bad links and duplicates); this gives instant feedback.

export type LinkPlatform = "twitch" | "kick" | "youtube" | "x";
export type LinkStatus = "queued" | "fetching" | "detecting" | "clipping" | "done" | "failed" | "canceled";

export type LinkJob = {
  id: string; url: string; url_key: string; platform: LinkPlatform; streamer: string | null;
  start_s: number | null; end_s: number | null; max_clips: number; full_frame: boolean;
  status: LinkStatus; detail: string | null; source_title: string | null; duration_s: number | null;
  chat: boolean | null; candidates: number; judged: number; clips: number; dropped: number;
  est_usd: number; cost_usd: number; job_ids: string[]; requested_at: string; started_at: string | null;
  finished_at: string | null; updated_at: string;
};

/** Grok judgment, about $0.0025 each (grok-4.20 non-reasoning). */
export const GROK_USD = 0.0025;
export const MAX_CLIPS = 20;

const UUID = "[0-9a-fA-F-]{36}";

export function linkKey(raw: string): string | null {
  let u = (raw ?? "").trim();
  if (!/^https:\/\//i.test(u) || u.length > 500) return null;
  u = u.replace(/^https:\/\//i, "");
  const first = u.split("/")[0];
  let host = first.split("?")[0].toLowerCase();
  if (host.includes("@") || host.includes(":")) return null;
  host = host.replace(/^(www|m|mobile)\./, "");
  const rest = u.slice(first.length);
  const qi = rest.indexOf("?");
  const q = qi >= 0 ? rest.slice(qi + 1) : "";
  const path = rest.split("?")[0].split("#")[0];
  let m: RegExpMatchArray | null;
  if (host === "twitch.tv") {
    if ((m = path.match(/^\/videos\/([0-9]+)\/?$/))) return `twitch:vod:${m[1]}`;
    if ((m = path.match(/^\/[A-Za-z0-9_]+\/clip\/([A-Za-z0-9_-]+)\/?$/))) return `twitch:clip:${m[1]}`;
  } else if (host === "clips.twitch.tv") {
    if ((m = path.match(/^\/([A-Za-z0-9_-]+)\/?$/))) return `twitch:clip:${m[1]}`;
  } else if (host === "kick.com") {
    if ((m = path.match(new RegExp(`^/(?:[A-Za-z0-9_-]+/)?videos?/(${UUID})/?$`)))) return `kick:vod:${m[1].toLowerCase()}`;
    if ((m = path.match(/^\/[A-Za-z0-9_-]+\/clips\/([A-Za-z0-9_]+)\/?$/))) return `kick:clip:${m[1]}`;
    if ((m = q.match(/(?:^|&)clip=([A-Za-z0-9_]+)/)) && /^\/[A-Za-z0-9_-]+\/?$/.test(path)) return `kick:clip:${m[1]}`;
  } else if (host === "youtube.com" || host === "youtu.be") {
    if (host === "youtu.be" && (m = path.match(/^\/([A-Za-z0-9_-]{11})\/?$/))) return `youtube:${m[1]}`;
    if ((m = path.match(/^\/(?:live|shorts)\/([A-Za-z0-9_-]{11})\/?$/))) return `youtube:${m[1]}`;
    if (path === "/watch" && (m = q.match(/(?:^|&)v=([A-Za-z0-9_-]{11})(?:&|$)/))) return `youtube:${m[1]}`;
  } else if (host === "x.com" || host === "twitter.com") {
    if ((m = path.match(/^\/[A-Za-z0-9_]+\/status\/([0-9]+)(?:\/video\/[0-9])?\/?$/))) return `x:${m[1]}`;
  }
  return null;
}

const NAMES: Record<string, string> = { twitch: "Twitch", kick: "Kick", youtube: "YouTube", x: "X" };

/** "Twitch VOD", "Kick clip", "YouTube video", "X post"; null = unsupported. */
export function linkLabel(key: string | null): string | null {
  if (!key) return null;
  const [p, kind] = key.split(":");
  if (p === "twitch" || p === "kick") return `${NAMES[p]} ${kind === "vod" ? "VOD" : "clip"}`;
  return p === "x" ? "X post" : `${NAMES[p]} video`;
}

/** "1:02:03", "62:03", "90" -> seconds. "" -> null. Anything else -> NaN. */
export function parseTime(v: string): number | null {
  const s = v.trim();
  if (!s) return null;
  if (!/^\d+(:\d{1,2}){0,2}$/.test(s)) return Number.NaN;
  return s.split(":").reduce((t, p) => t * 60 + Number(p), 0);
}

export function estimateUsd(maxClips: number): number {
  return Math.round(Math.max(1, Math.min(MAX_CLIPS, maxClips)) * GROK_USD * 10000) / 10000;
}

export const ACTIVE: LinkStatus[] = ["queued", "fetching", "detecting", "clipping"];

const STEP: Record<LinkStatus, string> = {
  queued: "Waiting for the PC", fetching: "Downloading", detecting: "Finding moments", clipping: "Judging and rendering",
  done: "Done", failed: "Failed", canceled: "Canceled",
};
export const statusLabel = (s: LinkStatus) => STEP[s];

/** Same link + same range, still live (not failed/canceled) = the request the database will hand back. */
export function findDuplicate(jobs: LinkJob[], key: string, start: number | null, end: number | null): LinkJob | null {
  return jobs.find((j) => j.url_key === key && (j.start_s ?? -1) === (start ?? -1) && (j.end_s ?? -1) === (end ?? -1)
    && j.status !== "failed" && j.status !== "canceled") ?? null;
}

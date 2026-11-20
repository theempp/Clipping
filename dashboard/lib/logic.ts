// Pure helpers shared by the UI and the tests. No React, no network.
import type { Clip, Heartbeat, Streamer, Submission } from "./types.ts";

/** Review queue order (D053): judge score 1-10 first, then confidence, then oldest first. */
export function rankQueue(clips: Clip[]): Clip[] {
  const n = (v: number | null | undefined) => (v == null ? -Infinity : v);
  return clips
    .filter((c) => c.state === "pending_review")
    .sort((a, b) =>
      n(b.score_10) - n(a.score_10) ||
      n(b.confidence) - n(a.confidence) ||
      a.created_at.localeCompare(b.created_at));
}

/** Heartbeat older than this means the PC is off, asleep or disconnected. */
export const ONLINE_WINDOW_S = 45;

export type PcState = "offline" | "waking" | "watching" | "idle" | "sleeping";

/** What the PC is really doing, from its own heartbeat. The switch alone never says "watching". */
export function pcState(hb: Heartbeat | null, wantAwake: boolean, now: number): PcState {
  if (!hb) return "offline";
  const age = (now - Date.parse(hb.seen_at)) / 1000;
  if (age > ONLINE_WINDOW_S) return "offline";
  const awake = hb.status.awake !== false;
  if (wantAwake && !awake) return "waking";
  if (!wantAwake && awake) return "sleeping";
  if (!awake) return "idle";
  return (hb.status.live?.length ?? 0) > 0 ? "watching" : "idle";
}

export function liveKeys(hb: Heartbeat | null, now: number): Set<string> {
  if (!hb || (now - Date.parse(hb.seen_at)) / 1000 > ONLINE_WINDOW_S) return new Set();
  return new Set(hb.status.live ?? []);
}

export function streamerKeys(s: Streamer): string[] {
  const k: string[] = [];
  if (s.twitch_login) k.push(`twitch:${s.twitch_login.toLowerCase()}`);
  if (s.kick_slug) k.push(`kick:${s.kick_slug.toLowerCase()}`);
  return k;
}

/** Seconds left on the 30-minute Content Rewards window (D025), from the deadline, not a stored count. */
export function secondsLeft(s: Pick<Submission, "deadline_at" | "submitted_at">, now: number): number {
  if (s.submitted_at) return 0;
  return Math.max(0, Math.floor((Date.parse(s.deadline_at) - now) / 1000));
}

export function openSubmissions(subs: Submission[], now: number): Submission[] {
  return subs
    .filter((s) => !s.submitted_at && secondsLeft(s, now) > 0)
    .sort((a, b) => a.deadline_at.localeCompare(b.deadline_at));
}

export function mmss(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function ago(iso: string, now: number): string {
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}

export function initials(name: string): string {
  return name.replace(/[^A-Za-z0-9 ]/g, "").slice(0, 2).toUpperCase() || "??";
}

/** Download filename: streamer_title_score.mp4, safe on Windows and phones. */
export function downloadName(c: Clip, streamer?: Streamer): string {
  const base = [streamer?.slug ?? c.channel_key.split(":")[1], c.title ?? c.job_id]
    .join("_").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
  return `${base || "clip"}.mp4`;
}

/** Revision box rule: plain English, trimmed, 3-500 chars. The worker parses it (P4). */
export function cleanNote(text: string): string | null {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length >= 3 && t.length <= 500 ? t : null;
}

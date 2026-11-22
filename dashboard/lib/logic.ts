// Pure helpers shared by the UI and the tests. No React, no network.
import type { Clip, Heartbeat, Streamer, Submission } from "./types.ts";

/** Review queue order (D053): judge score 1-10 first, then confidence, then oldest first. */
export function rankQueue(clips: Clip[]): Clip[] {
  const n = (v: number | null | undefined) => (v == null ? -Infinity : v);
  return clips
    .filter((c) => c.state === "pending_review" && !c.fixing)  // being re-edited with a learned rule (D078)
    .sort((a, b) =>
      n(b.score_10) - n(a.score_10) ||
      n(b.confidence) - n(a.confidence) ||
      a.created_at.localeCompare(b.created_at));
}

/** Heartbeat older than this means the PC is off, asleep or disconnected. */
export const ONLINE_WINDOW_S = 45;

export type PcState = "offline" | "waking" | "watching" | "idle" | "sleeping" | "asleep";

/** What the PC is really doing, from its own heartbeat. The switch alone never says "watching". */
export function pcState(hb: Heartbeat | null, wantAwake: boolean, now: number): PcState {
  if (!hb) return "offline";
  const age = (now - Date.parse(hb.seen_at)) / 1000;
  if (age > ONLINE_WINDOW_S) return "offline";
  const awake = hb.status.awake !== false;
  if (wantAwake && !awake) return "waking";
  if (!wantAwake && awake) return "sleeping";
  if (!awake) return "asleep";
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

export type DayStat = { key: string; label: string; day: number; made: number; approved: number; today: boolean };
export type WeekStats = { days: DayStat[]; streak: number; approvalRate: number | null; avgScore: number | null; approved7: number };

const OK_STATES = new Set(["approved", "scheduled", "published"]);

/** Last 7 local days of clip output, the approve streak (days in a row with an approved clip, ending today or
 *  yesterday), approval rate over reviewed clips and the average judge score. */
export function weekStats(clips: Clip[], now: number): WeekStats {
  const dayKey = (t: number) => { const d = new Date(t); return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`; };
  const made = new Map<string, number>();
  const ok = new Map<string, number>();
  for (const c of clips) {
    const k = dayKey(Date.parse(c.created_at));
    made.set(k, (made.get(k) ?? 0) + 1);
    if (OK_STATES.has(c.state)) {
      const r = dayKey(Date.parse(c.reviewed_at ?? c.created_at));
      ok.set(r, (ok.get(r) ?? 0) + 1);
    }
  }
  const start = new Date(now); start.setHours(12, 0, 0, 0);
  const days: DayStat[] = [];
  for (let i = 6; i >= 0; i--) {
    const t = start.getTime() - i * 86400_000;
    const d = new Date(t);
    const k = dayKey(t);
    days.push({ key: k, label: d.toLocaleDateString("en-US", { weekday: "short" }).slice(0, 2), day: d.getDate(),
      made: made.get(k) ?? 0, approved: ok.get(k) ?? 0, today: i === 0 });
  }
  let streak = 0;
  for (let i = ok.get(dayKey(start.getTime())) ? 0 : 1; ; i++) {
    if (!ok.get(dayKey(start.getTime() - i * 86400_000))) break;
    streak++;
  }
  const reviewed = clips.filter((c) => OK_STATES.has(c.state) || c.state === "rejected");
  const scored = clips.filter((c) => c.score_10 != null);
  return {
    days, streak,
    approvalRate: reviewed.length ? reviewed.filter((c) => OK_STATES.has(c.state)).length / reviewed.length : null,
    avgScore: scored.length ? scored.reduce((a, c) => a + (c.score_10 ?? 0), 0) / scored.length : null,
    approved7: days.reduce((a, d) => a + d.approved, 0),
  };
}

/** Revision box rule: plain English, trimmed, 3-500 chars. The worker parses it (P4). */
export function cleanNote(text: string): string | null {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length >= 3 && t.length <= 500 ? t : null;
}

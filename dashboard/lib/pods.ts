// Pods (D091-D109): pure helpers shared by the store and pages. No network here.
import type { Access, Clip, Pod, PodAccess, PodStatement, PostStat, Snapshot } from "./types.ts";

/** my_access() json -> Access. Anything unexpected reads as "no access". */
export function parseAccess(raw: unknown): Access {
  const r = (raw ?? {}) as { admin?: unknown; pods?: unknown };
  const pods = Array.isArray(r.pods) ? r.pods : [];
  return {
    admin: r.admin === true,
    pods: pods.filter((p): p is PodAccess => !!p && typeof (p as PodAccess).id === "string")
      .map((p) => ({ id: p.id, slug: p.slug, name: p.name, role: p.role === "owner" ? "owner" : "member" })),
  };
}

/** Can this user see anything at all? Admin, or a member of at least one pod. */
export function hasAccess(a: Access | null): boolean {
  return !!a && (a.admin || a.pods.length > 0);
}

/** Owner of a live (not ended) pod: mirrors public.is_pod_owner(). */
export function isPodOwner(podId: string | null | undefined, a: Access | null, pods: Pod[]): boolean {
  if (!podId || !a) return false;
  if (pods.find((p) => p.id === podId)?.status === "ended") return false;
  return a.pods.some((p) => p.id === podId && p.role === "owner");
}

/** Mirrors review_clip(): tagged clip -> only its pod owner; untagged -> only the admin (D102, D103). */
export function canReview(clip: Pick<Clip, "pod_id">, a: Access | null, pods: Pod[]): boolean {
  if (!a) return false;
  return clip.pod_id ? isPodOwner(clip.pod_id, a, pods) : a.admin;
}

/** The pod a page is scoped to: admin picks (null = All); members are pinned to their first pod. */
export function scopedPod(a: Access | null, picked: string | null): string | null {
  if (!a) return null;
  if (a.admin) return picked;
  return a.pods[0]?.id ?? null;
}

/** Snapshot narrowed to one pod (null = everything RLS returned). */
export function podSnapshot(s: Snapshot, pod: string | null): Snapshot {
  if (!pod) return s;
  const clips = s.clips.filter((c) => c.pod_id === pod);
  const clipIds = new Set(clips.map((c) => c.id));
  const streamers = s.streamers.filter((x) => x.pod_id === pod);
  const streamerIds = new Set(streamers.map((x) => x.id));
  return {
    ...s,
    clips,
    streamers,
    candidates: s.candidates.filter((c) => c.pod_id === pod),
    revisions: s.revisions.filter((r) => clipIds.has(r.clip_id)),
    publications: s.publications.filter((p) => clipIds.has(p.clip_id)),
    longform: s.longform.filter((v) => !v.clip_id || clipIds.has(v.clip_id)),
    brains: s.brains.filter((b) => streamerIds.has(b.streamer_id)),
    campaigns: s.campaigns.filter((c) => s.podCampaigns.some((pc) => pc.pod_id === pod && pc.campaign_id === c.id)),
    podCampaigns: s.podCampaigns.filter((pc) => pc.pod_id === pod),
    postStats: s.postStats.filter((r) => clipIds.has(r.clip_id)),
    statements: s.statements.filter((r) => r.pod_id === pod),
  };
}

/** Name for a pod id, for chips and table cells. */
export function podName(pods: Pod[], id: string | null | undefined): string {
  if (!id) return "untagged";
  return pods.find((p) => p.id === id)?.name ?? "unknown pod";
}

// --- stuck posts: same rule as worker clipworker/pods.py stuck_flags (Phase 1 stats) ---
export const STUCK_PLAYS = 20;
export type StuckPost = { clip_id: string; platform: PostStat["platform"]; plays: number; hours_since_post: number; read_at: string };

function reading(rows: PostStat[], lo: number, hi: number, target: number): PostStat | null {
  const near = rows.filter((r) => r.hours_since_post >= lo && r.hours_since_post < hi && r.plays != null);
  return near.reduce<PostStat | null>((a, r) => (!a || Math.abs(r.hours_since_post - target) < Math.abs(a.hours_since_post - target) ? r : a), null);
}

/** One flag per (clip, platform) with < 20 plays at ~1 h, or at ~2 h when there is no 1 h reading. Flags only. */
export function stuckPosts(rows: PostStat[]): StuckPost[] {
  const by = new Map<string, PostStat[]>();
  for (const r of rows) {
    const k = `${r.clip_id}|${r.platform}`;
    by.set(k, [...(by.get(k) ?? []), r]);
  }
  const out: StuckPost[] = [];
  for (const rs of by.values()) {
    const r = reading(rs, 0.5, 1.5, 1) ?? reading(rs, 1.5, 2.5, 2);
    if (r && (r.plays ?? 0) < STUCK_PLAYS) {
      out.push({ clip_id: r.clip_id, platform: r.platform, plays: r.plays ?? 0, hours_since_post: r.hours_since_post, read_at: r.read_at });
    }
  }
  return out;
}

// --- money: display formatting only; every amount comes from the database (D092) ---
/** 123456 -> "1,234.56" (no sign, no symbol). */
export function cents(n: number): string {
  return (Math.abs(n) / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
/** -123456 -> "-$1,234.56". */
export function usd(n: number): string {
  return `${n < 0 ? "-" : ""}$${cents(n)}`;
}
/** Adds database amounts for a totals tile (no rate math here). */
export function total<T>(rows: T[], pick: (r: T) => number): number {
  return rows.reduce((a, r) => a + pick(r), 0);
}
/** "2026-11-01" for the month containing `now` (UTC, like date_trunc in pod_statements). */
export function monthOf(now: number): string {
  const d = new Date(now);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-01`;
}
/** pod_statements rows for one month. */
export function statementsFor(rows: PodStatement[], month: string): PodStatement[] {
  return rows.filter((r) => r.month.slice(0, 10) === month);
}

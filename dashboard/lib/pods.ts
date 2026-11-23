// Pods (D091-D109): pure helpers shared by the store and pages. No network here.
import type { Access, Clip, Pod, PodAccess, Snapshot } from "./types.ts";

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
  };
}

/** Name for a pod id, for chips and table cells. */
export function podName(pods: Pod[], id: string | null | undefined): string {
  if (!id) return "untagged";
  return pods.find((p) => p.id === id)?.name ?? "unknown pod";
}

// Halo Pro review page (D116): every number on the page comes from here, derived from real rows.
// Missing data returns null so the UI shows an empty state instead of a made-up number.
import type { Candidate, Clip, Destination, EditPlan, Publication, Snapshot, SpendDay } from "./types.ts";

export type Platform = "youtube" | "tiktok" | "x";
export const PLATFORMS: Platform[] = ["youtube", "tiktok", "x"];
export const PLATFORM_LABEL: Record<Platform, string> = { youtube: "YouTube", tiktok: "TikTok", x: "X" };

/** Per-streamer colour (design: Lacy coral, Jynxzi halo, xQc violet, Stable Ronaldo mint). Others cycle the tokens. */
const FIXED: Record<string, string> = { lacy: "#ff7a59", jynxzi: "var(--halo)", xqc: "var(--vio)", stableronaldo: "var(--ok)" };
const CYCLE = ["var(--warn)", "var(--tt)", "var(--spike)", "var(--halo2)", "var(--kick)", "var(--tw)"];
export function streamerColor(slug: string | null | undefined): string {
  if (!slug) return "var(--halo)";
  if (slug in FIXED) return FIXED[slug];
  let h = 0;
  for (const ch of slug) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return CYCLE[h % CYCLE.length];
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);

/** 0-100 Grok score (D089 judge.score), else the 1-10 queue score x10. */
export function clipScore(c: Clip): number | null {
  const s = num(c.judge?.score);
  if (s != null) return Math.round(Math.max(0, Math.min(100, s)));
  return c.score_10 != null ? c.score_10 * 10 : null;
}

export type SubScores = { hook: number | null; payoff: number | null; trend: number | null; views: number | null };
/** Hook / Payoff from the judge's 0-10 parts (x10). Trend and est. views are not produced by the judge yet: null. */
export function subScores(c: Clip): SubScores {
  const parts = (c.judge?.parts ?? null) as Record<string, unknown> | null;
  const judged = (parts?.judged ?? null) as Record<string, unknown> | null;
  const part = (k: string) => { const v = num(judged?.[k]); return v == null ? null : Math.round(v * 10); };
  return { hook: part("hook"), payoff: part("payoff"), trend: num(c.judge?.trend), views: num(c.judge?.est_views) };
}

export function judgeWhy(c: Clip): string | null {
  return str(c.judge?.why) ?? str(c.judge?.reason);
}

/** The words burned into the clip as the headline box (judge hook, else title). */
export function headlineOf(c: Clip): string {
  return (str(c.hook) ?? str(c.title) ?? "").toUpperCase();
}

export const NEW_MS = 15 * 60_000;
export const isNew = (c: Clip, now: number) => now - Date.parse(c.created_at) < NEW_MS;

export function queueSummary(queue: Clip[], now: number): { waiting: number; avg: number | null; fresh: number } {
  const scores = queue.map(clipScore).filter((x): x is number => x != null);
  return {
    waiting: queue.length,
    avg: scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null,
    fresh: queue.filter((c) => isNew(c, now)).length,
  };
}

/** Chat heat across one clip, from detector scores logged on its channel around the moment. Null = no readings. */
export function clipHeat(cands: Candidate[], clip: Clip, bars = 18): { h: number[]; spike: boolean[]; ratio: number } | null {
  // The minutes around the moment: the detector logs scored windows, not every chat line.
  const t = Date.parse(clip.moment_at);
  const lo = t - 8 * 60_000, hi = t + 2 * 60_000;
  const pts = cands.filter((c) => c.channel_key === clip.channel_key).map((c) => ({ at: Date.parse(c.moment_at), s: c.score }))
    .filter((p) => p.at >= lo && p.at <= hi);
  if (pts.length < 3) return null;
  const h = new Array(bars).fill(0) as number[];
  for (const p of pts) {
    const i = Math.min(bars - 1, Math.floor(((p.at - lo) / (hi - lo)) * bars));
    h[i] = Math.max(h[i], p.s);
  }
  const max = Math.max(...h);
  const sorted = [...pts.map((p) => p.s)].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)] || 1;
  return { h: h.map((v) => (max > 0 ? v / max : 0)), spike: h.map((v) => v >= max * 0.6 && v > median), ratio: +(max / median).toFixed(1) };
}

/** Today's funnel. Found = moments the detector logged; Judged = minus duplicates and errors; Passed = clips that
 *  reached review; Okayed = clips approved today; Posted = posts that went out today. */
export function pipelineToday(snap: Snapshot, now: number) {
  const d = new Date(now); d.setHours(0, 0, 0, 0);
  const start = d.getTime();
  const today = (iso: string | null | undefined) => !!iso && Date.parse(iso) >= start && Date.parse(iso) <= now;
  const found = snap.candidates.filter((c) => today(c.moment_at));
  const judged = found.filter((c) => c.outcome !== "duplicate" && c.outcome !== "error");
  const passed = snap.clips.filter((c) => today(c.created_at));
  const okayed = snap.clips.filter((c) => today(c.reviewed_at) && ["approved", "scheduled", "published"].includes(c.state));
  const posted = snap.publications.filter((p) => p.status === "posted" && today(p.posted_at));
  return { found: found.length, judged: judged.length, passed: passed.length, okayed: okayed.length, posted: posted.length };
}

/** AI spend this month: total, per kind, today, 14-day daily series and a straight-line month projection. */
export function spendView(snap: Snapshot, days: SpendDay[], now: number) {
  const total = snap.spend.reduce((a, r) => a + r.usd, 0);
  const kinds = [...snap.spend].filter((r) => r.usd > 0).sort((a, b) => b.usd - a.usd);
  const d = new Date(now);
  const dim = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
  const day = d.getDate() - 1 + (d.getHours() * 60 + d.getMinutes()) / 1440;
  const pace = day >= 1 && total > 0 ? (total / day) * dim : null;
  const key = (t: number) => new Date(t).toISOString().slice(0, 10);
  const byDay = new Map(days.map((r) => [r.day, r.usd]));
  const series = Array.from({ length: 14 }, (_, i) => byDay.get(key(now - (13 - i) * 86400_000)) ?? 0);
  const today = days.length ? byDay.get(key(now)) ?? 0 : null;
  return { total, kinds, pace, series: days.length ? series : null, today };
}

export const SPEND_LABEL: Record<string, string> = { grok: "Grok judge", x_post: "X posts", storage: "Storage", transcribe: "Captions", other: "Other" };

/** Views on Zo's channels over 7 days from stat_snapshots: latest total, gained, growth vs the week before. */
export function channels7d(snap: Snapshot, now: number): Record<Platform, { views: number | null; gained: number | null; growth: number | null }> {
  const out = {} as Record<Platform, { views: number | null; gained: number | null; growth: number | null }>;
  for (const p of PLATFORMS) {
    const pts = snap.history.filter((h) => h.key === `${p}:own` && h.metric === "views").sort((a, b) => a.at.localeCompare(b.at));
    const live = snap.live.find((r) => r.kind === "own" && r.platform === p)?.views ?? null;
    const latest = live ?? (pts.length ? pts[pts.length - 1].value : null);
    const at = (msAgo: number) => {
      const t = now - msAgo;
      const before = pts.filter((x) => Date.parse(x.at) <= t);
      return before.length ? before[before.length - 1].value : null;
    };
    const w1 = at(7 * 86400_000), w2 = at(14 * 86400_000);
    const gained = latest != null && w1 != null ? latest - w1 : null;
    const prev = w1 != null && w2 != null ? w1 - w2 : null;
    out[p] = { views: latest, gained, growth: gained != null && prev != null && prev > 0 ? Math.round(((gained - prev) / prev) * 100) : null };
  }
  return out;
}

/** Platforms that have an active posting account. The worker posts to these only (and only what Zo picks). */
export function postablePlatforms(dests: Destination[]): Platform[] {
  return PLATFORMS.filter((p) => dests.some((d) => d.active && d.platform === p));
}

/** Posts in the next 24 h. The publisher posts right after approval (D088 ramp gates it), so only posts already
 *  queued but not yet out count: approved/scheduled clips without a posted publication. */
export function upcomingPosts(clips: Clip[], pubs: Publication[]): Clip[] {
  const posted = new Set(pubs.filter((p) => p.status === "posted").map((p) => p.clip_id));
  return clips.filter((c) => (c.state === "approved" || c.state === "scheduled") && c.category !== "longform" && !posted.has(c.id));
}

export function compactNum(n: number | null | undefined): string {
  if (n == null) return "—";
  const a = Math.abs(n);
  if (a >= 1e6) return `${(n / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(/\.0$/, "")}M`;
  if (a >= 1e3) return `${(n / 1e3).toFixed(a >= 1e4 ? 1 : 1).replace(/\.0$/, "")}K`;
  return String(Math.round(n));
}

export function clipLen(s: number | null): string {
  if (s == null) return "—";
  const t = Math.round(s);
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

export function agoShort(iso: string, now: number): string {
  const m = Math.max(0, Math.floor((now - Date.parse(iso)) / 60_000));
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h} h ago` : `${Math.floor(h / 24)} d ago`;
}

/** The editor's starting plan for a clip: whole clip, centred crop, its headline and emphasis words. No zoom (D112). */
export function basePlan(c: Clip): EditPlan {
  const total = Math.max(1, c.duration_s ?? 30);
  const words = (c.manifest?.emphasis_words ?? c.judge?.emphasis_words) as unknown;
  return {
    trim_in: 0, trim_out: total, crop_x: 0.5, zoom: 1, remove_tools: [], headline: headlineOf(c),
    caption_style: "words", splits: [], drop: [],
    emphasis_words: Array.isArray(words) ? words.filter((w): w is string => typeof w === "string").map((w) => w.toLowerCase()).slice(0, 12) : [],
  };
}

/** Seconds of the judge's hook window start ("0:02-0:05" -> 2), or null. */
export function hookStart(c: Clip): number | null {
  const m = typeof c.judge?.hook_window === "string" ? c.judge.hook_window.match(/^(\d+):(\d{2})/) : null;
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

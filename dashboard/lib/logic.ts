// Pure helpers shared by the UI and the tests. No React, no network.
import type { Clip, EditPlan, Heartbeat, Streamer, Submission } from "./types.ts";

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

/** Editor plan -> one readable revision note the PC and Zo can both read. Lists only what Zo changed
 *  against `base` (the same rule as `editPayload`), so an untouched zoom or headline is not reported. */
export function editNote(p: EditPlan, base: EditPlan): string {
  const parts: string[] = [];
  const d = (s: number) => `${s.toFixed(1)}s`;
  const e = editPayload(p, base);
  if ("trim_in" in e) parts.push(`trim ${d(p.trim_in)}-${d(p.trim_out)}`);
  if ("cuts" in e) parts.push(droppedCuts(p).length ? `drop ${droppedCuts(p).map(([a, b]) => `${d(a)}-${d(b)}`).join(", ")}` : "keep every piece");
  if ("crop_x" in e) parts.push(`crop centre ${Math.round(p.crop_x * 100)}%`);
  if ("zoom" in e) parts.push(`zoom ${Math.round(p.zoom * 100)}%`);
  if ("remove_tools" in e) parts.push(`remove ${p.remove_tools!.join(", ")}`);
  if ("flashback" in e) parts.push(p.flashback === "approve" ? "flashback approved" : "flashback dropped");
  if ("headline" in e) parts.push(`headline "${p.headline.trim().slice(0, 80)}"`);
  if ("caption_style" in e) parts.push(p.caption_style === "words" ? "captions 2-3 words" : "captions full line");
  if ("emphasis_words" in e) parts.push(p.emphasis_words.length ? `emphasis ${p.emphasis_words.join(" ")}` : "no emphasis");
  return parts.length ? `Editor: ${parts.join(" · ")}` : "Editor: no changes yet";
}

/** Caption-words box -> emphasis list (max 12, no punctuation, lower case like the worker). */
export function emphasisWords(text: string): string[] {
  return text.split(/\s+/).map((w) => w.replace(/^[.,!?"']+|[.,!?"']+$/g, "").toLowerCase()).filter(Boolean).slice(0, 12);
}

/** The worker's `edit` payload (D098): only what Zo changed against `base`, so an untouched
 *  slider never overrides the PC's own choice. Trim is clip-relative seconds. */
export function editPayload(p: EditPlan, base: EditPlan): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (Math.abs(p.trim_in - base.trim_in) > 0.05 || Math.abs(p.trim_out - base.trim_out) > 0.05) {
    out.trim_in = p.trim_in; out.trim_out = p.trim_out;
  }
  if (Math.abs(p.crop_x - base.crop_x) > 0.01) out.crop_x = p.crop_x;
  if (Math.abs(p.zoom - base.zoom) > 0.005) out.zoom = p.zoom;
  if (p.caption_style !== base.caption_style) out.caption_style = p.caption_style;
  if (p.emphasis_words.join(" ") !== base.emphasis_words.join(" ")) out.emphasis_words = p.emphasis_words;
  if (p.headline.trim() && p.headline.trim() !== base.headline.trim()) out.headline = p.headline.trim();
  const cuts = droppedCuts(p);
  if (cuts.length || droppedCuts(base).length) out.cuts = cuts;
  if ((p.remove_tools ?? []).length) out.remove_tools = p.remove_tools;
  if (p.flashback) out.flashback = p.flashback;
  return out;
}

/** Tools every clip has (hard cut, headline box); they are not offered as toggles. */
export const DEFAULT_TOOLS = ["hard_cut", "headline_box"];
export const TOOL_LABEL: Record<string, string> = {
  black_spacer: "Black spacer", slowmo_vignette: "Slow-mo + vignette", music_cue: "Music cue",
  sfx_whoosh: "Whoosh", sfx_hit: "Hit", sfx_glitch: "Glitch",
  swap_full_face: "Full-face swap", swap_full_game: "Full-game swap", gta_stinger: "GTA stinger",
};
export type FlashbackProposal = { reason: string; source_moment: string };
export type ClipRecipe = {
  tools: string[]; captionStyle: string | null; flashbackOn: boolean; proposal: FlashbackProposal | null;
};

/** The edit recipe the PC stored in the render manifest (D114), or null for clips rendered before it. */
export function clipRecipe(c: Clip): ClipRecipe | null {
  const m = c.manifest as Record<string, unknown> | undefined;
  const r = m?.recipe as { tools?: unknown; caption_style?: unknown; flashback?: { approved?: boolean } | null } | undefined;
  if (!r || !Array.isArray(r.tools)) return null;
  const pr = m?.flashback_proposal as Partial<FlashbackProposal> | null | undefined;
  return {
    tools: r.tools.filter((t): t is string => typeof t === "string" && !DEFAULT_TOOLS.includes(t)),
    captionStyle: typeof r.caption_style === "string" ? r.caption_style : null,
    flashbackOn: !!r.flashback?.approved,
    proposal: pr && typeof pr.reason === "string" ? { reason: pr.reason, source_moment: String(pr.source_moment ?? "") } : null,
  };
}

/** Pieces of the trimmed clip between splits: [start, end] in clip seconds. */
export function pieces(p: EditPlan): [number, number][] {
  const edges = [p.trim_in, ...p.splits.filter((s) => s > p.trim_in && s < p.trim_out), p.trim_out];
  return edges.slice(0, -1).map((a, i) => [a, edges[i + 1]]);
}

/** Dropped pieces as cut ranges. Never all of them: at least one piece always stays. */
export function droppedCuts(p: EditPlan): [number, number][] {
  const all = pieces(p);
  const drop = new Set(p.drop ?? []);
  const cut = all.filter(([a]) => drop.has(a));
  return cut.length < all.length ? cut : [];
}

/** Clamp a trim so it stays inside the clip and at least `min` seconds long. */
export function clampTrim(a: number, b: number, total: number, min = 1): [number, number] {
  let x = Math.max(0, Math.min(a, total - min));
  let y = Math.min(total, Math.max(b, x + min));
  if (y - x < min) x = Math.max(0, y - min);
  return [+x.toFixed(2), +y.toFixed(2)];
}

/** Short number: 1234 -> 1.2K, 2_910_000 -> 2.91M. */
export function compact(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const a = Math.abs(n);
  if (a >= 1e6) return `${(n / 1e6).toFixed(a >= 1e7 ? 1 : 2).replace(/\.?0+$/, "")}M`;
  if (a >= 1e3) return `${(n / 1e3).toFixed(a >= 1e4 ? 0 : 1).replace(/\.0$/, "")}K`;
  return String(Math.round(n));
}

/** Revision box rule: plain English, trimmed, 3-500 chars. The worker parses it (P4). */
export function cleanNote(text: string): string | null {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length >= 3 && t.length <= 500 ? t : null;
}

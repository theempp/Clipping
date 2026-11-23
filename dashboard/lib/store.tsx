"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { demoAccess, demoEntry, demoEvent, demoSnapshot, demoStatements } from "./demo";
import { IS_DEMO, PODS_ON } from "./env";
import { canReview as podCanReview, hasAccess, isPodOwner, parseAccess, podSnapshot, scopedPod } from "./pods";
import { browserClient } from "./supabase/client";
import type { Access, Clip, EditPlan, LedgerEntry, LongformVideo, ReviewAction, Snapshot, TiktokStats } from "./types";
import { editNote, editPayload } from "./logic";
import type { LiveStat } from "./types";

/** Demo only: nudge live viewer counts a little, like a real stream. */
function driftLive(rows: LiveStat[]): LiveStat[] {
  const at = new Date().toISOString();
  return rows.map((r) => (r.is_live && r.viewers != null
    ? { ...r, viewers: Math.max(50, Math.round(r.viewers * (1 + (Math.random() - 0.48) * 0.02))), updated_at: at } : r));
}

export const UNDO_MS = 4000;

type Pending = { clip: Clip; action: ReviewAction; note?: string; applyAll?: boolean; platforms?: string[]; until: number };
/** key lets a page hide the row while the action waits. */
export type Deferred = { key: string; verb: string; label: string; until: number; run: () => Promise<void> };

type Store = {
  demo: boolean;
  ready: boolean;
  error: string | null;
  /** Data for the pod in scope (everything when pods are off or the admin picked All). */
  snap: Snapshot;
  /** Pods (NEXT_PUBLIC_CLIPP_PODS=1). podsOn false = single-owner dashboard, access/pod unused. */
  podsOn: boolean;
  access: Access | null;
  /** Pod in scope: admin's pick (null = All) or the member's pinned pod. */
  pod: string | null;
  setPod: (id: string | null) => void;
  /** Mirrors review_clip(): only the clip's pod owner, or the admin for untagged clips. The DB enforces it too. */
  canReview: (clip: Clip) => boolean;
  pending: Pending | null;
  /** A non-clip action waiting UNDO_MS (campaign decline, ledger clear/approve); UndoToast shows it. */
  later: Deferred | null;
  /** Pod owner joins / declines a campaign for its pod (pod_campaign_set, D106). Decline waits for undo. */
  setPodCampaign: (pod: string, campaign: string, status: "joined" | "declined", label: string) => Promise<string | null>;
  /** Ledger, admin only (D092: records money, never moves it). Each returns an error message or null. */
  ledgerAdd: (pod: string, campaign: string | null, sourceRef: string, grossCents: number, note: string | null) => Promise<string | null>;
  /** cleared / approved wait UNDO_MS (undoable); paid needs the transfer ref and is final. */
  ledgerStep: (entry: LedgerEntry, to: "cleared" | "approved" | "paid", ref?: string) => Promise<string | null>;
  ledgerReverse: (entry: LedgerEntry, reason: string) => Promise<string | null>;
  /** Approve / deny wait UNDO_MS before they reach the database, so a stray key press can be undone. */
  /** applyAll (revise only): the note's style asks also become standing rules for every clip (D078). */
  act: (clip: Clip, action: ReviewAction, note?: string, applyAll?: boolean) => void;
  /** Post = approve with the platforms Zo picked, after the confirm dialog (D116). Waits UNDO_MS like approve. */
  post: (clip: Clip, platforms: string[]) => void;
  /** CLIP THAT: ask the PC for the last `seconds` of a live streamer (request_clip RPC). Error message or null. */
  requestClip: (slug: string, seconds: number) => Promise<string | null>;
  undo: () => void;
  setRuleActive: (id: string, on: boolean) => Promise<void>;
  markSubmitted: (id: string) => Promise<void>;
  mediaUrl: (path: string | null, download?: string) => Promise<string | null>;
  /** TikTok is uploaded by hand (D074); these record the post, its stats and any eligibility notice. */
  markTiktokPosted: (id: string, url: string) => Promise<boolean>;
  addTiktokStats: (id: string, stats: TiktokStats) => Promise<boolean>;
  setNotice: (id: string, notice: LongformVideo["notice"]) => Promise<void>;
  /** Editor: trim/crop/headline/caption plan goes back to the PC as a revision (clip leaves the queue until re-rendered). */
  sendEdit: (clip: Clip, plan: EditPlan, base: EditPlan) => Promise<boolean>;
  setBrain: (streamerId: string, weights: Record<string, number>, words?: string[]) => Promise<void>;
  setTiktokChannel: (followers: number | null, views: number | null, posts: number | null) => Promise<boolean>;
  /** Ask the server to poll the platforms now (throttled server-side). */
  pollLive: (force?: boolean) => Promise<void>;
  signOut: () => Promise<void>;
};

const EMPTY: Snapshot = {
  streamers: [], clips: [], submissions: [], heartbeat: null, destinations: [], spendDays: [],
  candidates: [], spend: [], revisions: [], rules: [],
  longform: [], results: [], live: [], history: [], publications: [], campaigns: [], brains: [], pods: [],
  podCampaigns: [], postStats: [], statements: [], ledger: [], ledgerEvents: [],
};

const Ctx = createContext<Store | null>(null);

const POD_KEY = "clipp.pod";
function readPod(): string | null {
  try { return localStorage.getItem(POD_KEY) || null; } catch { return null; }
}

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore outside DataProvider");
  return s;
}

/** Re-render every `ms` with the current time (countdowns, "seen 4s ago"). */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

async function loadLive(): Promise<Snapshot> {
  const sb = browserClient();
  // Candidates: the last 6 h, or since midnight when that is longer (today's pipeline funnel).
  const midnight = new Date(); midnight.setHours(0, 0, 0, 0);
  const since6h = new Date(Math.min(Date.now() - 6 * 3600_000, midnight.getTime())).toISOString();
  const since24h = new Date(Date.now() - 24 * 3600_000).toISOString();
  const month = new Date(); month.setUTCDate(1); month.setUTCHours(0, 0, 0, 0);
  const [st, cl, su, hb, ca, sp, rv, ru, lf, lr] = await Promise.all([
    PODS_ON ? sb.from("streamers").select("id,slug,display_name,twitch_login,kick_slug,avatar_url,pod_id").order("display_name")
      : sb.from("streamers").select("id,slug,display_name,twitch_login,kick_slug,avatar_url").order("display_name"),
    sb.from("clips").select("*").order("created_at", { ascending: false }).limit(300),
    sb.from("submissions_live").select("*").gte("created_at", since24h).order("deadline_at"),
    sb.from("worker_heartbeat").select("*").order("seen_at", { ascending: false }).limit(1),
    (PODS_ON ? sb.from("candidate_log").select("channel_key,moment_at,score,outcome,pod_id")
      : sb.from("candidate_log").select("channel_key,moment_at,score,outcome")).gte("moment_at", since6h)
      .order("moment_at").limit(5000),
    sb.from("spend_month").select("kind,usd").gte("month", month.toISOString()),
    sb.from("revisions").select("id,clip_id,kind,note,created_at,resolved_at")
      .order("created_at", { ascending: false }).limit(200),
    sb.from("edit_rules").select("id,key,value,label,note,clip_id,active,fixed_count,created_at")
      .order("created_at", { ascending: false }).limit(50),
    sb.from("longform_videos").select("id,clip_id,channel,format,pacing,caption_style,voice,layout,runtime_s,coverage,tiktok_url,posted_at,notice")
      .order("created_at", { ascending: false }).limit(200),
    sb.from("longform_results").select("*"),
  ]);
  const err = [st, cl, su, hb, ca, sp, rv, ru, lf, lr].find((r) => r.error)?.error;
  if (err) throw new Error(err.message);
  // Newer tables (live numbers, brain, schedule) are optional: until their migration is applied they read as empty.
  const since30d = new Date(Date.now() - 30 * 86400_000).toISOString();
  const since14d = new Date(Date.now() - 14 * 86400_000).toISOString();
  const [li, hi, pu, de, cm, br, sd] = await Promise.all([
    sb.from("live_stats").select("*"),
    sb.from("stat_snapshots").select("key,metric,value,at").gte("at", since30d).order("at").limit(5000),
    sb.from("publications").select("id,clip_id,destination_id,status,url,posted_at,created_at").order("created_at", { ascending: false }).limit(200),
    sb.from("destinations").select("id,platform,label,active,streamer_id"),
    sb.from("campaigns").select("id,title,status,source_url,streamer_slugs,platforms,cpm_usd,cap_usd,deadline,score,recommendation,created_at")
      .order("created_at", { ascending: false }).limit(100),
    sb.from("streamer_brain").select("streamer_id,weights,words,updated_at"),
    sb.from("spend").select("amount_usd,at").gte("at", since14d).order("at").limit(5000),
  ]);
  // Admin reads every pod; a member reads only its own (RLS pod_read).
  const pods = PODS_ON ? await sb.from("pods").select("id,slug,name,status").order("slug") : null;
  if (pods?.error) throw new Error(pods.error.message);
  const none = { data: [], error: null };
  const [pc, ps, pst] = PODS_ON ? await Promise.all([
    sb.from("pod_campaigns").select("pod_id,campaign_id,status,scout,decided_at,created_at"),
    // post_stats is admin-only under RLS today; members read it as empty.
    sb.from("post_stats").select("clip_id,platform,read_at,hours_since_post,plays").lte("hours_since_post", 2.5)
      .gte("read_at", since30d).limit(3000),
    sb.from("pod_statements").select("*").order("month", { ascending: false }).limit(240),
  ]) : [none, none, none];
  // Ledger reads are RLS-scoped (admin: all; pod: its own, D107). Required once pods are on.
  const [le, lev] = PODS_ON ? await Promise.all([
    sb.from("ledger_entries").select("id,pod_id,source,source_ref,campaign_id,gross_cents,agency_rate,agency_cut_cents,pod_net_cents,status,note,reverses_id,cleared_at,approved_at,paid_at,paid_ref,created_at")
      .order("created_at", { ascending: false }).limit(500),
    sb.from("ledger_events").select("id,entry_id,pod_id,op,from_status,to_status,actor,actor_id,row_after,at")
      .order("at", { ascending: false }).limit(500),
  ]) : [none, none];
  if (le.error) throw new Error(le.error.message);
  if (lev.error) throw new Error(lev.error.message);
  const num = (v: unknown) => Number(v ?? 0);
  const ok = <T,>(r: { data: T[] | null; error: unknown }): T[] => (r.error ? [] : r.data ?? []);
  const dest = new Map(ok(de).map((d) => [d.id, d]));
  const days = new Map<string, number>();
  for (const r of ok(sd)) { const k = String(r.at).slice(0, 10); days.set(k, (days.get(k) ?? 0) + Number(r.amount_usd ?? 0)); }
  const opt = {
    destinations: ok(de).map((d) => ({ id: d.id, platform: d.platform, label: d.label, active: d.active !== false, streamer_id: d.streamer_id ?? null })),
    spendDays: [...days].map(([day, usd]) => ({ day, usd })),
    live: ok(li),
    history: ok(hi).map((p) => ({ ...p, value: Number(p.value) })),
    publications: ok(pu).map((p) => ({ ...p, platform: dest.get(p.destination_id)?.platform ?? null, label: dest.get(p.destination_id)?.label ?? null })),
    campaigns: ok(cm).map((c) => ({ ...c, cpm_usd: c.cpm_usd == null ? null : Number(c.cpm_usd), cap_usd: c.cap_usd == null ? null : Number(c.cap_usd), score: c.score == null ? null : Number(c.score) })),
    brains: ok(br),
    pods: pods?.data ?? [],
    podCampaigns: ok(pc),
    postStats: ok(ps).map((r) => ({ ...r, hours_since_post: Number(r.hours_since_post) })),
    // bigint sums arrive as numbers or strings; Number() only changes the type, never the amount.
    statements: ok(pst).map((r) => ({
      pod_id: r.pod_id, month: String(r.month), entries: num(r.entries), gross_cents: num(r.gross_cents),
      agency_cut_cents: num(r.agency_cut_cents), pod_net_cents: num(r.pod_net_cents), pending_net_cents: num(r.pending_net_cents),
      owed_net_cents: num(r.owed_net_cents), paid_net_cents: num(r.paid_net_cents),
    })),
    ledger: (le.data ?? []).map((r) => ({
      ...r, gross_cents: num(r.gross_cents), agency_rate: num(r.agency_rate), agency_cut_cents: num(r.agency_cut_cents), pod_net_cents: num(r.pod_net_cents),
    })),
    ledgerEvents: lev.data ?? [],
  };
  return {
    ...opt,
    streamers: st.data ?? [],
    clips: cl.data ?? [],
    submissions: su.data ?? [],
    heartbeat: hb.data?.[0] ?? null,
    candidates: ca.data ?? [],
    spend: (sp.data ?? []).map((r) => ({ kind: r.kind, usd: Number(r.usd) })),
    revisions: rv.data ?? [],
    rules: ru.data ?? [],
    longform: lf.data ?? [],
    results: lr.data ?? [],
  };
}

export function DataProvider({ children }: { children: ReactNode }) {
  // Data loads after mount only: everything shown is time-relative, so server HTML stays a neutral shell.
  const [snap, setSnap] = useState<Snapshot>(EMPTY);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [access, setAccess] = useState<Access | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [later, setLater] = useState<Deferred | null>(null);
  const laterRef = useRef<Deferred | null>(null);
  const laterTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const accessRef = useRef<Access | null>(null);
  accessRef.current = access;
  const pendingRef = useRef<Pending | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const urls = useRef(new Map<string, { url: string; exp: number }>());
  const snapRef = useRef(snap);
  snapRef.current = snap;

  const refresh = useCallback(async () => {
    if (IS_DEMO) return;
    try {
      const sb = browserClient();
      if (PODS_ON) {
        const { data: raw, error: e } = await sb.rpc("my_access");
        if (e) throw new Error(e.message);
        const a = parseAccess(raw);
        setAccess(a);
        if (!hasAccess(a)) { setError("not-owner"); setReady(true); return; }
      } else {
        const { data: owner, error: e } = await sb.rpc("is_owner");
        if (e) throw new Error(e.message);
        if (!owner) { setError("not-owner"); setReady(true); return; }
      }
      setSnap(await loadLive());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReady(true);
    }
  }, []);

  // Initial load, realtime refresh (debounced), and a 30 s safety poll.
  useEffect(() => {
    if (PODS_ON) setPicked(readPod());
    if (IS_DEMO) {
      if (PODS_ON) setAccess(demoAccess(window.location.search));
      setSnap(demoSnapshot());
      setReady(true);
      // The fake PC keeps reporting in, so demo never drifts to "offline".
      const beat = setInterval(() => setSnap((s) => (s.heartbeat
        ? { ...s, heartbeat: { ...s.heartbeat, seen_at: new Date().toISOString() } } : s)), 15_000);
      // Demo stand-in for the Realtime push: live viewer counts drift every few seconds.
      const tick = setInterval(() => setSnap((s) => ({ ...s, live: driftLive(s.live) })), 4_000);
      return () => { clearInterval(beat); clearInterval(tick); };
    }
    void refresh();
    const sb = browserClient();
    let t: ReturnType<typeof setTimeout> | null = null;
    const bump = () => { if (t) clearTimeout(t); t = setTimeout(() => void refresh(), 400); };
    const ch = sb.channel("clipp-dashboard");
    for (const table of ["clips", "worker_heartbeat", "submissions", "edit_rules", "longform_videos", "streamer_brain", "publications"]) {
      ch.on("postgres_changes", { event: "*", schema: "public", table }, bump);
    }
    // Live numbers are patched in place: no full reload for a viewer count.
    ch.on("postgres_changes", { event: "*", schema: "public", table: "live_stats" }, (m) => {
      const row = m.new as LiveStat | undefined;
      if (!row?.key) return;
      setSnap((s) => ({ ...s, live: [...s.live.filter((x) => x.key !== row.key), row] }));
    });
    ch.subscribe();
    const poll = setInterval(() => void refresh(), 30_000);
    // While the dashboard is open and visible, ask the server for fresh platform numbers every minute.
    const kick = () => { if (document.visibilityState === "visible") void fetch("/api/live", { method: "POST" }).catch(() => {}); };
    kick();
    const live = setInterval(kick, 60_000);
    return () => { clearInterval(poll); clearInterval(live); if (t) clearTimeout(t); void sb.removeChannel(ch); };
  }, [refresh]);

  const commit = useCallback(async (p: Pending) => {
    if (IS_DEMO) {
      const to = p.action === "approve" ? "approved" : p.action === "revise" ? "revise" : "rejected";
      // Demo stand-in for the publisher: a confirmed post goes out a few seconds later.
      if (p.action === "approve") {
        setTimeout(() => setSnap((s) => ({
          ...s,
          clips: s.clips.map((c) => (c.id === p.clip.id && c.state === "approved" ? { ...c, state: "published" } : c)),
          publications: [...(p.platforms ?? []).map((pl, i) => ({ id: `demo-pub-${Date.now()}-${i}`, clip_id: p.clip.id, status: "posted" as const,
            url: null, posted_at: new Date().toISOString(), created_at: new Date().toISOString(), platform: pl, label: "demo" })), ...s.publications],
        })), 3000);
      }
      setSnap((s) => ({
        ...s,
        clips: s.clips.map((c) => (c.id === p.clip.id ? { ...c, state: to, reviewed_at: new Date().toISOString(),
          post_platforms: p.platforms ?? c.post_platforms ?? null } : c)),
        revisions: p.action === "revise" && p.note
          ? [{ id: `demo-rev-${Date.now()}`, clip_id: p.clip.id, kind: "other", note: p.note,
               created_at: new Date().toISOString(), resolved_at: null }, ...s.revisions]
          : s.revisions,
        // demo stand-in for the PC's note reader: any note shared with all clips shows up as a rule
        rules: p.action === "revise" && p.note && p.applyAll !== false
          ? [{ id: `demo-rule-${Date.now()}`, key: "zoom_style", value: "smooth", label: `From your note: ${p.note}`,
               note: p.note, clip_id: p.clip.id, active: true, fixed_count: 0, created_at: new Date().toISOString() },
             ...s.rules]
          : s.rules,
      }));
      return;
    }
    // Revision box: kind 'other', the typed text as the note. The PC reads it (P4) and, unless Zo
    // turned it off, keeps its style asks as standing rules for every later clip (D078).
    const { error: e } = await browserClient().rpc("review_clip", {
      p_clip: p.clip.id, p_action: p.action, p_note: p.note ?? null, p_kind: "other",
      p_payload: p.action === "revise" ? { apply_all: p.applyAll !== false } : p.platforms ? { platforms: p.platforms } : {},
    });
    if (e) setError(e.message);
    await refresh();
  }, [refresh]);

  const flush = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    const p = pendingRef.current;
    pendingRef.current = null;
    setPending(null);
    if (p) void commit(p);
  }, [commit]);

  const canReview = useCallback((clip: Clip) => !PODS_ON || podCanReview(clip, accessRef.current, snapRef.current.pods), []);

  const act = useCallback((clip: Clip, action: ReviewAction, note?: string, applyAll?: boolean) => {
    if (!canReview(clip)) { setError("Only the owner of this clip's pod can review it."); return; }
    // Approving is what makes the PC post, so it only happens through post() after the confirm dialog (D116).
    if (action === "approve") { setError("Approve, then Post: posting always asks to confirm first."); return; }
    flush();
    if (action === "revise") { void commit({ clip, action, note, applyAll, until: Date.now() }); return; }
    const p = { clip, action, note, until: Date.now() + UNDO_MS };
    pendingRef.current = p;
    setPending(p);
    timer.current = setTimeout(flush, UNDO_MS);
  }, [commit, flush, canReview]);

  const post = useCallback((clip: Clip, platforms: string[]) => {
    if (!canReview(clip)) { setError("Only the owner of this clip's pod can review it."); return; }
    if (!platforms.length) { setError("Pick at least one platform before posting."); return; }
    flush();
    const p = { clip, action: "approve" as const, platforms, until: Date.now() + UNDO_MS };
    pendingRef.current = p;
    setPending(p);
    timer.current = setTimeout(flush, UNDO_MS);
  }, [flush, canReview]);

  const requestClip = useCallback(async (slug: string, seconds: number) => {
    if (IS_DEMO) return null;
    const { error: e } = await browserClient().rpc("request_clip", { p_streamer: slug, p_seconds: Math.max(10, Math.min(90, Math.round(seconds))) });
    return e ? e.message : null;
  }, []);

  // Non-clip actions on the same undo pattern: run after UNDO_MS unless undone.
  const flushLater = useCallback(() => {
    if (laterTimer.current) clearTimeout(laterTimer.current);
    laterTimer.current = null;
    const d = laterRef.current;
    laterRef.current = null;
    setLater(null);
    if (d) void d.run();
  }, []);

  const defer = useCallback((key: string, verb: string, label: string, run: () => Promise<void>) => {
    flushLater();
    const d: Deferred = { key, verb, label, until: Date.now() + UNDO_MS, run };
    laterRef.current = d;
    setLater(d);
    laterTimer.current = setTimeout(flushLater, UNDO_MS);
  }, [flushLater]);

  const undo = useCallback(() => {
    if (!pendingRef.current && laterRef.current) {
      if (laterTimer.current) clearTimeout(laterTimer.current);
      laterTimer.current = null;
      laterRef.current = null;
      setLater(null);
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    pendingRef.current = null;
    setPending(null);
  }, []);

  // Leaving the page commits whatever is waiting, so nothing is silently lost.
  useEffect(() => {
    const h = () => { const p = pendingRef.current; if (p) void commit(p); const d = laterRef.current; laterRef.current = null; if (d) void d.run(); };
    window.addEventListener("pagehide", h);
    return () => window.removeEventListener("pagehide", h);
  }, [commit]);

  const setRuleActive = useCallback(async (id: string, on: boolean) => {
    setSnap((s) => ({ ...s, rules: s.rules.map((r) => (r.id === id ? { ...r, active: on } : r)) }));
    if (IS_DEMO) return;
    const { error: e } = await browserClient().rpc("set_rule_active", { p_rule: id, p_on: on });
    if (e) setError(e.message);
    await refresh();
  }, [refresh]);

  const markSubmitted = useCallback(async (id: string) => {
    const at = new Date().toISOString();
    setSnap((s) => ({ ...s, submissions: s.submissions.map((x) => (x.id === id ? { ...x, submitted_at: at, status: "submitted" } : x)) }));
    if (IS_DEMO) return;
    const { error: e } = await browserClient().rpc("mark_submitted", { p_submission: id });
    if (e) setError(e.message);
    await refresh();
  }, [refresh]);

  // Private clip links (D056): short-lived signed URLs, cached until 10 min before expiry.
  const mediaUrl = useCallback(async (path: string | null, download?: string) => {
    if (!path) return null;
    if (IS_DEMO) return path;
    const key = `${path}|${download ?? ""}`;
    const hit = urls.current.get(key);
    if (hit && hit.exp > Date.now()) return hit.url;
    const { data, error: e } = await browserClient().storage.from("clips")
      .createSignedUrl(path, 3600, download ? { download } : undefined);
    if (e || !data) return null;
    urls.current.set(key, { url: data.signedUrl, exp: Date.now() + 50 * 60_000 });
    return data.signedUrl;
  }, []);

  const markTiktokPosted = useCallback(async (id: string, url: string) => {
    const at = new Date().toISOString();
    if (IS_DEMO) {
      setSnap((s) => ({ ...s, longform: s.longform.map((v) => (v.id === id ? { ...v, tiktok_url: url, posted_at: at } : v)) }));
      return true;
    }
    const { error: e } = await browserClient().rpc("mark_tiktok_posted", { p_video: id, p_url: url });
    if (e) { setError(e.message); return false; }
    await refresh();
    return true;
  }, [refresh]);

  const addTiktokStats = useCallback(async (id: string, stats: TiktokStats) => {
    if (IS_DEMO) return true;
    const { error: e } = await browserClient().from("tiktok_stats").insert({ video_id: id, ...stats });
    if (e) { setError(e.message); return false; }
    await refresh();
    return true;
  }, [refresh]);

  const setNotice = useCallback(async (id: string, notice: LongformVideo["notice"]) => {
    setSnap((s) => ({ ...s, longform: s.longform.map((v) => (v.id === id ? { ...v, notice } : v)) }));
    if (IS_DEMO) return;
    const { error: e } = await browserClient().rpc("set_tiktok_notice", { p_video: id, p_notice: notice });
    if (e) setError(e.message);
    await refresh();
  }, [refresh]);

  const sendEdit = useCallback(async (clip: Clip, plan: EditPlan, base: EditPlan) => {
    const note = editNote(plan, base);
    if (!canReview(clip)) { setError("Only the owner of this clip's pod can review it."); return false; }
    if (IS_DEMO) {
      setSnap((s) => ({
        ...s,
        clips: s.clips.map((c) => (c.id === clip.id ? { ...c, state: "revise" } : c)),
        revisions: [{ id: `demo-rev-${Date.now()}`, clip_id: clip.id, kind: "trim", note, created_at: new Date().toISOString(), resolved_at: null }, ...s.revisions],
      }));
      // Demo stand-in for the PC re-render: the edited clip comes back to review a few seconds later.
      setTimeout(() => setSnap((s) => ({
        ...s,
        clips: s.clips.map((c) => (c.id === clip.id && c.state === "revise"
          ? { ...c, state: "pending_review", hook: plan.headline || c.hook, duration_s: +(plan.trim_out - plan.trim_in).toFixed(1), revision: c.revision + 1 } : c)),
        revisions: s.revisions.map((r) => (r.clip_id === clip.id && !r.resolved_at ? { ...r, resolved_at: new Date().toISOString() } : r)),
      })), 5000);
      return true;
    }
    const { error: e } = await browserClient().rpc("review_clip", {
      p_clip: clip.id, p_action: "revise", p_note: note, p_kind: "trim", p_payload: { edit: editPayload(plan, base), apply_all: false },
    });
    if (e) { setError(e.message); return false; }
    await refresh();
    return true;
  }, [refresh, canReview]);

  const setBrain = useCallback(async (streamerId: string, weights: Record<string, number>, words?: string[]) => {
    const at = new Date().toISOString();
    setSnap((s) => {
      const cur = s.brains.find((b) => b.streamer_id === streamerId);
      const next = { streamer_id: streamerId, weights: { ...cur?.weights, ...weights }, words: words ?? cur?.words ?? [], updated_at: at };
      return { ...s, brains: [...s.brains.filter((b) => b.streamer_id !== streamerId), next] };
    });
    if (IS_DEMO) return;
    const { error: e } = await browserClient().rpc("set_brain_weights", { p_streamer: streamerId, p_weights: weights, p_words: words ?? null });
    if (e) setError(`Brain weights did not save: ${e.message}`);
  }, []);

  const setTiktokChannel = useCallback(async (followers: number | null, views: number | null, posts: number | null) => {
    const at = new Date().toISOString();
    const row: LiveStat = { key: "tiktok:own", kind: "own", platform: "tiktok", is_live: null, viewers: null, followers, views, posts,
      title: null, game: null, started_at: null, avatar_url: null, updated_at: at };
    setSnap((s) => ({ ...s, live: [...s.live.filter((x) => x.key !== row.key), row] }));
    if (IS_DEMO) return true;
    const { error: e } = await browserClient().rpc("set_manual_stat", { p_followers: followers, p_views: views, p_posts: posts });
    if (e) { setError(e.message); return false; }
    return true;
  }, []);

  const pollLive = useCallback(async (force = false) => {
    if (IS_DEMO) { setSnap((s) => ({ ...s, live: driftLive(s.live) })); return; }
    const r = await fetch(`/api/live${force ? "?force=1" : ""}`, { method: "POST" }).catch(() => null);
    if (r && !r.ok) {
      const j = (await r.json().catch(() => ({}))) as { error?: string };
      setError(`Live numbers: ${j.error ?? r.status}`);
    }
  }, []);

  const signOut = useCallback(async () => {
    if (IS_DEMO) return;
    await browserClient().auth.signOut();
    window.location.href = "/login";
  }, []);

  const setPodCampaign = useCallback(async (podId: string, campaign: string, status: "joined" | "declined", label: string) => {
    if (!isPodOwner(podId, accessRef.current, snapRef.current.pods)) return "Only this pod's owner joins or declines campaigns.";
    const save = async (): Promise<string | null> => {
      if (IS_DEMO) {
        const at = new Date().toISOString();
        setSnap((s) => ({ ...s, podCampaigns: s.podCampaigns.map((r) => (r.pod_id === podId && r.campaign_id === campaign
          ? { ...r, status, decided_at: at } : r)) }));
        return null;
      }
      const { error: e } = await browserClient().rpc("pod_campaign_set", { p_pod: podId, p_campaign: campaign, p_status: status });
      if (e) { setError(e.message); return e.message; }
      await refresh();
      return null;
    };
    if (status === "joined") return save();
    defer(`camp:${podId}:${campaign}`, "Declined", label, async () => { await save(); });
    return null;
  }, [refresh, defer]);

  // Demo stand-in for ledger_guard + ledger_audit: apply the row, append its audit event, rebuild the statement view.
  const demoLedgerWrite = useCallback((row: LedgerEntry, from: LedgerEntry["status"] | null) => {
    const at = new Date().toISOString();
    setSnap((s) => {
      const ledger = from === null ? [row, ...s.ledger] : s.ledger.map((r) => (r.id === row.id ? row : r));
      return { ...s, ledger, ledgerEvents: [demoEvent(row, from, at), ...s.ledgerEvents], statements: demoStatements(ledger) };
    });
  }, []);

  const notAdmin = () => (accessRef.current?.admin ? null : "Only the agency admin changes the ledger.");

  const ledgerAdd = useCallback(async (podId: string, campaign: string | null, sourceRef: string, grossCents: number, note: string | null) => {
    const no = notAdmin(); if (no) return no;
    if (IS_DEMO) {
      if (snapRef.current.ledger.some((r) => r.pod_id === podId && r.source === "campaign" && r.source_ref === sourceRef)) {
        return "This source ref is already in the ledger for this pod.";
      }
      demoLedgerWrite(demoEntry({ id: `le-${Date.now()}`, pod_id: podId, source_ref: sourceRef, campaign_id: campaign, gross_cents: grossCents,
        note, created_at: new Date().toISOString() }), null);
      return null;
    }
    const { error: e } = await browserClient().rpc("ledger_add", { p_pod: podId, p_campaign: campaign, p_source_ref: sourceRef,
      p_gross_cents: grossCents, p_note: note });
    if (e) return e.message;
    await refresh();
    return null;
  }, [refresh, demoLedgerWrite]);

  const ledgerStep = useCallback(async (entry: LedgerEntry, to: "cleared" | "approved" | "paid", ref?: string) => {
    const no = notAdmin(); if (no) return no;
    if (to === "paid" && !ref?.trim()) return "Mark paid needs the transfer reference.";
    const save = async (): Promise<string | null> => {
      if (IS_DEMO) {
        const at = new Date().toISOString();
        demoLedgerWrite({ ...entry, status: to, cleared_at: to === "cleared" ? at : entry.cleared_at,
          approved_at: to === "approved" ? at : entry.approved_at, paid_at: to === "paid" ? at : entry.paid_at,
          paid_ref: to === "paid" ? ref!.trim() : entry.paid_ref }, entry.status);
        return null;
      }
      const { error: e } = await browserClient().rpc("ledger_set_status", { p_entry: entry.id, p_status: to, p_ref: to === "paid" ? ref!.trim() : null });
      if (e) { setError(e.message); return e.message; }
      await refresh();
      return null;
    };
    if (to === "paid") return save();
    const what = `${entry.source_ref} · ${entry.source === "reversal" ? "reversal" : "entry"}`;
    defer(`ledger:${entry.id}`, to === "cleared" ? "Marked cleared" : "Approved", what, async () => { await save(); });
    return null;
  }, [refresh, defer, demoLedgerWrite]);

  const ledgerReverse = useCallback(async (entry: LedgerEntry, reason: string) => {
    const no = notAdmin(); if (no) return no;
    if (!reason.trim()) return "A reversal needs a reason.";
    if (IS_DEMO) {
      if (entry.source === "reversal") return "cannot reverse a reversal";
      if (snapRef.current.ledger.some((r) => r.reverses_id === entry.id)) return "This entry is already reversed.";
      demoLedgerWrite(demoEntry({ id: `le-${Date.now()}`, pod_id: entry.pod_id, source: "reversal", source_ref: `rev:${entry.id}`,
        campaign_id: entry.campaign_id, gross_cents: -entry.gross_cents, agency_rate: entry.agency_rate, note: reason.trim(),
        reverses_id: entry.id, created_at: new Date().toISOString() }), null);
      return null;
    }
    const { error: e } = await browserClient().rpc("ledger_reverse", { p_entry: entry.id, p_note: reason.trim() });
    if (e) return e.message;
    await refresh();
    return null;
  }, [refresh, demoLedgerWrite]);

  const setPod = useCallback((id: string | null) => {
    setPicked(id);
    try { if (id) localStorage.setItem(POD_KEY, id); else localStorage.removeItem(POD_KEY); } catch { /* pick lasts this visit */ }
  }, []);

  // A stale pick (pod gone, or no longer admin) falls back to All.
  const pod = PODS_ON ? scopedPod(access, picked && snap.pods.some((p) => p.id === picked) ? picked : null) : null;
  const view = useMemo(() => (PODS_ON ? podSnapshot(snap, pod) : snap), [snap, pod]);

  const value = useMemo<Store>(() => ({
    demo: IS_DEMO, ready, error, snap: view, podsOn: PODS_ON, access, pod, setPod, canReview, pending, later, setPodCampaign, ledgerAdd, ledgerStep, ledgerReverse, act, post, requestClip, undo,
    setRuleActive, markSubmitted, mediaUrl,
    markTiktokPosted, addTiktokStats, setNotice, sendEdit, setBrain, setTiktokChannel, pollLive, signOut,
  }), [ready, error, view, access, pod, setPod, canReview, pending, later, setPodCampaign, ledgerAdd, ledgerStep, ledgerReverse, act, post, requestClip, undo, setRuleActive, markSubmitted, mediaUrl,
    markTiktokPosted, addTiktokStats, setNotice, sendEdit, setBrain, setTiktokChannel, pollLive, signOut]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

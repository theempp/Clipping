"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { demoSnapshot } from "./demo";
import { IS_DEMO } from "./env";
import { browserClient } from "./supabase/client";
import type { Clip, EditPlan, LongformVideo, ReviewAction, Snapshot, TiktokStats } from "./types";
import { editNote, editPayload } from "./logic";
import type { LiveStat } from "./types";

/** Demo only: nudge live viewer counts a little, like a real stream. */
function driftLive(rows: LiveStat[]): LiveStat[] {
  const at = new Date().toISOString();
  return rows.map((r) => (r.is_live && r.viewers != null
    ? { ...r, viewers: Math.max(50, Math.round(r.viewers * (1 + (Math.random() - 0.48) * 0.02))), updated_at: at } : r));
}

export const UNDO_MS = 4000;

type Pending = { clip: Clip; action: ReviewAction; note?: string; applyAll?: boolean; until: number };

type Store = {
  demo: boolean;
  ready: boolean;
  error: string | null;
  snap: Snapshot;
  pending: Pending | null;
  /** Approve / deny wait UNDO_MS before they reach the database, so a stray key press can be undone. */
  /** applyAll (revise only): the note's style asks also become standing rules for every clip (D078). */
  act: (clip: Clip, action: ReviewAction, note?: string, applyAll?: boolean) => void;
  undo: () => void;
  setRuleActive: (id: string, on: boolean) => Promise<void>;
  setAwake: (on: boolean) => Promise<void>;
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
  streamers: [], clips: [], submissions: [], heartbeat: null,
  control: { awake: false, updated_at: new Date(0).toISOString() }, candidates: [], spend: [], revisions: [], rules: [],
  longform: [], results: [], live: [], history: [], publications: [], campaigns: [], brains: [],
};

const Ctx = createContext<Store | null>(null);

const DEMO_KEY = "clipp.demo.awake";
function readDemoAwake(): boolean {
  try { return localStorage.getItem(DEMO_KEY) === "1"; } catch { return false; }
}
function writeDemoAwake(on: boolean) {
  try { localStorage.setItem(DEMO_KEY, on ? "1" : "0"); } catch { /* storage blocked: state lasts this visit only */ }
}
/** Demo snapshot with the PC told to sleep: switch off, heartbeat reports asleep, nobody watched. */
function demoSleep(s: Snapshot): Snapshot {
  const at = new Date().toISOString();
  return {
    ...s,
    control: { awake: false, updated_at: at },
    heartbeat: s.heartbeat && { ...s.heartbeat, seen_at: at,
      status: { ...s.heartbeat.status, awake: false, live: [], gpu: { ...s.heartbeat.status.gpu, util: 4 } } },
  };
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
  const since6h = new Date(Date.now() - 6 * 3600_000).toISOString();
  const since24h = new Date(Date.now() - 24 * 3600_000).toISOString();
  const month = new Date(); month.setUTCDate(1); month.setUTCHours(0, 0, 0, 0);
  const [st, cl, su, hb, co, ca, sp, rv, ru, lf, lr] = await Promise.all([
    sb.from("streamers").select("id,slug,display_name,twitch_login,kick_slug,avatar_url").order("display_name"),
    sb.from("clips").select("*").order("created_at", { ascending: false }).limit(300),
    sb.from("submissions_live").select("*").gte("created_at", since24h).order("deadline_at"),
    sb.from("worker_heartbeat").select("*").order("seen_at", { ascending: false }).limit(1),
    sb.from("control").select("awake,updated_at").limit(1),
    sb.from("candidate_log").select("channel_key,moment_at,score,outcome").gte("moment_at", since6h)
      .order("moment_at").limit(3000),
    sb.from("spend_month").select("kind,usd").gte("month", month.toISOString()),
    sb.from("revisions").select("id,clip_id,kind,note,created_at,resolved_at")
      .order("created_at", { ascending: false }).limit(200),
    sb.from("edit_rules").select("id,key,value,label,note,clip_id,active,fixed_count,created_at")
      .order("created_at", { ascending: false }).limit(50),
    sb.from("longform_videos").select("id,clip_id,channel,format,pacing,caption_style,voice,layout,runtime_s,coverage,tiktok_url,posted_at,notice")
      .order("created_at", { ascending: false }).limit(200),
    sb.from("longform_results").select("*"),
  ]);
  const err = [st, cl, su, hb, co, ca, sp, rv, ru, lf, lr].find((r) => r.error)?.error;
  if (err) throw new Error(err.message);
  // Newer tables (live numbers, brain, schedule) are optional: until their migration is applied they read as empty.
  const since30d = new Date(Date.now() - 30 * 86400_000).toISOString();
  const [li, hi, pu, de, cm, br] = await Promise.all([
    sb.from("live_stats").select("*"),
    sb.from("stat_snapshots").select("key,metric,value,at").gte("at", since30d).order("at").limit(5000),
    sb.from("publications").select("id,clip_id,destination_id,status,url,posted_at,created_at").order("created_at", { ascending: false }).limit(200),
    sb.from("destinations").select("id,platform,label"),
    sb.from("campaigns").select("id,title,status,source_url,streamer_slugs,platforms,cpm_usd,cap_usd,deadline,score,recommendation,created_at")
      .order("created_at", { ascending: false }).limit(100),
    sb.from("streamer_brain").select("streamer_id,weights,words,updated_at"),
  ]);
  const ok = <T,>(r: { data: T[] | null; error: unknown }): T[] => (r.error ? [] : r.data ?? []);
  const dest = new Map(ok(de).map((d) => [d.id, d]));
  const opt = {
    live: ok(li),
    history: ok(hi).map((p) => ({ ...p, value: Number(p.value) })),
    publications: ok(pu).map((p) => ({ ...p, platform: dest.get(p.destination_id)?.platform ?? null, label: dest.get(p.destination_id)?.label ?? null })),
    campaigns: ok(cm).map((c) => ({ ...c, cpm_usd: c.cpm_usd == null ? null : Number(c.cpm_usd), cap_usd: c.cap_usd == null ? null : Number(c.cap_usd), score: c.score == null ? null : Number(c.score) })),
    brains: ok(br),
  };
  return {
    ...opt,
    streamers: st.data ?? [],
    clips: cl.data ?? [],
    submissions: su.data ?? [],
    heartbeat: hb.data?.[0] ?? null,
    control: co.data?.[0] ?? EMPTY.control,
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
  const pendingRef = useRef<Pending | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const urls = useRef(new Map<string, { url: string; exp: number }>());
  // While a Wake Up write is in flight, a refresh that started earlier must not flip the switch back.
  const awakeWant = useRef<boolean | null>(null);
  const snapRef = useRef(snap);
  snapRef.current = snap;

  const refresh = useCallback(async () => {
    if (IS_DEMO) return;
    try {
      const sb = browserClient();
      const { data: owner, error: e } = await sb.rpc("is_owner");
      if (e) throw new Error(e.message);
      if (!owner) { setError("not-owner"); setReady(true); return; }
      const next = await loadLive();
      const want = awakeWant.current;
      setSnap(want == null ? next : { ...next, control: { ...next.control, awake: want } });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReady(true);
    }
  }, []);

  // Initial load, realtime refresh (debounced), and a 30 s safety poll.
  useEffect(() => {
    if (IS_DEMO) {
      // Demo keeps the switch across reloads; it starts asleep until Zo wakes it.
      const on = readDemoAwake();
      const d = demoSnapshot();
      setSnap(on ? d : demoSleep(d));
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
    for (const table of ["clips", "worker_heartbeat", "submissions", "control", "edit_rules", "longform_videos", "streamer_brain", "publications"]) {
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
      setSnap((s) => ({
        ...s,
        clips: s.clips.map((c) => (c.id === p.clip.id ? { ...c, state: to, reviewed_at: new Date().toISOString() } : c)),
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
      p_payload: p.action === "revise" ? { apply_all: p.applyAll !== false } : {},
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

  const act = useCallback((clip: Clip, action: ReviewAction, note?: string, applyAll?: boolean) => {
    flush();
    if (action === "revise") { void commit({ clip, action, note, applyAll, until: Date.now() }); return; }
    const p = { clip, action, note, until: Date.now() + UNDO_MS };
    pendingRef.current = p;
    setPending(p);
    timer.current = setTimeout(flush, UNDO_MS);
  }, [commit, flush]);

  const undo = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    pendingRef.current = null;
    setPending(null);
  }, []);

  // Leaving the page commits whatever is waiting, so nothing is silently lost.
  useEffect(() => {
    const h = () => { const p = pendingRef.current; if (p) void commit(p); };
    window.addEventListener("pagehide", h);
    return () => window.removeEventListener("pagehide", h);
  }, [commit]);

  const setAwake = useCallback(async (on: boolean) => {
    if (IS_DEMO) {
      writeDemoAwake(on);
      setSnap((s) => (on ? { ...demoSnapshot(), clips: s.clips, submissions: s.submissions, revisions: s.revisions } : demoSleep(s)));
      return;
    }
    const prev = snapRef.current.control.awake;
    setSnap((s) => ({ ...s, control: { awake: on, updated_at: new Date().toISOString() } }));
    awakeWant.current = on;
    const { error: e } = await browserClient().rpc("set_awake", { p_on: on });
    awakeWant.current = null;
    if (e) {
      setError(`Wake Up did not save: ${e.message}`);
      setSnap((s) => ({ ...s, control: { ...s.control, awake: prev } }));
      return;
    }
    await refresh();
  }, [refresh]);

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
    const note = editNote(plan, clip.duration_s ?? plan.trim_out);
    if (IS_DEMO) {
      setSnap((s) => ({
        ...s,
        clips: s.clips.map((c) => (c.id === clip.id ? { ...c, state: "revise", title: plan.headline || c.title } : c)),
        revisions: [{ id: `demo-rev-${Date.now()}`, clip_id: clip.id, kind: "trim", note, created_at: new Date().toISOString(), resolved_at: null }, ...s.revisions],
      }));
      return true;
    }
    const { error: e } = await browserClient().rpc("review_clip", {
      p_clip: clip.id, p_action: "revise", p_note: note, p_kind: "trim", p_payload: { edit: editPayload(plan, base), apply_all: false },
    });
    if (e) { setError(e.message); return false; }
    await refresh();
    return true;
  }, [refresh]);

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

  const value = useMemo<Store>(() => ({
    demo: IS_DEMO, ready, error, snap, pending, act, undo, setRuleActive, setAwake, markSubmitted, mediaUrl,
    markTiktokPosted, addTiktokStats, setNotice, sendEdit, setBrain, setTiktokChannel, pollLive, signOut,
  }), [ready, error, snap, pending, act, undo, setRuleActive, setAwake, markSubmitted, mediaUrl, markTiktokPosted,
    addTiktokStats, setNotice, sendEdit, setBrain, setTiktokChannel, pollLive, signOut]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

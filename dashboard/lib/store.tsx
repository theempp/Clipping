"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { demoSnapshot } from "./demo";
import { IS_DEMO } from "./env";
import { browserClient } from "./supabase/client";
import type { Clip, LongformVideo, ReviewAction, Snapshot, TiktokStats } from "./types";

export const UNDO_MS = 4000;

type Pending = { clip: Clip; action: ReviewAction; note?: string; until: number };

type Store = {
  demo: boolean;
  ready: boolean;
  error: string | null;
  snap: Snapshot;
  pending: Pending | null;
  /** Approve / deny wait UNDO_MS before they reach the database, so a stray key press can be undone. */
  act: (clip: Clip, action: ReviewAction, note?: string) => void;
  undo: () => void;
  setAwake: (on: boolean) => Promise<void>;
  markSubmitted: (id: string) => Promise<void>;
  mediaUrl: (path: string | null, download?: string) => Promise<string | null>;
  /** TikTok is uploaded by hand (D074); these record the post, its stats and any eligibility notice. */
  markTiktokPosted: (id: string, url: string) => Promise<boolean>;
  addTiktokStats: (id: string, stats: TiktokStats) => Promise<boolean>;
  setNotice: (id: string, notice: LongformVideo["notice"]) => Promise<void>;
  signOut: () => Promise<void>;
};

const EMPTY: Snapshot = {
  streamers: [], clips: [], submissions: [], heartbeat: null,
  control: { awake: false, updated_at: new Date(0).toISOString() }, candidates: [], spend: [], revisions: [],
  longform: [], results: [],
};

const Ctx = createContext<Store | null>(null);

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
  const [st, cl, su, hb, co, ca, sp, rv, lf, lr] = await Promise.all([
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
    sb.from("longform_videos").select("id,clip_id,channel,format,pacing,caption_style,voice,layout,runtime_s,coverage,tiktok_url,posted_at,notice")
      .order("created_at", { ascending: false }).limit(200),
    sb.from("longform_results").select("*"),
  ]);
  const err = [st, cl, su, hb, co, ca, sp, rv, lf, lr].find((r) => r.error)?.error;
  if (err) throw new Error(err.message);
  return {
    streamers: st.data ?? [],
    clips: cl.data ?? [],
    submissions: su.data ?? [],
    heartbeat: hb.data?.[0] ?? null,
    control: co.data?.[0] ?? EMPTY.control,
    candidates: ca.data ?? [],
    spend: (sp.data ?? []).map((r) => ({ kind: r.kind, usd: Number(r.usd) })),
    revisions: rv.data ?? [],
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

  const refresh = useCallback(async () => {
    if (IS_DEMO) return;
    try {
      const sb = browserClient();
      const { data: owner, error: e } = await sb.rpc("is_owner");
      if (e) throw new Error(e.message);
      if (!owner) { setError("not-owner"); setReady(true); return; }
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
    if (IS_DEMO) { setSnap(demoSnapshot()); setReady(true); return; }
    void refresh();
    const sb = browserClient();
    let t: ReturnType<typeof setTimeout> | null = null;
    const bump = () => { if (t) clearTimeout(t); t = setTimeout(() => void refresh(), 400); };
    const ch = sb.channel("clipp-dashboard");
    for (const table of ["clips", "worker_heartbeat", "submissions", "control", "longform_videos"]) {
      ch.on("postgres_changes", { event: "*", schema: "public", table }, bump);
    }
    ch.subscribe();
    const poll = setInterval(() => void refresh(), 30_000);
    return () => { clearInterval(poll); if (t) clearTimeout(t); void sb.removeChannel(ch); };
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
      }));
      return;
    }
    // Revision box: kind 'other', the typed text as the note, empty payload (worker parses it, P4).
    const { error: e } = await browserClient().rpc("review_clip", {
      p_clip: p.clip.id, p_action: p.action, p_note: p.note ?? null, p_kind: "other", p_payload: {},
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

  const act = useCallback((clip: Clip, action: ReviewAction, note?: string) => {
    flush();
    if (action === "revise") { void commit({ clip, action, note, until: Date.now() }); return; }
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
      setSnap((s) => ({
        ...s,
        control: { awake: on, updated_at: new Date().toISOString() },
        heartbeat: s.heartbeat && { ...s.heartbeat, seen_at: new Date().toISOString(),
          status: { ...s.heartbeat.status, awake: on, live: on ? ["twitch:xqc", "twitch:stableronaldo", "twitch:kaicenat"] : [],
            gpu: { ...s.heartbeat.status.gpu, util: on ? 62 : 4 } } },
      }));
      return;
    }
    setSnap((s) => ({ ...s, control: { awake: on, updated_at: new Date().toISOString() } }));
    const { error: e } = await browserClient().rpc("set_awake", { p_on: on });
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

  const signOut = useCallback(async () => {
    if (IS_DEMO) return;
    await browserClient().auth.signOut();
    window.location.href = "/login";
  }, []);

  const value = useMemo<Store>(() => ({
    demo: IS_DEMO, ready, error, snap, pending, act, undo, setAwake, markSubmitted, mediaUrl,
    markTiktokPosted, addTiktokStats, setNotice, signOut,
  }), [ready, error, snap, pending, act, undo, setAwake, markSubmitted, mediaUrl, markTiktokPosted,
    addTiktokStats, setNotice, signOut]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

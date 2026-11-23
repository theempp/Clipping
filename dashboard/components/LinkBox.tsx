"use client";
// Paste-a-link (D115): zo pastes a VOD / clip / video link, the PC cuts clips from it and they land
// in this Review queue as pending. Owner only (request_link_clips RPC checks is_owner). Nothing posts.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { IS_DEMO } from "@/lib/env";
import { ACTIVE, estimateUsd, findDuplicate, GROK_USD, linkKey, linkLabel, MAX_CLIPS, parseTime, statusLabel } from "@/lib/links";
import type { LinkJob } from "@/lib/links";
import { useStore } from "@/lib/store";
import { browserClient } from "@/lib/supabase/client";

const COLS = "id,url,url_key,platform,streamer,start_s,end_s,max_clips,full_frame,status,detail,source_title,duration_s,chat,candidates,judged,clips,dropped,est_usd,cost_usd,job_ids,requested_at,started_at,finished_at,updated_at";
const num = (v: unknown) => Number(v ?? 0);
const norm = (r: LinkJob): LinkJob => ({ ...r, est_usd: num(r.est_usd), cost_usd: num(r.cost_usd) });
const hms = (t: number) => { const s = Math.max(0, Math.floor(t)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}` : `${m}:${String(x).padStart(2, "0")}`; };
const usd = (v: number) => `$${v.toFixed(v < 0.1 ? 4 : 2)}`;

/** Demo: walk a fake request through the steps so the flow can be seen without the PC. */
function demoRun(job: LinkJob, set: (f: (js: LinkJob[]) => LinkJob[]) => void) {
  const steps: [number, Partial<LinkJob>][] = [
    [1500, { status: "fetching", detail: "downloading video" }],
    [3500, { status: "detecting", detail: "finding moments", chat: job.platform === "twitch" }],
    [5500, { status: "clipping", detail: `judging and rendering ${job.max_clips} moment(s)`, candidates: job.max_clips + 3 }],
    [8500, { status: "done", detail: `2 clip(s) in Review · ${job.max_clips - 2} dropped`, clips: 2, dropped: job.max_clips - 2,
      judged: job.max_clips, cost_usd: job.est_usd, finished_at: new Date().toISOString() }],
  ];
  for (const [ms, p] of steps) {
    setTimeout(() => set((js) => js.map((j) => (j.id === job.id && j.status !== "canceled" ? { ...j, ...p } : j))), ms);
  }
}

export function LinkBox() {
  const { snap } = useStore();
  const [jobs, setJobs] = useState<LinkJob[]>([]);
  const [url, setUrl] = useState("");
  const [streamer, setStreamer] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [max, setMax] = useState(6);
  const [full, setFull] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "ok" | "warn" | "bad"; text: string } | null>(null);
  const t = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    if (IS_DEMO) return;
    const { data, error } = await browserClient().from("link_jobs").select(COLS).order("requested_at", { ascending: false }).limit(12);
    if (error) { setMsg({ tone: "bad", text: `Link list did not load: ${error.message}` }); return; }
    setJobs((data as LinkJob[] | null ?? []).map(norm));
  }, []);

  useEffect(() => {
    if (IS_DEMO) return;
    void load();
    const sb = browserClient();
    const ch = sb.channel("clipp-links").on("postgres_changes", { event: "*", schema: "public", table: "link_jobs" }, () => {
      if (t.current) clearTimeout(t.current);
      t.current = setTimeout(() => void load(), 300);
    }).subscribe();
    const poll = setInterval(() => void load(), 30_000);
    return () => { clearInterval(poll); if (t.current) clearTimeout(t.current); void sb.removeChannel(ch); };
  }, [load]);

  const key = linkKey(url);
  const start = parseTime(from);
  const end = parseTime(to);
  const badTime = Number.isNaN(start) || Number.isNaN(end) || (start != null && end != null && end <= start);
  const dup = key && !badTime ? findDuplicate(jobs, key, start, end) : null;
  const est = estimateUsd(max);
  const canGo = !!key && !badTime && !busy;

  const submit = async () => {
    if (!key || badTime) return;
    setBusy(true); setMsg(null);
    try {
      if (dup) { setMsg({ tone: "warn", text: `Already pasted: ${statusLabel(dup.status).toLowerCase()}. Shown below.` }); return; }
      if (IS_DEMO) {
        const now = new Date().toISOString();
        const job: LinkJob = { id: `demo-link-${Date.now()}`, url: url.trim(), url_key: key, platform: key.split(":")[0] as LinkJob["platform"],
          streamer: streamer || null, start_s: start, end_s: end, max_clips: max, full_frame: full, status: "queued", detail: null,
          source_title: null, duration_s: null, chat: null, candidates: 0, judged: 0, clips: 0, dropped: 0, est_usd: est, cost_usd: 0,
          job_ids: [], requested_at: now, started_at: null, finished_at: null, updated_at: now };
        setJobs((js) => [job, ...js]);
        demoRun(job, setJobs);
      } else {
        const { data, error } = await browserClient().rpc("request_link_clips", {
          p_url: url.trim(), p_streamer: streamer || null, p_start: start, p_end: end, p_max: max, p_full_frame: full,
        });
        if (error) { setMsg({ tone: "bad", text: error.message }); return; }
        const r = data as { job: LinkJob; duplicate: boolean };
        if (r.duplicate) { setMsg({ tone: "warn", text: `Already pasted: ${statusLabel(r.job.status).toLowerCase()}. Shown below.` }); await load(); return; }
        await load();
      }
      setMsg({ tone: "ok", text: "Queued. The PC picks it up within 15 seconds while the worker runs." });
      setUrl(""); setFrom(""); setTo("");
    } finally { setBusy(false); }
  };

  const cancel = async (j: LinkJob) => {
    if (IS_DEMO) { setJobs((js) => js.map((x) => (x.id === j.id ? { ...x, status: "canceled", detail: "canceled from the dashboard" } : x))); return; }
    const { error } = await browserClient().rpc("cancel_link_job", { p_id: j.id });
    if (error) setMsg({ tone: "bad", text: error.message });
    await load();
  };

  const names = useMemo(() => new Map(snap.streamers.map((s) => [s.slug, s.display_name])), [snap.streamers]);
  const spent = jobs.reduce((a, j) => a + j.cost_usd, 0);

  return (
    <section className="glass" aria-label="Clips from a link">
      <div className="hd"><h3><Icon name="scissors" /> Clips from a link</h3><span className="r">lands here as pending</span></div>
      <form className="lk-form" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
        <input type="url" inputMode="url" className="in" placeholder="Paste a Twitch, Kick, YouTube or X link" value={url}
          onChange={(e) => setUrl(e.target.value)} aria-label="Video link" aria-invalid={!!url && !key} />
        {url && <p className={`quiet${key ? "" : " bad"}`}>{key ? `${linkLabel(key)}${dup ? " · already pasted" : ""}` : "Not a supported video link"}</p>}
        <div className="lk-opts">
          <label className="field"><span>Streamer</span>
            <select value={streamer} onChange={(e) => setStreamer(e.target.value)}>
              <option value="">Detect from link</option>
              {snap.streamers.map((s) => <option key={s.id} value={s.slug}>{s.display_name}</option>)}
            </select></label>
          <label className="field"><span>From (optional)</span>
            <input type="text" inputMode="numeric" placeholder="1:00:00" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label className="field"><span>To (optional)</span>
            <input type="text" inputMode="numeric" placeholder="1:30:00" value={to} onChange={(e) => setTo(e.target.value)} /></label>
          <label className="field"><span>Most clips</span>
            <input type="number" min={1} max={MAX_CLIPS} value={max}
              onChange={(e) => setMax(Math.max(1, Math.min(MAX_CLIPS, Number(e.target.value) || 1)))} /></label>
        </div>
        {badTime && <p className="quiet bad">Times are h:mm:ss or seconds, and To must be after From.</p>}
        <label className="lk-check"><input type="checkbox" checked={full} onChange={(e) => setFull(e.target.checked)} />
          <span>Full frame (IRL / no facecam): face-tracked, no split</span></label>
        <div className="lk-go">
          <span className="mut">Grok up to {usd(est)} ({max} × {usd(GROK_USD)})</span>
          <button type="submit" className="b ok" disabled={!canGo}><Icon name="scissors" /> Make clips</button>
        </div>
        {msg && <p className={`quiet ${msg.tone}`} role="status">{msg.text}</p>}
      </form>

      {jobs.length > 0 && (
        <ul className="tt-list lk-list">
          {jobs.slice(0, 6).map((j) => (
            <li key={j.id} className="tt-row">
              <div className="tt-top">
                <span className="tx">
                  <b title={j.url}>{j.source_title || linkLabel(j.url_key) || j.url}</b>
                  <span>{j.streamer ? names.get(j.streamer) ?? j.streamer : "detecting streamer"}
                    {j.start_s != null || j.end_s != null ? ` · ${hms(j.start_s ?? 0)}–${j.end_s != null ? hms(j.end_s) : "end"}` : ""}
                    {j.full_frame ? " · full frame" : ""}</span>
                </span>
                {ACTIVE.includes(j.status)
                  ? <button type="button" className="b" onClick={() => void cancel(j)}><Icon name="x" /> Cancel</button>
                  : j.status === "done" && j.clips > 0 ? <span className="chip acc">{j.clips} to review</span> : null}
              </div>
              <div className="chips">
                <span className={`chip${j.status === "failed" ? " warn" : j.status === "done" ? " on" : ""}`}>{statusLabel(j.status)}</span>
                {j.chat != null && <span className="chip">{j.chat ? "chat + audio" : "audio only"}</span>}
                {j.candidates > 0 && <span className="chip">{j.candidates} moments</span>}
                <span className="chip">{j.status === "done" ? `Grok ${usd(j.cost_usd)}` : `est. ${usd(j.est_usd)}`}</span>
              </div>
              {j.detail && <p className={`quiet${j.status === "failed" ? " bad" : ""}`}>{j.detail}</p>}
            </li>
          ))}
        </ul>
      )}
      {jobs.length > 0 && <p className="quiet">Link clips so far: Grok {usd(spent)}. Every clip still needs your approval.</p>}
    </section>
  );
}

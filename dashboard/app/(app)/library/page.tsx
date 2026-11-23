"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { ClipVideo } from "@/components/ClipCard";
import { Icon } from "@/components/Icon";
import { PodChip } from "@/components/PodChip";
import { downloadName } from "@/lib/logic";
import { useStore } from "@/lib/store";
import type { Clip, ClipState } from "@/lib/types";

const STATES: [ClipState | "all", string][] = [
  ["all", "All"], ["pending_review", "In review"], ["approved", "Approved"], ["scheduled", "Posting"],
  ["published", "Posted"], ["revise", "Revising"], ["rejected", "Denied"],
];

const SORTS = [["new", "Newest first"], ["old", "Oldest first"], ["score", "Top score"], ["long", "Longest"], ["short", "Shortest"]] as const;
type Sort = (typeof SORTS)[number][0];
const SORT_FN: Record<Sort, (a: Clip, b: Clip) => number> = {
  new: (a, b) => b.created_at.localeCompare(a.created_at),
  old: (a, b) => a.created_at.localeCompare(b.created_at),
  score: (a, b) => (b.score_10 ?? -1) - (a.score_10 ?? -1) || b.created_at.localeCompare(a.created_at),
  long: (a, b) => (b.duration_s ?? 0) - (a.duration_s ?? 0),
  short: (a, b) => (a.duration_s ?? 1e9) - (b.duration_s ?? 1e9),
};

export default function LibraryPage() {
  return <Suspense fallback={<div className="loading">Loading…</div>}><Library /></Suspense>;
}

/** Every clip the PC has made, playing in place. Filter by streamer and state; save any approved one. */
function Library() {
  const { snap, mediaUrl, act, canReview } = useStore();
  const params = useSearchParams();
  const [st, setSt] = useState<ClipState | "all">("all");
  const [who, setWho] = useState("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<Sort>("new");
  const [busy, setBusy] = useState<string | null>(null);
  const focus = params.get("clip");
  const base = useMemo(() => snap.clips.filter((c) => (who === "all" || c.streamer_id === who)
    && (!q.trim() || [c.title, c.job_id, c.hook, c.description].some((x) => x?.toLowerCase().includes(q.trim().toLowerCase())))), [snap.clips, who, q]);
  const counts = useMemo(() => { const m = new Map<string, number>(); for (const c of base) m.set(c.state, (m.get(c.state) ?? 0) + 1); return m; }, [base]);
  const list = useMemo(() => base.filter((c) => st === "all" || c.state === st)
    .sort((a, b) => Number(b.id === focus) - Number(a.id === focus) || SORT_FN[sort](a, b)),
  [base, st, sort, focus]);
  const byId = new Map(snap.streamers.map((s) => [s.id, s]));
  const save = async (c: Clip) => {
    setBusy(c.id);
    const name = downloadName(c, c.streamer_id ? byId.get(c.streamer_id) : undefined);
    const url = await mediaUrl(c.storage_path, name);
    setBusy(null);
    if (!url) return;
    const a = document.createElement("a");
    a.href = url; a.download = name; a.rel = "noopener";
    document.body.appendChild(a); a.click(); a.remove();
  };
  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}>
        <div><h1>Library<br /><b>{snap.clips.length} clips.</b></h1>
          <p>Clips play muted as you scroll. Approved and posted clips can be saved to your phone.</p></div>
      </section>
      <div className="filters">
        <input className="in" type="search" placeholder="Search titles, hooks, descriptions" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search clips" />
        <select className="in" value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort" style={{ flex: "0 1 170px" }}>
          {SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <select className="in" value={who} onChange={(e) => setWho(e.target.value)} aria-label="Streamer" style={{ flex: "0 1 200px" }}>
          <option value="all">Every streamer</option>
          {snap.streamers.map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}
        </select>
        <div className="seg" role="tablist" aria-label="State">
          {STATES.map(([k, l]) => {
            const n = k === "all" ? base.length : counts.get(k) ?? 0;
            return <button key={k} type="button" className={st === k ? "on" : ""} disabled={n === 0 && st !== k} onClick={() => setSt(k)}>{l} <span style={{ opacity: 0.6 }}>{n}</span></button>;
          })}
        </div>
      </div>
      <p className="quiet" style={{ margin: "0 0 14px" }}>{list.length} of {snap.clips.length} clips{q.trim() ? ` matching “${q.trim()}”` : ""}</p>
      <div className="lib">
        {list.map((c) => {
          const s = c.streamer_id ? byId.get(c.streamer_id) : undefined;
          const ok = ["approved", "scheduled", "published"].includes(c.state);
          return (
            <figure key={c.id} className="clip" style={c.id === focus ? { outline: "2px solid var(--acc)", borderRadius: 22, outlineOffset: 4 } : undefined}>
              <ClipVideo clip={c}><span className="sc">{c.score_10 ?? "—"}</span></ClipVideo>
              <figcaption>
                <b>{c.title ?? c.job_id}</b>
                <small>{s?.display_name ?? c.channel_key} · <span className={`st-${c.state}`}>{STATES.find(([k]) => k === c.state)?.[1] ?? c.state}</span> <PodChip clip={c} /></small>
                {c.state === "revise" && c.revise_failed && (
                  <p className="fixing bad" role="status">Revision {c.revise_failed.rev} failed QA: {c.revise_failed.reason}. The PC stopped retrying; deny it to clear it.</p>
                )}
                <div className="chips" style={{ marginTop: 8 }}>
                  {c.state === "revise" && c.revise_failed && canReview(c) && <button type="button" className="b ghost" onClick={() => act(c, "reject")}><Icon name="x" size={14} /> Deny</button>}
                  {c.state === "pending_review" && <Link className="b" href={`/review?clip=${c.id}`}>Review</Link>}
                  {c.state === "pending_review" && <Link className="b" href={`/editor?clip=${c.id}`}>Edit</Link>}
                  {ok && <button type="button" className="b" disabled={busy === c.id} onClick={() => void save(c)}><Icon name="download" size={14} /> {busy === c.id ? "…" : "Save"}</button>}
                </div>
              </figcaption>
            </figure>
          );
        })}
      </div>
      {list.length === 0 && <p className="quiet">No clips match.</p>}
    </>
  );
}

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
  const [busy, setBusy] = useState<string | null>(null);
  const focus = params.get("clip");
  const list = useMemo(() => snap.clips
    .filter((c) => (st === "all" || c.state === st) && (who === "all" || c.streamer_id === who)
      && (!q.trim() || (c.title ?? c.job_id).toLowerCase().includes(q.trim().toLowerCase())))
    .sort((a, b) => Number(b.id === focus) - Number(a.id === focus) || b.created_at.localeCompare(a.created_at)),
  [snap.clips, st, who, q, focus]);
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
        <input className="in" type="search" placeholder="Search titles" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search clips" />
        <select className="in" value={who} onChange={(e) => setWho(e.target.value)} aria-label="Streamer" style={{ flex: "0 1 200px" }}>
          <option value="all">Every streamer</option>
          {snap.streamers.map((s) => <option key={s.id} value={s.id}>{s.display_name}</option>)}
        </select>
        <div className="seg" role="tablist" aria-label="State">
          {STATES.map(([k, l]) => <button key={k} type="button" className={st === k ? "on" : ""} onClick={() => setSt(k)}>{l}</button>)}
        </div>
      </div>
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

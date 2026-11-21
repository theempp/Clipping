"use client";
import { useState } from "react";
import { downloadName } from "@/lib/logic";
import { useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { Icon } from "./Icon";

/** Approved clips, ready to save on the phone (D021) through a signed download link. */
export function ApprovedList() {
  const { snap, mediaUrl } = useStore();
  const [busy, setBusy] = useState<string | null>(null);
  const list = snap.clips
    .filter((c) => ["approved", "scheduled", "published"].includes(c.state))
    .sort((a, b) => (b.reviewed_at ?? "").localeCompare(a.reviewed_at ?? ""))
    .slice(0, 8);
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
  const label = (c: Clip) => (c.state === "approved" ? "waiting to post" : c.state === "scheduled" ? "posting" : "posted");
  return (
    <section className="card appr" id="approved" aria-label="Approved clips">
      <div className="card-h"><h2>Approved <span className="ct">{list.length}</span></h2><span className="lbl">ready on phone</span></div>
      {list.length === 0 && <p className="quiet">Approved clips land here with a download button.</p>}
      <ul>
        {list.map((c) => (
          <li key={c.id}>
            <span className="sc">{c.score_10 ?? "—"}</span>
            <span className="tx">
              <b>{c.title ?? c.job_id}</b>
              <span>{byId.get(c.streamer_id ?? "")?.display_name ?? c.channel_key} · <em className={`st-${c.state}`}>{label(c)}</em></span>
            </span>
            <button type="button" className="btn sm" onClick={() => void save(c)} disabled={busy === c.id} aria-label={`Download ${c.title ?? "clip"}`}>
              <Icon name="download" /> {busy === c.id ? "…" : "Save"}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

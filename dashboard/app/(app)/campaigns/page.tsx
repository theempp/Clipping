"use client";
import { useState } from "react";
import { useNow, useStore } from "@/lib/store";
import type { Campaign } from "@/lib/types";

const TONE: Record<Campaign["status"], string> = { active: "ok", draft: "", paused: "warn", ended: "", avoid: "bad" };

/** Campaigns from Content Rewards / Discord (campaign-scout scores them). Rights gate: only listed streamers get clipped. */
export default function Campaigns() {
  const { snap } = useStore();
  const now = useNow(60_000);
  const [show, setShow] = useState<"open" | "all">("open");
  const list = snap.campaigns.filter((c) => show === "all" || c.status === "active" || c.status === "draft")
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const days = (iso: string | null) => (iso ? Math.ceil((Date.parse(iso) - now) / 86400_000) : null);
  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}>
        <div><h1>Campaigns<br /><b>{snap.campaigns.filter((c) => c.status === "active").length} active.</b></h1>
          <p>Best score first. Paste a new brief to campaign-scout and it lands here with a pursue or avoid call.</p></div>
        <div className="seg" role="tablist" aria-label="Filter">
          <button type="button" className={show === "open" ? "on" : ""} onClick={() => setShow("open")}>Open</button>
          <button type="button" className={show === "all" ? "on" : ""} onClick={() => setShow("all")}>All</button>
        </div>
      </section>
      <div className="row3">
        {list.map((c) => {
          const d = days(c.deadline);
          return (
            <article key={c.id} className="glass camp">
              <div className="hd" style={{ margin: 0 }}>
                <span className={`pill ${TONE[c.status]}`}>{c.status}</span>
                {c.score != null && <span className="sc">{c.score.toFixed(1)}</span>}
              </div>
              <h3>{c.title}</h3>
              {c.recommendation && <p className="rec">{c.recommendation}</p>}
              <dl>
                <div><dt>CPM</dt><dd>{c.cpm_usd != null ? `$${c.cpm_usd.toFixed(2)}` : "—"}</dd></div>
                <div><dt>Cap</dt><dd>{c.cap_usd != null ? `$${Math.round(c.cap_usd)}` : "—"}</dd></div>
                <div><dt>Ends</dt><dd>{d == null ? "—" : d < 0 ? "ended" : `${d} d`}</dd></div>
              </dl>
              <div className="chips">
                {c.streamer_slugs.map((s) => <span key={s} className="chip acc">{snap.streamers.find((x) => x.slug === s)?.display_name ?? s}</span>)}
                {c.platforms.map((p) => <span key={p} className="chip">{p}</span>)}
              </div>
              {c.source_url && <a className="b" href={c.source_url} target="_blank" rel="noreferrer noopener">Open brief</a>}
            </article>
          );
        })}
      </div>
      {list.length === 0 && <p className="quiet">No campaigns yet. They come in from Discord or campaign-scout.</p>}
    </>
  );
}

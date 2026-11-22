"use client";
import { useState } from "react";
import { downloadName, mmss } from "@/lib/logic";
import { useStore } from "@/lib/store";
import type { LongformVideo, TiktokStats } from "@/lib/types";
import { Icon } from "./Icon";

export const FORMAT: Record<LongformVideo["format"], string> = {
  recap: "Story recap", topn: "Top N", explainer: "Explainer", extended: "Extended moment",
};

/** Test tags for a long video (D082): what this post is testing. */
export function tagLine(v: LongformVideo): string[] {
  return [
    FORMAT[v.format], v.pacing === "short" ? "Short-style" : "Long-style",
    v.caption_style === "A" ? "Caption A" : "Caption B", v.voice === "ai" ? "AI voice" : "Your voice",
    v.layout === "switch" ? "Layout switch" : "Stacked",
  ];
}

const FIELDS: { k: keyof TiktokStats; label: string; step?: string }[] = [
  { k: "views", label: "Views" }, { k: "for_you_views", label: "For You views" },
  { k: "follows", label: "Follows" }, { k: "avg_watch_s", label: "Avg watch (s)", step: "0.1" },
  { k: "hold_5s_pct", label: "5 s hold %", step: "0.1" }, { k: "watched_full_pct", label: "Watched full %", step: "0.1" },
  { k: "search_views_pct", label: "Search %", step: "0.1" }, { k: "qualified_views", label: "Qualified views" },
  { k: "rewards_usd", label: "Rewards $", step: "0.01" },
];

function Row({ v }: { v: LongformVideo }) {
  const { snap, mediaUrl, markTiktokPosted, addTiktokStats, setNotice } = useStore();
  const clip = snap.clips.find((c) => c.id === v.clip_id);
  const [url, setUrl] = useState("");
  const [open, setOpen] = useState(false);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const okUrl = /^https:\/\/(www\.|vm\.)?tiktok\.com\//.test(url.trim());

  const save = async () => {
    if (!clip) return;
    setBusy(true);
    const s = snap.streamers.find((x) => x.id === clip.streamer_id);
    const link = await mediaUrl(clip.storage_path, downloadName(clip, s));
    setBusy(false);
    if (!link) return;
    const a = document.createElement("a");
    a.href = link; a.rel = "noopener"; a.download = "";
    document.body.appendChild(a); a.click(); a.remove();
  };
  const submitStats = async () => {
    const stats: TiktokStats = {};
    for (const f of FIELDS) {
      const raw = vals[f.k]?.trim();
      if (raw) stats[f.k] = Number(raw);
    }
    if (!Object.keys(stats).length) return;
    setBusy(true);
    const ok = await addTiktokStats(v.id, stats);
    setBusy(false);
    if (ok) { setVals({}); setSaved(true); setOpen(false); }
  };

  return (
    <li className="tt-row">
      <div className="tt-top">
        <span className="tx">
          <b>{clip?.title ?? v.id}</b>
          <span>{mmss(v.runtime_s)} · narration {v.coverage != null ? `${Math.round(v.coverage * 100)}%` : "?"}
            {v.posted_at ? " · posted" : clip?.state === "approved" ? " · approved, not posted" : clip ? ` · ${clip.state.replace("_", " ")}` : ""}</span>
        </span>
        {v.tiktok_url
          ? <a className="lnk" href={v.tiktok_url} target="_blank" rel="noreferrer">Open <Icon name="arrow" /></a>
          : <button type="button" className="btn sm" disabled={busy || !clip || clip.state !== "approved"} onClick={() => void save()}>
              <Icon name="download" /> Save</button>}
      </div>
      <div className="chips">{tagLine(v).map((t) => <span key={t} className="chip">{t}</span>)}</div>
      {!v.posted_at && clip?.state === "approved" && (
        <div className="tt-post">
          <input type="url" inputMode="url" placeholder="Paste the TikTok link after you post" value={url}
            onChange={(e) => setUrl(e.target.value)} aria-label="TikTok link" />
          <button type="button" className="btn light sm" disabled={!okUrl || busy}
            onClick={async () => { setBusy(true); await markTiktokPosted(v.id, url.trim()); setBusy(false); }}>
            Mark posted</button>
        </div>
      )}
      {v.posted_at && (
        <div className="tt-post">
          <label className="lbl" htmlFor={`n-${v.id}`}>TikTok notice</label>
          <select id={`n-${v.id}`} value={v.notice} onChange={(e) => void setNotice(v.id, e.target.value as LongformVideo["notice"])}>
            <option value="none">None</option>
            <option value="ineligible">Not eligible for rewards</option>
            <option value="unoriginal">Unoriginal content</option>
          </select>
          <button type="button" className="btn sm" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {saved ? "Stats saved · add more" : "Enter stats"}</button>
        </div>
      )}
      {open && (
        <div className="tt-form" role="group" aria-label="TikTok Studio numbers">
          {FIELDS.map((f) => (
            <label key={f.k}><span>{f.label}</span>
              <input type="number" min="0" step={f.step ?? "1"} inputMode="decimal" value={vals[f.k] ?? ""}
                onChange={(e) => setVals((x) => ({ ...x, [f.k]: e.target.value }))} /></label>
          ))}
          <button type="button" className="btn light sm" disabled={busy} onClick={() => void submitStats()}>Save stats</button>
        </div>
      )}
    </li>
  );
}

/** Zwoclipp long videos: post by hand, then log the numbers so the test cells can be ranked (D082). */
export function TikTokPanel() {
  const { snap } = useStore();
  const list = snap.longform.filter((v) => {
    const c = snap.clips.find((x) => x.id === v.clip_id);
    return v.posted_at || (c && ["approved", "pending_review"].includes(c.state));
  }).slice(0, 12);
  const results = [...snap.results].sort((a, b) => (b.follows_per_1k ?? -1) - (a.follows_per_1k ?? -1));
  return (
    <section className="card tt" id="tiktok" aria-label="TikTok long videos">
      <div className="card-h"><h2>TikTok · Zwoclipp <span className="ct">{list.length}</span></h2><span className="lbl">over 1 min · manual post</span></div>
      {list.length === 0 && <p className="quiet">Long videos show up here once the PC builds them (needs the Grok key for narration).</p>}
      <ul>{list.map((v) => <Row key={v.id} v={v} />)}</ul>
      {results.length > 0 && (
        <div className="tt-res">
          <div className="card-h"><h2>Test results</h2><span className="lbl">best follows per 1K first</span></div>
          <div className="tt-scroll">
            <table>
              <thead><tr><th>Cell</th><th>Posts</th><th>Notices</th><th>Avg watch</th><th>5 s hold</th><th>Follows/1K</th><th>RPM</th></tr></thead>
              <tbody>
                {results.map((r) => (
                  <tr key={`${r.format}${r.pacing}${r.caption_style}${r.voice}${r.layout}`}>
                    <td>{FORMAT[r.format as LongformVideo["format"]] ?? r.format} · {r.pacing} · {r.caption_style} · {r.voice} · {r.layout}</td>
                    <td>{r.posts}</td><td className={r.notices >= 2 ? "bad" : ""}>{r.notices}</td>
                    <td>{r.avg_watch_s != null ? `${r.avg_watch_s}s` : "—"}</td>
                    <td>{r.hold_5s_pct != null ? `${r.hold_5s_pct}%` : "—"}</td>
                    <td>{r.follows_per_1k ?? "—"}</td><td>{r.rpm_usd != null ? `$${r.rpm_usd}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

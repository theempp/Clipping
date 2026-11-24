"use client";
import Link from "next/link";
import { useState, type CSSProperties } from "react";
import { Avatar } from "@/components/Avatar";
import { compact } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { fmtViewers, liveFor, rosterSections, streamerHue, streamerViews, type StreamerView } from "@/lib/view";

/** Every streamer on the roster, Lacy first (D098), then live, then A-Z. Live numbers update in place. */
type Show = "all" | "live" | "offline" | "queue";
type Sort = "roster" | "viewers" | "clips" | "name";
const SHOW: [Show, string][] = [["all", "All"], ["live", "Live"], ["offline", "Offline"], ["queue", "Has clips to review"]];
const SORT: [Sort, string][] = [["roster", "Roster order"], ["viewers", "Most watched"], ["clips", "Most clips"], ["name", "A-Z"]];

export default function Streamers() {
  const { snap } = useStore();
  const now = useNow(1000);
  const [q, setQ] = useState("");
  const [show, setShow] = useState<Show>("all");
  const [sort, setSort] = useState<Sort>("roster");
  const all = streamerViews(snap, now);
  const clipsOf = (id: string) => snap.clips.filter((c) => c.streamer_id === id).length;
  const keep = (v: StreamerView) => (!q.trim() || [v.s.display_name, v.s.slug, v.game ?? "", v.title ?? ""].some((x) => x.toLowerCase().includes(q.trim().toLowerCase())))
    && (show === "all" || (show === "live" ? v.live : show === "offline" ? !v.live : v.queued > 0));
  const order = (list: StreamerView[]) => sort === "roster" ? list : [...list].sort((a, b) => sort === "name" ? a.s.display_name.localeCompare(b.s.display_name)
    : sort === "viewers" ? (b.live ? b.viewers ?? 0 : -1) - (a.live ? a.viewers ?? 0 : -1) : clipsOf(b.s.id) - clipsOf(a.s.id));
  const views = all.filter(keep);
  const sections = rosterSections(views, !!snap.heartbeat?.status.roster);
  const core = order(sections.core), gta6 = order(sections.gta6);
  const live = all.filter((v) => v.live);
  const watching = live.reduce((a, v) => a + (v.viewers ?? 0), 0);
  const card = (v: StreamerView) => {
    const clips = snap.clips.filter((c) => c.streamer_id === v.s.id);
    const posted = clips.filter((c) => c.state === "published").length;
    return (
      <Link key={v.s.id} href={`/streamers/${v.s.slug}`} className="pc" style={{ "--h": streamerHue(v.s.slug) } as CSSProperties}>
        <div className="t">
          <span>{v.live ? `Live ${liveFor(v.since, now)}` : "Offline"}</span>
          {v.live ? <span className="livepulse">Live</span> : <span>{v.s.kick_slug && !v.s.twitch_login ? "Kick" : "Twitch"}</span>}
        </div>
        <div className="who">
          <Avatar s={v.s} live={v.live} size={72} />
          <h3>{v.s.display_name}</h3>
          <div className="s">{v.live ? v.game ?? "Live now" : v.group === "gta6_only" ? "GTA 6 only" : "Core"}</div>
        </div>
        <div className="kv">
          <div><b className="tnum">{v.live ? fmtViewers(v.viewers) || "—" : "—"}</b><span>watching</span></div>
          <div><b>{compact(clips.length)}</b><span>clips · {posted} posted</span></div>
        </div>
        <div className="f"><span className="chip">{v.queued ? `${v.queued} to review` : "queue clear"}</span><span className="chip">Open</span></div>
      </Link>
    );
  };
  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}>
        <div><h1>Streamers<br /><b>{live.length} live now.</b></h1>
          <p>Live status and viewers come straight from Twitch and Kick, so they stay right even when the PC is offline.
            {live.length > 0 && <> {compact(watching)} people watching across {live.length} stream{live.length === 1 ? "" : "s"}.</>}</p></div>
      </section>
      <div className="filters">
        <input className="in" type="search" placeholder="Search name, game or stream title" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search streamers" />
        <select className="in" value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort" style={{ flex: "0 1 170px" }}>
          {SORT.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <div className="seg" role="group" aria-label="Show">
          {SHOW.map(([k, l]) => {
            const n = all.filter((v) => k === "all" || (k === "live" ? v.live : k === "offline" ? !v.live : v.queued > 0)).length;
            return <button key={k} type="button" className={show === k ? "on" : ""} aria-pressed={show === k} onClick={() => setShow(k)}>{l} <span style={{ opacity: 0.6 }}>{n}</span></button>;
          })}
        </div>
      </div>
      <div className="sec first"><h2>Core roster</h2><span>{core.filter((v) => v.live).length} live</span></div>
      <div className="slist">{core.map(card)}</div>
      {core.length === 0 && <p className="quiet">{all.length ? "No streamers match. Clear the search or pick All." : "No streamers yet. The worker adds them from its channel config."}</p>}
      {gta6.length > 0 && <>
        <div className="sec"><h2>GTA 6 only</h2><span>{gta6.filter((v) => v.live).length} live</span></div>
        <div className="slist">{gta6.map(card)}</div>
      </>}
    </>
  );
}

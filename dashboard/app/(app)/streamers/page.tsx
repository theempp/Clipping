"use client";
import Link from "next/link";
import type { CSSProperties } from "react";
import { Avatar } from "@/components/Avatar";
import { compact } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { fmtViewers, liveFor, rosterSections, streamerHue, streamerViews, type StreamerView } from "@/lib/view";

/** Every streamer on the roster, Lacy first (D098), then live, then A-Z. Live numbers update in place. */
export default function Streamers() {
  const { snap } = useStore();
  const now = useNow(1000);
  const views = streamerViews(snap, now);
  const { core, gta6 } = rosterSections(views, !!snap.heartbeat?.status.roster);
  const live = views.filter((v) => v.live);
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
          <p>Live status and viewers come straight from Twitch and Kick, so they stay right even while the PC sleeps.</p></div>
      </section>
      <div className="sec first"><h2>Core roster</h2><span>{core.filter((v) => v.live).length} live</span></div>
      <div className="slist">{core.map(card)}</div>
      {core.length === 0 && <p className="quiet">No streamers yet. The worker adds them from its channel config.</p>}
      {gta6.length > 0 && <>
        <div className="sec"><h2>GTA 6 only</h2><span>{gta6.filter((v) => v.live).length} live</span></div>
        <div className="slist">{gta6.map(card)}</div>
      </>}
    </>
  );
}

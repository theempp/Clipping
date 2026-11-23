"use client";
import Link from "next/link";
import type { CSSProperties } from "react";
import { Avatar } from "@/components/Avatar";
import { Spark } from "@/components/Charts";
import { ClipCard } from "@/components/ClipCard";
import { Countdown } from "@/components/Countdown";
import { OwnChannels } from "@/components/OwnChannels";
import { AgentTicker } from "@/components/Pipeline";
import { WakeToggle } from "@/components/WakeToggle";
import { compact, rankQueue } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { fmtViewers, liveFor, series, streamerHue, streamerViews } from "@/lib/view";

const GOAL = 8; // clips a day per streamer (concept C)

function greet(now: number) {
  const h = new Date(now).getHours();
  return h < 5 ? "Late night" : h < 12 ? "Morning" : h < 18 ? "Afternoon" : "Evening";
}

/** Overview: who is live, what is waiting on Zo, and the numbers moving right now. */
export default function Overview() {
  const { snap } = useStore();
  const now = useNow(1000);
  const views = streamerViews(snap, now).filter((v) => v.inRoster || !snap.heartbeat?.status.roster);
  const queue = rankQueue(snap.clips);
  const live = views.filter((v) => v.live);
  const byId = new Map(snap.streamers.map((s) => [s.id, s]));
  const top = views[0];
  const lacyQ = top ? queue.filter((c) => c.streamer_id === top.s.id).length : 0;
  const watching = live.reduce((a, v) => a + (v.viewers ?? 0), 0);
  const ytViews = series(snap, "youtube:own", "views").map((p) => p.value);
  const ttViews = series(snap, "tiktok:own", "views").map((p) => p.value);
  const day = (a: number[]) => (a.length >= 2 ? a[a.length - 1] - a[a.length - 2] : null);
  const views24 = [day(ytViews), day(ttViews)].filter((x): x is number => x != null);
  const viewsToday = views24.length ? views24.reduce((a, b) => a + b, 0) : null;
  const sparkViews = ytViews.slice(-8).map((v, i) => v + (ttViews.slice(-8)[i] ?? 0));
  const lacyViewers = series(snap, "twitch:lacy", "viewers").map((p) => p.value);
  const today = (id: string) => snap.clips.filter((c) => c.streamer_id === id && now - Date.parse(c.created_at) < 86400_000);

  return (
    <>
      <section className="hero">
        <div>
          <h1>{greet(now)}, zo.<br /><b>{live.length} streamer{live.length === 1 ? "" : "s"} live.</b></h1>
          <p>{queue.length ? `${queue.length} clip${queue.length === 1 ? " is" : "s are"} waiting on you.` : "Nothing is waiting on you."}
            {top?.live ? ` ${top.s.display_name} is live${top.viewers ? ` with ${fmtViewers(top.viewers)} watching` : ""}${top.game ? `, playing ${top.game}` : ""}.` : ""}</p>
        </div>
        <WakeToggle />
      </section>

      <div className="row3" style={{ marginTop: 34 }}>
        <div className="glass stat">
          <span className="lab">Views · 24h {viewsToday != null && <em>YouTube + TikTok</em>}</span>
          <span className="sk"><Spark data={sparkViews} /></span>
          <div className="num tnum">{compact(viewsToday)}</div>
        </div>
        <Link href="/review" className="glass stat hot">
          <span className="lab">Waiting on you {lacyQ > 0 && <em>{lacyQ} {top?.s.display_name}</em>}</span>
          <span className="sk"><Spark data={[2, 4, 3, 5, 7, 6, 9, queue.length + 1]} color="#fff" /></span>
          <div className="num">{queue.length}<small>clips</small></div>
        </Link>
        <div className="glass stat">
          <span className="lab">Watching now <em className="livepulse" style={{ fontSize: 12 }}>live</em></span>
          <span className="sk"><Spark data={lacyViewers.length > 1 ? lacyViewers : [3, 4, 3, 5]} color="var(--c2)" /></span>
          <div className="num tnum">{compact(watching)}</div>
        </div>
      </div>

      <div className="sec"><h2>Agents right now</h2><span className="livepulse">live</span></div>
      <AgentTicker />

      <div className="sec"><h2>Streamers</h2><span>goal = {GOAL} clips a day each</span></div>
      <div className="pcards">
        {views.slice(0, 6).map((v) => {
          const t = today(v.s.id);
          const n = t.length;
          const rendering = t.filter((c) => c.state === "qa_passed").length;
          const sched = t.filter((c) => c.state === "scheduled").length;
          return (
            <Link key={v.s.id} href={`/streamers/${v.s.slug}`} className="pc" style={{ "--h": streamerHue(v.s.slug) } as CSSProperties}>
              <div className="t">
                <span>{v.live ? `Live ${liveFor(v.since, now)}` : "Offline"}</span>
                {v.live ? <span className="livepulse">{v.viewers != null ? fmtViewers(v.viewers) : "Live"}</span> : <span>{v.group === "gta6_only" ? "GTA 6 only" : ""}</span>}
              </div>
              <div className="who">
                <Avatar s={v.s} live={v.live} size={56} />
                <h3>{v.s.display_name}</h3>
                <div className="s">{v.game ?? (v.s.slug === "lacy" ? "GTA 6 priority" : v.group === "gta6_only" ? "GTA 6 only" : "Core")}</div>
              </div>
              <div>
                <div className="pb"><span>Clips today</span><span className="tnum">{n} / {GOAL}</span></div>
                <div className="bar"><i style={{ width: `${Math.min(100, (n / GOAL) * 100)}%` }} /></div>
              </div>
              <div className="f">
                <span className="chip">{v.queued ? `${v.queued} to review` : "queue clear"}</span>
                <span className="chip">{rendering ? `${rendering} rendering` : sched ? `${sched} scheduled` : v.live ? "watching" : "idle"}</span>
              </div>
            </Link>
          );
        })}
        {views.length === 0 && <p className="quiet">No streamers yet. The worker adds them from its channel config.</p>}
      </div>

      <div className="row2" style={{ marginTop: 40 }}>
        <div>
          <div className="sec first"><h2>Review</h2><Link href="/review" className="r">approve, revise or deny · open queue</Link></div>
          {(() => {
            const stuck = snap.clips.filter((c) => c.state === "revise" && c.revise_failed);
            return stuck.length > 0 && (
              <p className="fixing bad" role="alert" style={{ marginBottom: 12 }}>
                {stuck.length === 1 ? "A revision" : `${stuck.length} revisions`} failed QA on the PC. <Link href={`/library?clip=${stuck[0].id}`}>See why</Link>
              </p>
            );
          })()}
          <div className="qgrid">
            {queue.slice(0, 4).map((c) => (
              <ClipCard key={c.id} clip={c} streamer={c.streamer_id ? byId.get(c.streamer_id) : undefined} />
            ))}
          </div>
          {queue.length === 0 && <p className="quiet">Queue clear. New clips land here the moment the PC finishes render and QA.</p>}
        </div>
        <Countdown />
      </div>

      <div className="sec"><h2>Your channels</h2><Link href="/analytics" className="r">live from YouTube and X · TikTok by hand</Link></div>
      <OwnChannels />
    </>
  );
}

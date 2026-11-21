"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { PC_NAME } from "@/lib/env";
import { ago, pcState, rankQueue } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { fmtViewers, monthSpend, rosterSections, streamerViews, type StreamerView } from "@/lib/view";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { UndoToast } from "./UndoToast";
import { WakeToggle } from "./WakeToggle";

export function Shell({ children }: { children: ReactNode }) {
  const { snap, demo, error, ready, signOut } = useStore();
  const now = useNow(5000);
  const path = usePathname();
  const views = streamerViews(snap, now);
  const sections = rosterSections(views, !!snap.heartbeat?.status.roster);
  const queue = rankQueue(snap.clips);
  const approved = snap.clips.filter((c) => c.state === "approved").length;
  const games = snap.heartbeat?.status.games ?? {};
  const awake = snap.control.awake;
  const st = pcState(snap.heartbeat, awake, now);
  const gpu = snap.heartbeat?.status.gpu;
  const spend = monthSpend(snap);

  const row = (v: StreamerView) => {
    const on = path === `/live/${v.s.slug}`;
    const game = v.live && v.key ? games[v.key] : undefined;
    return (
      <Link key={v.s.id} href={`/live/${v.s.slug}`} title={game ? `${v.s.display_name} · ${game}` : v.s.display_name}
        className={`sr${v.live ? " lv" : ""}${on ? " on" : ""}`} aria-current={on ? "page" : undefined}>
        <Avatar s={v.s} live={v.live} size={34} />
        <span className="sr-t">
          <b>{v.s.display_name}</b>
          <span>{v.live
            ? <>{fmtViewers(v.viewers) ? `${fmtViewers(v.viewers)} watching` : "live now"}</>
            : v.queued ? `${v.queued} in queue` : "offline"}</span>
        </span>
        {v.live
          ? <span className="tag live"><span className="eq" aria-hidden="true"><i /><i /><i /></span>LIVE</span>
          : <span className="hs" aria-hidden="true">{v.heat.slice(-6).map((h, i) => <i key={i} className={h ? `h${h}` : ""} />)}</span>}
      </Link>
    );
  };

  if (error === "not-owner") {
    return (
      <main className="gate">
        <div className="gate-card">
          <h1>Not allowed</h1>
          <p>This account is signed in but is not the owner. Clipp is private.</p>
          <button className="btn light" onClick={() => void signOut()}>Sign out</button>
        </div>
      </main>
    );
  }

  const liveCore = sections.core.filter((v) => v.live).length;
  const liveGta = sections.gta6.filter((v) => v.live).length;

  return (
    <div className={`app ${awake ? "awake" : "asleep"}`}>
      <nav className="rail" aria-label="Main">
        <div className="brand">
          <span className="mk"><Icon name="bolt" size={18} /></span>
          <b>Clipp</b>
          <small>{demo ? "demo" : "v1"}</small>
        </div>

        <div className="nav">
          <Link href="/" className={path === "/" ? "on" : ""} aria-current={path === "/" ? "page" : undefined}>
            <Icon name="queue" /> <span>Review queue</span> <em>{queue.length}</em>
          </Link>
          <Link href="/#approved">
            <Icon name="download" /> <span>Approved</span> <em>{approved}</em>
          </Link>
        </div>

        <h6><span>Streamers</span>{liveCore > 0 && <em>{liveCore} live</em>}</h6>
        <div className="srs">
          {sections.core.map(row)}
          {views.length === 0 && <p className="quiet">No streamers yet. The worker adds them from its channel config.</p>}
        </div>
        {sections.gta6.length > 0 && <>
          <h6><span>GTA 6 only</span>{liveGta > 0 && <em>{liveGta} live</em>}</h6>
          <div className="srs">{sections.gta6.map(row)}</div>
        </>}

        <div className="rail-end">
          <div className={`mach pc-${st}`}>
            <div className="r1">
              <Icon name="chip" />
              <b>{PC_NAME}</b>
              <span className="state">{st === "offline" ? "offline" : st === "watching" ? "watching" : st}</span>
            </div>
            <div className="gb" aria-hidden="true"><i style={{ width: `${st === "offline" ? 0 : gpu?.util ?? 6}%` }} /></div>
            <div className="r2">
              <span>{gpu?.name ?? "GPU"}{st !== "offline" && gpu?.util != null ? ` · ${gpu.util}%` : ""}</span>
              <span>{st === "offline"
                ? snap.heartbeat ? ago(snap.heartbeat.seen_at, now) : "never seen"
                : gpu?.mem_used_gb != null ? `${gpu.mem_used_gb}/${gpu.mem_total_gb} GB` : "online"}</span>
            </div>
          </div>
          <div className="rail-foot">
            <span>${spend.total.toFixed(0)} spent this month</span>
            {!demo && <button type="button" onClick={() => void signOut()} aria-label="Sign out"><Icon name="out" /></button>}
          </div>
        </div>
      </nav>

      <header className="mhead">
        <div className="mrow">
          <Link href="/" className="mbrand"><span className="mk"><Icon name="bolt" size={16} /></span>Clipp{demo && <small>demo</small>}</Link>
          <Link href="/" className="mq"><Icon name="queue" /> {queue.length}</Link>
          <WakeToggle compact />
        </div>
        <div className="strip" role="list">
          {[...sections.core, ...sections.gta6].map((v) => (
            <Link key={v.s.id} href={`/live/${v.s.slug}`} role="listitem" aria-label={`${v.s.display_name}${v.live ? " (live)" : ""}`}
              className={`${path === `/live/${v.s.slug}` ? "on" : ""}${v.live ? " lv" : ""}`}>
              <Avatar s={v.s} live={v.live} size={42} />
              <span>{v.s.display_name.split(" ")[0]}</span>
            </Link>
          ))}
        </div>
      </header>

      <main className="main">
        {demo && <div className="demo-tag">Demo data. Nothing here is saved or posted.</div>}
        {error && error !== "not-owner" && <div className="err" role="alert">{error}</div>}
        {!ready ? <div className="loading">Loading…</div> : children}
      </main>
      <UndoToast />
    </div>
  );
}

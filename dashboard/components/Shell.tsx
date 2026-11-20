"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { PC_NAME } from "@/lib/env";
import { ago, pcState, rankQueue } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { fmtViewers, monthSpend, streamerViews } from "@/lib/view";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { UndoToast } from "./UndoToast";
import { WakeToggle } from "./WakeToggle";

export function Shell({ children }: { children: ReactNode }) {
  const { snap, demo, error, ready, signOut } = useStore();
  const now = useNow(5000);
  const path = usePathname();
  const views = streamerViews(snap, now);
  const queue = rankQueue(snap.clips);
  const approved = snap.clips.filter((c) => c.state === "approved").length;
  const liveN = views.filter((v) => v.live).length;
  const awake = snap.control.awake;
  const st = pcState(snap.heartbeat, awake, now);
  const gpu = snap.heartbeat?.status.gpu;
  const spend = monthSpend(snap);

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

  return (
    <div className={`app ${awake ? "awake" : "asleep"}`}>
      <nav className="NV" aria-label="Main">
        <div className="br">
          <span className="mk"><Icon name="bolt" size={18} /></span>
          <b>Clipp</b>
          <small>{demo ? "demo" : "v1"}</small>
        </div>
        <h6>Review</h6>
        <Link href="/" className={`ni ${path === "/" ? "on" : ""}`}>
          <Icon name="queue" /> Queue <span className="ct">{queue.length}</span>
        </Link>
        <Link href="/#approved" className="ni">
          <Icon name="download" /> Approved <span className="ct">{approved}</span>
        </Link>
        <h6>Streamers <em>{liveN} live</em></h6>
        <div className="srs">
          {views.map((v) => {
            const on = path === `/live/${v.s.slug}`;
            return (
              <Link key={v.s.id} href={`/live/${v.s.slug}`}
                className={`sr ${v.live ? "lv" : ""} ${on ? "on" : ""}`} aria-current={on ? "page" : undefined}>
                <Avatar s={v.s} live={v.live} />
                <b>{v.s.display_name}</b>
                {v.live
                  ? <span className="tg"><span className="eq"><i /><i /><i /></span>LIVE</span>
                  : <span className="tg off">OFF</span>}
                <span className="meta">
                  <span className="hs">{v.heat.map((h, i) => <i key={i} className={h ? `h${h}` : ""} />)}</span>
                  {v.live ? fmtViewers(v.viewers) : v.queued ? `${v.queued} queued` : "offline"}
                </span>
              </Link>
            );
          })}
          {views.length === 0 && <p className="empty-s">No streamers yet. The worker adds them from its channel config.</p>}
        </div>
        <h6>Machine</h6>
        <div className="mc">
          <div className="r1"><Icon name="chip" /> {PC_NAME}
            <span className={`pc-${st}`}>{st === "offline" ? "off" : gpu?.util != null ? `${gpu.util}%` : st}</span>
          </div>
          <div className="gb"><i style={{ width: `${st === "offline" ? 2 : gpu?.util ?? 8}%` }} /></div>
          <div className="r2">
            <span>{gpu?.name ?? "GPU"}</span>
            <span>{st === "offline"
              ? snap.heartbeat ? ago(snap.heartbeat.seen_at, now) : "never seen"
              : gpu?.mem_used_gb != null ? `${gpu.mem_used_gb} / ${gpu.mem_total_gb} GB` : "online"}</span>
          </div>
        </div>
        <div className="r-foot">
          <span>${spend.total.toFixed(0)} this month</span>
          {!demo && <button type="button" onClick={() => void signOut()}><Icon name="out" /> Sign out</button>}
        </div>
        <Link href="/" className="go">
          {queue.length ? `Review ${queue.length} ready` : "Queue is clear"}
          <span className="ar"><Icon name="arrow" /></span>
        </Link>
      </nav>

      <header className="mhead">
        <div className="mrow">
          <Link href="/" className="mbrand"><span className="mk"><Icon name="bolt" size={16} /></span>Clipp{demo && <small className="mdemo">demo</small>}</Link>
          <WakeToggle compact />
        </div>
        <div className="strip" role="list">
          {views.map((v) => (
            <Link key={v.s.id} href={`/live/${v.s.slug}`} role="listitem" aria-label={v.s.display_name}
              className={path === `/live/${v.s.slug}` ? "on" : ""}>
              <Avatar s={v.s} live={v.live} size={40} />
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

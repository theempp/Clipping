"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Avatar } from "@/components/Avatar";
import { Countdown } from "@/components/Countdown";
import { Icon } from "@/components/Icon";
import { LiveChat, LiveStage, useHost, type LiveStatus } from "@/components/LiveStage";
import { PipelineTiles } from "@/components/Pipeline";
import { WakeToggle } from "@/components/WakeToggle";
import { mmss, pcState, rankQueue, streamerKeys } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { fmtViewers, liveClock, livePlayer, monthSpend, streamerViews } from "@/lib/view";

const STATE_LABEL: Record<string, string> = {
  pending_review: "in review", approved: "approved", revise: "revising", rejected: "denied",
  scheduled: "posting", published: "posted", failed: "post failed", qa_passed: "uploading",
};

/** Streamer page: the live stream itself, with what Clipp is doing on it around the player. */
export default function LivePage() {
  const { slug } = useParams<{ slug: string }>();
  const { snap } = useStore();
  const now = useNow(1000);
  const host = useHost();
  const [view, setView] = useState<"stream" | "clip">("stream");
  const [side, setSide] = useState<"info" | "chat">("info");

  const v = streamerViews(snap, now).find((x) => x.s.slug === slug);
  const keys = useMemo(() => (v ? streamerKeys(v.s) : []), [v]);
  const clips = useMemo(
    () => snap.clips.filter((c) => c.streamer_id === v?.s.id || keys.includes(c.channel_key))
      .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [snap.clips, v, keys],
  );

  if (!v) {
    return (
      <div className="stp missing">
        <section className="card">
          <h2>No streamer called “{slug}”.</h2>
          <Link href="/" className="btn light">Back to queue</Link>
        </section>
      </div>
    );
  }

  const queue = rankQueue(clips);
  const cands = snap.candidates.filter((c) => keys.includes(c.channel_key));
  const spend = monthSpend(snap);
  const pcUp = pcState(snap.heartbeat, snap.control.awake, now) !== "offline";
  const status: LiveStatus = v.live ? "live" : pcUp ? "offline" : "unknown";
  const player = livePlayer(v.s, v.live ? v.key : null, host);
  const platform = (v.live ? v.key?.split(":")[0] : player?.platform) ?? (v.s.twitch_login ? "twitch" : "kick");
  const game = v.live && v.key ? snap.heartbeat?.status.games?.[v.key] : undefined;

  const today = clips.filter((c) => now - Date.parse(c.created_at) < 86400_000);
  const approvedN = today.filter((c) => ["approved", "scheduled", "published"].includes(c.state)).length;
  const last = cands.slice(-48);
  const maxScore = Math.max(3, ...last.map((c) => c.score));
  const peak = last.reduce<typeof last[number] | null>((m, c) => (!m || c.score > m.score ? c : m), null);
  const line = last.map((c, i) => `${((i / Math.max(1, last.length - 1)) * 300).toFixed(1)},${(78 - (c.score / maxScore) * 70).toFixed(1)}`).join(" ");
  const bars = cands.slice(-72);
  const kept = cands.filter((c) => c.outcome === "kept").length;
  const hasChat = !!player?.chat;

  return (
    <div className="stp">
      <header className="ptop stp-top">
        <Link href="/" className="iconbtn" aria-label="Back to queue"><Icon name="back" /></Link>
        <Avatar s={v.s} live={v.live} size={46} />
        <div className="who">
          <h1>{v.s.display_name}</h1>
          <div className="meta">
            {status === "live"
              ? <span className="chip live"><i className="dot" />LIVE</span>
              : status === "offline"
                ? <span className="chip">Offline</span>
                : <span className="chip warn" title="The PC is not reporting, so live status is unknown">Status unknown</span>}
            <span className="m"><Icon name="live" />{platform === "kick" ? "Kick" : "Twitch"}</span>
            {v.live && v.since && <span className="m"><Icon name="clock" />{liveClock(v.since, now)}</span>}
            {v.live && v.viewers != null && <span className="m"><Icon name="users" />{fmtViewers(v.viewers)}</span>}
            {game && <span className="m game">{game}</span>}
            {v.group === "gta6_only" && <span className="m">GTA 6 only</span>}
          </div>
        </div>
        <WakeToggle />
      </header>

      <section className="card stage" aria-label="Stream">
        <div className="stage-bar">
          <div className="seg" role="tablist" aria-label="Stage view">
            <button type="button" role="tab" aria-selected={view === "stream"} className={view === "stream" ? "on" : ""} onClick={() => setView("stream")}>
              <Icon name="live" /> Stream
            </button>
            <button type="button" role="tab" aria-selected={view === "clip"} className={view === "clip" ? "on" : ""} onClick={() => setView("clip")}>
              <Icon name="film" /> Latest clip
            </button>
          </div>
          <span className="sb-note">
            {view === "clip" ? (clips[0]?.title ?? "No clips yet")
              : status === "live" ? "Muted autoplay · unmute in the player"
              : status === "unknown" ? "PC offline · showing the channel player"
              : "Not live right now"}
          </span>
          {player && (
            <a className="btn sm" href={player.watch} target="_blank" rel="noreferrer noopener">
              <Icon name="external" /> <span><span className="hide-s">Open on </span>{player.platform === "kick" ? "Kick" : "Twitch"}</span>
            </a>
          )}
        </div>
        <LiveStage s={v.s} status={status} liveKey={v.live ? v.key : null} view={view} clip={clips[0] ?? null} />
      </section>

      <aside className="side" aria-label="Streamer details">
        {hasChat && (
          <div className="seg full" role="tablist" aria-label="Side panel">
            <button type="button" role="tab" aria-selected={side === "info"} className={side === "info" ? "on" : ""} onClick={() => setSide("info")}><Icon name="grid" /> Overview</button>
            <button type="button" role="tab" aria-selected={side === "chat"} className={side === "chat" ? "on" : ""} onClick={() => setSide("chat")}><Icon name="chat" /> Chat</button>
          </div>
        )}
        {side === "chat" && hasChat ? (
          <section className="card chatc"><LiveChat s={v.s} liveKey={v.live ? v.key : null} /></section>
        ) : <>
          <section className="card kpis" aria-label="Today">
            <div><b>{fmtViewers(v.viewers) || "—"}</b><span>viewers</span></div>
            <div><b>{today.length}</b><span>clips today</span></div>
            <div><b>{approvedN}</b><span>approved</span></div>
            <div><b>${spend.total.toFixed(0)}</b><span>spend · month</span></div>
          </section>
          <section className="card lq" aria-label="Review queue">
            <div className="card-h"><h2>In review <span className="ct">{queue.length}</span></h2>{queue.length > 0 && <Link href="/" className="lnk">Open queue <Icon name="arrow" /></Link>}</div>
            {queue.length === 0 && <p className="quiet">Nothing from {v.s.display_name} waiting.</p>}
            <ul>
              {queue.slice(0, 3).map((c) => (
                <li key={c.id}>
                  <Link href="/">
                    <span className="tx"><b>{c.title ?? c.job_id}</b><span>{c.duration_s ? mmss(c.duration_s) : "—"}</span></span>
                    <span className="sc">{c.score_10 ?? "—"}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </>}
      </aside>

      <section className="card activity" aria-label="Stream activity">
        <div className="card-h">
          <h2>Chat heat</h2>
          <div className="stats">
            <span>Moments <b>{cands.length}</b></span>
            <span>Kept <b>{kept}</b></span>
            <span>Peak <b>{peak ? `${peak.score.toFixed(1)}×` : "—"}</b></span>
          </div>
        </div>
        {last.length > 1 ? (
          <svg viewBox="0 0 300 84" preserveAspectRatio="none" className="spark" role="img" aria-label="Detector score over time">
            <defs>
              <linearGradient id="g-heat-ln" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="var(--cyan)" /><stop offset=".55" stopColor="var(--lime)" /><stop offset="1" stopColor="var(--orange)" />
              </linearGradient>
              <linearGradient id="g-heat-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="var(--lime)" stopOpacity=".32" /><stop offset="1" stopColor="var(--cyan)" stopOpacity="0" />
              </linearGradient>
            </defs>
            <polyline points={`0,84 ${line} 300,84`} className="fill" fill="url(#g-heat-fill)" />
            <polyline points={line} className="ln" stroke="url(#g-heat-ln)" vectorEffect="non-scaling-stroke" />
          </svg>
        ) : <p className="quiet">No detector data yet for this stream.</p>}
        {bars.length > 0 && <>
          <div className="bars" role="img" aria-label="Detector score per moment">
            {bars.map((c, i) => (
              <i key={i} title={`${c.score.toFixed(1)}× · ${c.outcome}`} className={c.outcome === "kept" ? "kept" : ""}
                style={{ height: `${Math.max(8, (c.score / maxScore) * 100)}%`, animationDelay: `${i * 12}ms` }} />
            ))}
          </div>
          <div className="legend"><span><i className="k-kept" />kept as clip</span><span><i className="k-mom" />scored moment</span>
            {peak && <span className="pk">peak at {new Date(peak.moment_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>}</div>
        </>}
      </section>

      <Countdown variant="dial" />
      <PipelineTiles compact />

      <section className="card clips" aria-label="Recent clips">
        <div className="card-h"><h2>Recent clips <span className="ct">{clips.length}</span></h2></div>
        {clips.length === 0 && <p className="quiet">Clips from {v.s.display_name} show up here.</p>}
        <ul>
          {clips.slice(0, 8).map((c) => (
            <li key={c.id}>
              <span className="sc">{c.score_10 ?? "—"}</span>
              <span className="tx"><b>{c.title ?? c.job_id}</b><span>{c.duration_s ? `${mmss(c.duration_s)} · ` : ""}{new Date(c.created_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span></span>
              {c.state === "pending_review"
                ? <Link href="/" className="btn sm light">Review</Link>
                : <span className={`st st-${c.state}`}>{STATE_LABEL[c.state] ?? c.state}</span>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

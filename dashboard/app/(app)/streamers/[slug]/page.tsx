"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState, type CSSProperties } from "react";
import { Avatar } from "@/components/Avatar";
import { BrainWeights } from "@/components/Brain";
import { LineChart } from "@/components/Charts";
import { ClipVideo } from "@/components/ClipCard";
import { Icon } from "@/components/Icon";
import { LiveChat, LiveStage, useHost, type LiveStatus } from "@/components/LiveStage";
import { compact, pcState, rankQueue, streamerKeys } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { fmtViewers, liveFor, livePlayer, series, streamerHue, streamerViews } from "@/lib/view";

const STATE_LABEL: Record<string, string> = {
  pending_review: "in review", approved: "approved", revise: "revising", rejected: "denied",
  scheduled: "posting", published: "posted", failed: "post failed", qa_passed: "uploading",
};
type Tab = "clips" | "reels" | "brain";

function Tile({ c }: { c: Clip }) {
  return (
    <figure className="clip">
      <Link href={c.state === "pending_review" ? `/review?clip=${c.id}` : `/library?clip=${c.id}`} aria-label={c.title ?? c.job_id}>
        <ClipVideo clip={c} sound={false}><span className="sc">{c.score_10 ?? "—"}</span></ClipVideo>
      </Link>
      <figcaption><b>{c.title ?? c.job_id}</b>
        <small><span className={`st-${c.state}`}>{STATE_LABEL[c.state] ?? c.state}</span> · {new Date(c.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}</small>
      </figcaption>
    </figure>
  );
}

/** One streamer: the live stream itself, their clips and reels, the brain, and their numbers. */
export default function StreamerPage() {
  const { slug } = useParams<{ slug: string }>();
  const { snap } = useStore();
  const now = useNow(1000);
  const host = useHost();
  const [tab, setTab] = useState<Tab>("clips");
  const [side, setSide] = useState<"stats" | "chat">("stats");
  const [stage, setStage] = useState<"stream" | "clip">("stream");

  const v = streamerViews(snap, now).find((x) => x.s.slug === slug);
  const keys = useMemo(() => (v ? streamerKeys(v.s) : []), [v]);
  const clips = useMemo(
    () => snap.clips.filter((c) => c.streamer_id === v?.s.id || keys.includes(c.channel_key))
      .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [snap.clips, v, keys],
  );

  if (!v) {
    return (
      <section className="glass">
        <h2 style={{ marginTop: 0 }}>No streamer called “{slug}”.</h2>
        <Link href="/streamers" className="b ok">All streamers</Link>
      </section>
    );
  }

  const reels = clips.filter((c) => c.state === "published" || c.state === "scheduled");
  const queue = rankQueue(clips);
  const cands = snap.candidates.filter((c) => keys.includes(c.channel_key));
  const pcUp = pcState(snap.heartbeat, now) !== "offline";
  const status: LiveStatus = v.live ? "live" : pcUp || snap.live.length ? "offline" : "unknown";
  const player = livePlayer(v.s, v.live ? v.key : null, host);
  const platform = (v.live ? v.key?.split(":")[0] : player?.platform) ?? (v.s.twitch_login ? "twitch" : "kick");
  const reviewed = clips.filter((c) => ["approved", "scheduled", "published", "rejected"].includes(c.state));
  const okRate = reviewed.length ? Math.round((reviewed.filter((c) => c.state !== "rejected").length / reviewed.length) * 100) : null;
  const vh = series(snap, v.key ?? "", "viewers");
  const bars = cands.slice(-72);
  const maxScore = Math.max(3, ...bars.map((c) => c.score));
  const kept = cands.filter((c) => c.outcome === "kept").length;
  const shown = tab === "reels" ? reels : clips;

  return (
    <>
      <section className="shero" style={{ "--h": streamerHue(v.s.slug) } as CSSProperties}>
        <div className="banner">
          <Link href="/streamers" className="icb back" aria-label="All streamers"><Icon name="back" size={18} /></Link>
          {player && <div className="act"><a className="b" href={player.watch} target="_blank" rel="noreferrer noopener"><Icon name="external" size={14} /> {platform === "kick" ? "Kick" : "Twitch"}</a></div>}
        </div>
        <div className="sbody">
          <Avatar s={v.s} live={v.live} size={104} />
          <h2>{v.s.display_name}</h2>
          <div className="meta">
            {v.live ? <span className="livepulse">Live {liveFor(v.since, now)}</span> : <span>{status === "unknown" ? "Status unknown" : "Offline"}</span>}
            {v.live && v.viewers != null && <span className="tnum"><Icon name="users" /> {fmtViewers(v.viewers)} watching</span>}
            {v.game && <span>{v.game}</span>}
            {v.s.slug === "lacy" && <span>GTA 6 priority</span>}
            {v.group === "gta6_only" && <span>GTA 6 only</span>}
          </div>
          {v.title && <p className="quiet" style={{ maxWidth: "60ch" }}>{v.title}</p>}
          <div className="tagrow" role="tablist" aria-label="Streamer sections">
            {(["clips", "reels", "brain"] as Tab[]).map((t) => (
              <button key={t} type="button" role="tab" aria-selected={tab === t} className={`chip${tab === t ? " on" : ""}`} onClick={() => setTab(t)}>
                {t === "clips" ? `Clips · ${clips.length}` : t === "reels" ? `Reels · ${reels.length}` : "Brain"}
              </button>
            ))}
            <span className="chip">{okRate == null ? "no reviews yet" : `${okRate}% approved`}</span>
            <span className="chip">{queue.length} in review</span>
          </div>
          {tab === "brain"
            ? <div style={{ width: "min(100%, 520px)", textAlign: "left" }}><BrainWeights s={v.s} />
                <Link href="/settings#brain" className="b" style={{ marginTop: 10 }}>Tune in Settings</Link></div>
            : shown.length
              ? <div className="strip">{shown.slice(0, 20).map((c) => <Tile key={c.id} c={c} />)}</div>
              : <p className="quiet">{tab === "reels" ? "Nothing posted yet." : `Clips from ${v.s.display_name} show up here.`}</p>}
        </div>
      </section>

      <div className="row2" style={{ marginTop: 18 }}>
        <section className="glass" aria-label="Stream">
          <div className="hd">
            <div className="seg" role="tablist" aria-label="Stage view">
              <button type="button" role="tab" aria-selected={stage === "stream"} className={stage === "stream" ? "on" : ""} onClick={() => setStage("stream")}>Stream</button>
              <button type="button" role="tab" aria-selected={stage === "clip"} className={stage === "clip" ? "on" : ""} onClick={() => setStage("clip")}>Latest clip</button>
            </div>
            <span className="r">{stage === "clip" ? clips[0]?.title ?? "No clips yet" : v.live ? "Muted autoplay · unmute in the player" : "Not live right now"}</span>
          </div>
          <LiveStage s={v.s} status={status} liveKey={v.live ? v.key : null} view={stage} clip={clips[0] ?? null} />
        </section>
        <aside className="glass" aria-label="Streamer details">
          {player?.chat && (
            <div className="seg" role="tablist" aria-label="Side panel" style={{ marginBottom: 14 }}>
              <button type="button" role="tab" aria-selected={side === "stats"} className={side === "stats" ? "on" : ""} onClick={() => setSide("stats")}>Numbers</button>
              <button type="button" role="tab" aria-selected={side === "chat"} className={side === "chat" ? "on" : ""} onClick={() => setSide("chat")}>Chat</button>
            </div>
          )}
          {side === "chat" && player?.chat ? <LiveChat s={v.s} liveKey={v.live ? v.key : null} /> : (
            <div className="kv">
              <div><b className="tnum">{v.live ? fmtViewers(v.viewers) || "—" : "—"}</b><span>watching now</span></div>
              <div><b>{clips.filter((c) => now - Date.parse(c.created_at) < 86400_000).length}</b><span>clips today</span></div>
              <div><b>{reels.length}</b><span>posted</span></div>
              <div><b>{okRate == null ? "—" : `${okRate}%`}</b><span>approved</span></div>
              <div><b>{compact(cands.length)}</b><span>moments scored</span></div>
              <div><b>{kept}</b><span>kept as clips</span></div>
            </div>
          )}
        </aside>
      </div>

      <div className="row2e" style={{ marginTop: 18 }}>
        <section className="glass" aria-label="Viewers">
          <div className="hd"><h3>{v.s.display_name} viewers</h3><span className="r">this stream · live from {platform === "kick" ? "Kick" : "Twitch"}</span></div>
          <LineChart series={[{ name: "viewers", color: "var(--acc)", values: vh.map((p) => p.value) }]}
            labels={vh.map((p, i) => (i % 3 === 0 ? new Date(p.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : ""))}
            height={220} fmt={(x) => compact(x)} empty={v.live ? "Collecting viewer history…" : "Not live"} />
        </section>
        <section className="glass" aria-label="Chat heat">
          <div className="hd"><h3>Chat heat</h3><span className="r">{cands.length} moments · {kept} kept</span></div>
          {bars.length ? (
            <div className="heat" role="img" aria-label="Detector score per moment">
              {bars.map((c, i) => <i key={i} title={`${c.score.toFixed(1)}× · ${c.outcome}`} className={c.outcome === "kept" ? "kept" : ""}
                style={{ height: `${Math.max(5, (c.score / maxScore) * 100)}%` }} />)}
            </div>
          ) : <p className="quiet">No detector data yet for this stream.</p>}
          <div className="legend" style={{ marginTop: 10 }}><span><i style={{ background: "var(--acc)" }} />kept as clip</span><span><i style={{ background: "#ffffff40" }} />scored moment</span></div>
        </section>
      </div>
    </>
  );
}

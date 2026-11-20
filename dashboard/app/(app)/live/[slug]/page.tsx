"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Avatar } from "@/components/Avatar";
import { ClipPlayer } from "@/components/ClipPlayer";
import { Countdown } from "@/components/Countdown";
import { Icon } from "@/components/Icon";
import { usePipeline } from "@/components/Pipeline";
import { mmss, rankQueue, streamerKeys } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { fmtViewers, liveClock, monthSpend, streamerViews } from "@/lib/view";

const STATE_LABEL: Record<string, string> = {
  pending_review: "in review", approved: "approved", revise: "revising", rejected: "denied",
  scheduled: "posting", published: "posted", failed: "post failed", qa_passed: "uploading",
};

/** Cinema live page (D049): opens when a streamer is clicked in the rail. */
export default function LivePage() {
  const { slug } = useParams<{ slug: string }>();
  const { snap, demo, setAwake } = useStore();
  const now = useNow(1000);
  const [view, setView] = useState<"stream" | "clip">("stream");
  const [host, setHost] = useState("");
  useEffect(() => setHost(window.location.hostname), []);
  const steps = usePipeline();

  const v = streamerViews(snap, now).find((x) => x.s.slug === slug);
  const keys = useMemo(() => (v ? streamerKeys(v.s) : []), [v]);
  const clips = useMemo(
    () => snap.clips.filter((c) => c.streamer_id === v?.s.id || keys.includes(c.channel_key))
      .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [snap.clips, v, keys],
  );
  const queue = rankQueue(clips);
  const cands = snap.candidates.filter((c) => keys.includes(c.channel_key));
  const spend = monthSpend(snap);

  if (!v) {
    return (
      <div className="cin missing">
        <p>No streamer called “{slug}”.</p>
        <Link href="/" className="btn light">Back to queue</Link>
      </div>
    );
  }

  const today = clips.filter((c) => Date.now() - Date.parse(c.created_at) < 86400_000);
  const approvedN = today.filter((c) => ["approved", "scheduled", "published"].includes(c.state)).length;
  const last = cands.slice(-48);
  const maxScore = Math.max(3, ...last.map((c) => c.score));
  const peak = last.reduce<typeof last[number] | null>((m, c) => (!m || c.score > m.score ? c : m), null);
  const line = last.map((c, i) => `${(i / Math.max(1, last.length - 1)) * 210},${80 - (c.score / maxScore) * 70}`).join(" ");
  const bars = cands.slice(-64);
  const embed = v.s.twitch_login
    ? `https://player.twitch.tv/?channel=${encodeURIComponent(v.s.twitch_login)}&parent=${host}&muted=true`
    : v.s.kick_slug ? `https://player.kick.com/${encodeURIComponent(v.s.kick_slug)}?muted=true` : null;

  return (
    <div className="cin">
      <div className="top">
        <div className="lg">
          <Link href="/" className="ci gl back" aria-label="Back to queue"><Icon name="back" /></Link>
          <Avatar s={v.s} live={v.live} size={32} />
          {v.s.display_name}
          <small>{v.live ? <><i />{v.key?.split(":")[0]} · {liveClock(v.since, now) || "live"}</> : "offline"}</small>
        </div>
        <div className="seg gl" role="tablist">
          <button type="button" role="tab" aria-selected={view === "stream"} className={view === "stream" ? "on" : ""} onClick={() => setView("stream")}>Stream view</button>
          <button type="button" role="tab" aria-selected={view === "clip"} className={view === "clip" ? "on" : ""} onClick={() => setView("clip")}>Clip view</button>
        </div>
        <button type="button" className="stop" onClick={() => void setAwake(!snap.control.awake)}>
          <i />{snap.control.awake ? "Sleep" : "Wake Up"}
        </button>
      </div>

      <div className="cin-grid">
        <div className="cin-left">
          <section className="gl hc">
            <h2>Chat heat</h2>
            {last.length > 1 ? (
              <svg viewBox="0 0 210 84" className="spark" aria-label="Detector score over time">
                <polyline points={`0,84 ${line} 210,84`} className="fill" />
                <polyline points={line} className="ln" />
              </svg>
            ) : <p className="quiet">No detector data yet for this stream.</p>}
            <div className="ft">{peak
              ? <>Peak {peak.score.toFixed(1)}× at {new Date(peak.moment_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</>
              : "Waiting for chat"}</div>
          </section>
          <section className="gl rq">
            <h2>Review queue <span className="cnt">{queue.length}</span></h2>
            {queue.slice(0, 3).map((c) => (
              <Link href="/" key={c.id} className="it">
                <span className="t"><b>{c.title ?? c.job_id}</b><span>{c.duration_s ? mmss(c.duration_s) : ""}</span></span>
                <span className="sc">{c.score_10 ?? "—"}</span>
              </Link>
            ))}
            {queue.length === 0 && <p className="quiet">Nothing from {v.s.display_name} waiting.</p>}
          </section>
        </div>

        <div className="cin-center">
          {view === "stream" ? (
            embed && v.live && !demo ? (
              <iframe className="embed" src={embed} title={`${v.s.display_name} live`} allowFullScreen
                sandbox="allow-scripts allow-same-origin allow-popups" />
            ) : (
              <div className="fig-wrap">
                <div className="arc" /><div className="arc o" /><div className="fig" />
                <p>{v.live ? (demo ? "Live player shows here outside demo mode" : "No player for this channel") : `${v.s.display_name} is offline`}</p>
              </div>
            )
          ) : (
            <ClipPlayer clip={clips[0] ?? null} autoPlay />
          )}
        </div>

        <div className="cin-right">
          <section className="dk pp">
            <h2>Pipeline</h2>
            <div className="steps">
              {steps.map((s) => (
                <div key={s.k} className={`s ${s.n ? "on" : ""}`}>
                  <b>{s.label}</b><span>{s.sub}</span><em>{s.n ? (s.k === "watch" ? "live" : s.n) : ""}</em>
                </div>
              ))}
            </div>
          </section>
          <section className="gl ks">
            <div><b>{fmtViewers(v.viewers) || "—"}</b><span>viewers</span></div>
            <div><b>{today.length}</b><span>clips today</span><em>{approvedN} approved</em></div>
            <div><b>${spend.total.toFixed(0)}</b><span>spend</span><em>this month</em></div>
          </section>
        </div>
      </div>

      <div className="cin-bottom">
        <section className="tl">
          <div className="h">
            <h2>Stream timeline</h2>
            <div><span>Moments <b>{cands.length}</b></span><span>Kept <b>{cands.filter((c) => c.outcome === "kept").length}</b></span>
              <span>Approved <b>{approvedN}/{today.length}</b></span></div>
          </div>
          <div className="bars" aria-label="Detector score per moment">
            {bars.map((c, i) => (
              <i key={i} title={`${c.score.toFixed(1)}× · ${c.outcome}`} className={c.outcome === "kept" ? "kept" : ""}
                style={{ height: `${Math.max(6, (c.score / maxScore) * 100)}%` }} />
            ))}
            {bars.length === 0 && <p className="quiet">The timeline fills in as the detector scores moments.</p>}
          </div>
        </section>
        <Countdown variant="dial" />
      </div>

      <div className="cl-row">
        {clips.slice(0, 6).map((c) => (
          <div key={c.id} className="cl">
            <div className="t">
              <b>{c.title ?? c.job_id}</b>
              <span>{c.duration_s ? `${mmss(c.duration_s)} · ` : ""}{STATE_LABEL[c.state] ?? c.state}</span>
              {c.state === "pending_review" ? <Link href="/" className="p">Review</Link>
                : <span className="p g">{STATE_LABEL[c.state] ?? c.state}</span>}
            </div>
            <span className="sc">{c.score_10 ?? "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

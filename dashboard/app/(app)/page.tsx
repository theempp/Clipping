"use client";
import { useEffect, useMemo, useState } from "react";
import { ApprovedList } from "@/components/ApprovedList";
import { Avatar } from "@/components/Avatar";
import { ClipPlayer } from "@/components/ClipPlayer";
import { Countdown } from "@/components/Countdown";
import { PipelineTiles } from "@/components/Pipeline";
import { ReviewDock } from "@/components/ReviewDock";
import { WakeToggle } from "@/components/WakeToggle";
import { PC_NAME } from "@/lib/env";
import { mmss, rankQueue } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { fmtViewers, liveClock, monthSpend, streamerViews } from "@/lib/view";

const HOOK: Record<string, string> = {
  surprising_fact: "Surprising fact", bold_claim: "Bold claim", story_start: "Story start",
  reaction_peak: "Reaction peak", play_peak: "Play peak", none: "No clear hook",
};
const BUDGET = 100;

export default function ReviewPage() {
  const { snap, pending } = useStore();
  const now = useNow(1000);
  const queue = useMemo(
    () => rankQueue(snap.clips).filter((c) => c.id !== pending?.clip.id),
    [snap.clips, pending],
  );
  const [selId, setSelId] = useState<string | null>(null);
  const clip: Clip | null = queue.find((c) => c.id === selId) ?? queue[0] ?? null;
  useEffect(() => { if (selId && !queue.some((c) => c.id === selId)) setSelId(null); }, [queue, selId]);

  const byId = new Map(snap.streamers.map((s) => [s.id, s]));
  const streamer = clip?.streamer_id ? byId.get(clip.streamer_id) : undefined;
  const sv = streamerViews(snap, now).find((v) => v.s.id === clip?.streamer_id);
  const pos = clip ? queue.indexOf(clip) + 1 : 0;
  const spend = monthSpend(snap);
  const why = typeof clip?.judge?.why === "string" ? clip.judge.why : null;
  const hookWin = typeof clip?.judge?.hook_window === "string" ? clip.judge.hook_window : "—";
  const openRev = snap.revisions.filter((r) => r.clip_id === clip?.id);

  return (
    <div className="stage">
      <div className="frame">
        <section className="hero" aria-label="Now reviewing">
          <div className="grain" />
          <div className="tl">
            {sv?.live
              ? <span className="pill"><i className="dot" />{streamer?.display_name} · live {liveClock(sv.since, now)}</span>
              : streamer && <span className="pill dk">{streamer.display_name} · offline</span>}
            {sv?.viewers != null && <span className="pill dk">{fmtViewers(sv.viewers)} watching</span>}
          </div>
          {clip ? (
            <div className="cap">
              <div className="k">NOW REVIEWING · {pos} OF {queue.length}
                {clip.duration_s ? ` · ${mmss(clip.duration_s)}` : ""} · 9:16{clip.revision ? ` · REV ${clip.revision}` : ""}</div>
              <h1>{clip.title ?? clip.job_id}</h1>
              {why && <p className="why">{why}</p>}
              <div className="m">
                {clip.hook_type && <span className="pill dk">{HOOK[clip.hook_type] ?? clip.hook_type}</span>}
                {clip.detector_score != null && <span className="pill dk">Chat spike {clip.detector_score.toFixed(1)}×</span>}
                {openRev[0] && <span className="pill dk" title={openRev[0].note}>Last note: {openRev[0].note}</span>}
              </div>
            </div>
          ) : (
            <div className="cap">
              <div className="k">QUEUE CLEAR</div>
              <h1>Nothing waiting for review.</h1>
              <p className="why">New clips show up here the moment the PC finishes rendering and QA.</p>
            </div>
          )}
          <ClipPlayer clip={clip} />
          <div className="score">
            <div className="n">{clip?.score_10 ?? "—"}</div>
            <div className="l">clip score / 10</div>
            <div className="ln">
              <div><span>Hook</span>{hookWin}</div>
              <div><span>Confidence</span>{clip?.confidence != null ? `${Math.round(clip.confidence * 100)}%` : "—"}</div>
              <div><span>Captions</span>{typeof clip?.qa?.captions === "string" ? clip.qa.captions : "whisperX"}</div>
              <div><span>QA</span>{clip ? (clip.qa?.passed === false ? "failed" : "passed") : "—"}</div>
            </div>
          </div>
        </section>
        <div className="notch-wake"><WakeToggle /></div>

        <div className="row">
          <div className="col-left">
            <PipelineTiles />
            <div className="pc">
              <span className="o">GPU</span>
              <div>
                <b>{PC_NAME} · {snap.heartbeat?.status.gpu?.name ?? "RTX 5060"}</b>
                <span>{snap.heartbeat?.status.version ? `worker ${snap.heartbeat.status.version}` : "worker not reporting"}</span>
              </div>
            </div>
          </div>

          <section className="cd next" aria-label="Up next">
            <div className="h"><span>Up next</span><span className="ct">{Math.max(0, queue.length - 1)}</span></div>
            <ul>
              {queue.filter((c) => c.id !== clip?.id).slice(0, 5).map((c) => {
                const s = c.streamer_id ? byId.get(c.streamer_id) : undefined;
                return (
                  <li key={c.id}>
                    <button type="button" onClick={() => setSelId(c.id)}>
                      {s && <Avatar s={s} size={28} />}
                      <span className="t"><b>{c.title ?? c.job_id}</b>
                        <span>{s?.display_name ?? c.channel_key}{c.duration_s ? ` · ${mmss(c.duration_s)}` : ""}</span></span>
                      <span className="sc">{c.score_10 ?? "—"}</span>
                    </button>
                  </li>
                );
              })}
              {queue.length <= 1 && <li className="quiet">Nothing behind this one.</li>}
            </ul>
          </section>

          <Countdown />

          <section className="cd sp" aria-label="Spend this month">
            <div className="h"><span>Spend · {new Date().toLocaleString([], { month: "short" })}</span><span className="pill-sm">Budget ${BUDGET}</span></div>
            <div className="lt">${spend.total.toFixed(0)}</div>
            <div className="bar"><i style={{ right: `${100 - Math.min(100, (spend.grok / BUDGET) * 100)}%` }} />
              <em>Grok ${spend.grok.toFixed(0)}</em><span>${BUDGET}</span></div>
          </section>
        </div>
        <ReviewDock clip={clip} />
      </div>
      <ApprovedList />
      <div className="rays" aria-hidden="true" />
    </div>
  );
}

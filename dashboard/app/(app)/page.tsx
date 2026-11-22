"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ApprovedList } from "@/components/ApprovedList";
import { Avatar } from "@/components/Avatar";
import { BeforeAfter } from "@/components/BeforeAfter";
import { LearnedRules } from "@/components/LearnedRules";
import { Countdown } from "@/components/Countdown";
import { Icon } from "@/components/Icon";
import { PipelineTiles } from "@/components/Pipeline";
import { ReviewDock } from "@/components/ReviewDock";
import { TikTokPanel, tagLine } from "@/components/TikTokPanel";
import { WakeToggle } from "@/components/WakeToggle";
import { WeekPulse } from "@/components/WeekPulse";
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
  // A picked clip that leaves the queue (approve/deny) falls back to the top one; Undo brings it back into view.

  const byId = new Map(snap.streamers.map((s) => [s.id, s]));
  const streamer = clip?.streamer_id ? byId.get(clip.streamer_id) : undefined;
  const views = streamerViews(snap, now);
  const sv = views.find((v) => v.s.id === clip?.streamer_id);
  const liveN = views.filter((v) => v.live && v.inRoster).length;
  const pos = clip ? queue.indexOf(clip) + 1 : 0;
  const spend = monthSpend(snap);
  const why = typeof clip?.judge?.why === "string" ? clip.judge.why : null;
  const hookWin = typeof clip?.judge?.hook_window === "string" ? clip.judge.hook_window : "—";
  const openRev = snap.revisions.filter((r) => r.clip_id === clip?.id);
  const score = clip?.score_10 ?? null;
  const spendPct = Math.min(100, (spend.total / BUDGET) * 100);
  const long = clip?.category === "longform" ? snap.longform.find((v) => v.clip_id === clip.id) : undefined;

  return (
    <div className="rv">
      <header className="ptop">
        <div className="pt-l">
          <h1>Review</h1>
          <span className="lbl">{queue.length ? `${queue.length} waiting` : "queue clear"} · {liveN} streamer{liveN === 1 ? "" : "s"} live</span>
        </div>
        <WakeToggle />
      </header>

      <section className="card hero" aria-label="Now reviewing">
        <div className="hero-info">
          <div className="hero-k">
            {clip
              ? <span className="lbl">Now reviewing · {pos} of {queue.length}{clip.duration_s ? ` · ${mmss(clip.duration_s)}` : ""} · 9:16{clip.revision ? ` · rev ${clip.revision}` : ""}</span>
              : <span className="lbl">Queue clear</span>}
            {streamer && (
              <Link href={`/live/${streamer.slug}`} className={`chip${sv?.live ? " live" : ""}`}>
                {sv?.live && <i className="dot" />}
                {streamer.display_name}{sv?.live ? ` · live ${liveClock(sv.since, now)}` : " · offline"}
                {sv?.live && sv.viewers != null ? ` · ${fmtViewers(sv.viewers)}` : ""}
              </Link>
            )}
          </div>
          <h2 key={clip?.id ?? "none"} className="hero-t">{clip ? clip.title ?? clip.job_id : "Nothing waiting for review."}</h2>
          <p className="why">{clip ? why ?? "No judge note for this clip." : "New clips show up here the moment the PC finishes rendering and QA."}</p>
          {clip && (
            <div className="chips">
              {long && <span className="chip">TikTok · Zwoclipp</span>}
              {long && tagLine(long).map((t) => <span key={t} className="chip">{t}</span>)}
              {!long && clip.hook_type && <span className="chip">{HOOK[clip.hook_type] ?? clip.hook_type}</span>}
              {clip.detector_score != null && <span className="chip">Chat spike {clip.detector_score.toFixed(1)}×</span>}
              {openRev[0] && <span className="chip note" title={openRev[0].note}>Last note: {openRev[0].note}</span>}
            </div>
          )}

        </div>
        <div className="hero-media">
          <BeforeAfter clip={clip}>
              <div className="scorebox">
                <div className="big" aria-label={`Clip score ${score ?? "none"} out of 10`}>
                  <svg viewBox="0 0 64 64" aria-hidden="true">
                    <defs>
                      <linearGradient id="g-score" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0" stopColor="var(--lime)" /><stop offset=".5" stopColor="var(--mint)" /><stop offset="1" stopColor="var(--cyan)" />
                      </linearGradient>
                    </defs>
                    <circle cx="32" cy="32" r="28" className="trk" />
                    <circle key={clip?.id ?? "none"} cx="32" cy="32" r="28" className="val" stroke="url(#g-score)"
                      strokeDasharray={`${((score ?? 0) / 10) * 175.9} 175.9`} />
                  </svg>
                  <b>{score ?? "—"}</b>
                  <span>out of 10</span>
                </div>
                <dl className="metrics">
                  <div><dt>Hook</dt><dd>{hookWin}</dd></div>
                  <div><dt>Confidence</dt><dd>{clip?.confidence != null ? `${Math.round(clip.confidence * 100)}%` : "—"}</dd>
                    <span className="prob" aria-hidden="true"><i key={clip?.id ?? "none"} style={{ width: `${Math.round((clip?.confidence ?? 0) * 100)}%` }} /></span></div>
                  <div><dt>Captions</dt><dd>{typeof clip?.qa?.captions === "string" ? clip.qa.captions : clip ? "whisperX" : "—"}</dd></div>
                  <div><dt>QA</dt><dd className={clip?.qa?.passed === false ? "bad" : clip ? "ok" : ""}>{clip ? (clip.qa?.passed === false ? "failed" : "passed") : "—"}</dd></div>
                </dl>
              </div>

              <ReviewDock clip={clip} />
          </BeforeAfter>
        </div>
      </section>

      <section className="card next" aria-label="Up next">
        <div className="card-h"><h2>Up next <span className="ct">{Math.max(0, queue.length - 1)}</span></h2><span className="lbl">best first</span></div>
        <ul>
          {queue.filter((c) => c.id !== clip?.id).slice(0, 6).map((c) => {
            const s = c.streamer_id ? byId.get(c.streamer_id) : undefined;
            return (
              <li key={c.id}>
                <button type="button" onClick={() => setSelId(c.id)}>
                  {s ? <Avatar s={s} size={32} /> : <span className="av-ph" />}
                  <span className="tx"><b>{c.title ?? c.job_id}</b>
                    <span>{s?.display_name ?? c.channel_key}{c.duration_s ? ` · ${mmss(c.duration_s)}` : ""}</span></span>
                  <span className="sc">{c.score_10 ?? "—"}</span>
                </button>
              </li>
            );
          })}
        </ul>
        {queue.length <= 1 && <p className="quiet">Nothing behind this one.</p>}
        <LearnedRules />
      </section>

      <WeekPulse />

      <div className="strip3">
        <PipelineTiles />
        <Countdown />
        <section className="card spend" aria-label="Spend this month">
          <div className="card-h"><h2>Spend · {new Date().toLocaleString([], { month: "short" })}</h2><span className="lbl">budget ${BUDGET}</span></div>
          <div className="sp-n"><b>${spend.total.toFixed(0)}</b><span>of ${BUDGET}</span></div>
          <div className="meter" aria-hidden="true"><i style={{ width: `${spendPct}%` }} /></div>
          <div className="sp-l">
            <span><i className="k-grok" />Grok ${spend.grok.toFixed(0)}</span>
            <span><i className="k-other" />Other ${(spend.total - spend.grok).toFixed(0)}</span>
          </div>
        </section>
      </div>

      <ApprovedList />
      <TikTokPanel />
      <p className="keys" aria-hidden="true"><Icon name="bolt" /> Keys: <kbd>A</kbd> approve · <kbd>D</kbd> deny · <kbd>R</kbd> revise · <kbd>U</kbd> undo</p>
    </div>
  );
}

"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useMemo } from "react";
import { ApprovedList } from "@/components/ApprovedList";
import { BeforeAfter } from "@/components/BeforeAfter";
import { Ring } from "@/components/Charts";
import { ClipVideo } from "@/components/ClipCard";
import { Icon } from "@/components/Icon";
import { LearnedRules } from "@/components/LearnedRules";
import { LinkBox } from "@/components/LinkBox";
import { PodChip } from "@/components/PodChip";
import { ReviewDock } from "@/components/ReviewDock";
import { TikTokPanel, tagLine } from "@/components/TikTokPanel";
import { WeekPulse } from "@/components/WeekPulse";
import { mmss, rankQueue } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import type { Clip } from "@/lib/types";
import { fmtViewers, liveFor, streamerViews } from "@/lib/view";

const HOOK: Record<string, string> = {
  surprising_fact: "Surprising fact", bold_claim: "Bold claim", story_start: "Story start",
  reaction_peak: "Reaction peak", play_peak: "Play peak", none: "No clear hook",
};

export default function ReviewPage() {
  return <Suspense fallback={<div className="loading">Loading…</div>}><Review /></Suspense>;
}

function Review() {
  const { snap, pending } = useStore();
  const now = useNow(1000);
  const params = useSearchParams();
  const router = useRouter();
  const queue = useMemo(() => rankQueue(snap.clips).filter((c) => c.id !== pending?.clip.id), [snap.clips, pending]);
  const selId = params.get("clip");
  const clip: Clip | null = queue.find((c) => c.id === selId) ?? queue[0] ?? null;
  const pick = (id: string) => router.replace(`/review?clip=${id}`, { scroll: false });

  const byId = new Map(snap.streamers.map((s) => [s.id, s]));
  const streamer = clip?.streamer_id ? byId.get(clip.streamer_id) : undefined;
  const sv = streamerViews(snap, now).find((v) => v.s.id === clip?.streamer_id);
  const pos = clip ? queue.indexOf(clip) + 1 : 0;
  const why = typeof clip?.judge?.why === "string" ? clip.judge.why : null;
  const hookWin = typeof clip?.judge?.hook_window === "string" ? clip.judge.hook_window : "—";
  const lastNote = snap.revisions.find((r) => r.clip_id === clip?.id);
  const long = clip?.category === "longform" ? snap.longform.find((v) => v.clip_id === clip.id) : undefined;

  return (
    <>
      <section className="hero" style={{ marginBottom: 28 }}>
        <div>
          <h1>Review<br /><b>{queue.length ? `${queue.length} waiting` : "Queue clear"}</b></h1>
          <p>Best first: judge score, then confidence, then oldest. Approve and deny wait 4 seconds so you can undo.</p>
        </div>
      </section>

      <div className="rvw">
        <div className="rv-main">
          <section className="glass" aria-label="Now reviewing">
            <div className="hd">
              <span className="mut" style={{ fontSize: 12 }}>
                {clip ? <>Now reviewing · {pos} of {queue.length}{clip.duration_s ? ` · ${mmss(clip.duration_s)}` : ""} · 9:16{clip.revision ? ` · rev ${clip.revision}` : ""}</> : "Queue clear"}
              </span>
              {streamer && (
                <Link href={`/streamers/${streamer.slug}`} className={`chip${sv?.live ? " acc" : ""}`}>
                  {streamer.display_name}{sv?.live ? ` · live ${liveFor(sv.since, now)}` : " · offline"}
                  {sv?.live && sv.viewers != null ? ` · ${fmtViewers(sv.viewers)}` : ""}
                </Link>
              )}
            </div>
            <h2 style={{ font: "600 26px/1.2 var(--fd)", letterSpacing: "-.02em", margin: "0 0 8px" }}>{clip ? clip.title ?? clip.job_id : "Nothing waiting for review."}</h2>
            <p className="mut" style={{ margin: "0 0 12px" }}>{clip ? why ?? "No judge note for this clip." : "New clips show up here the moment the PC finishes rendering and QA."}</p>
            {clip && (
              <div className="chips" style={{ marginBottom: 16 }}>
                <PodChip clip={clip} />
                {long && <span className="chip acc">TikTok · Zwoclipp</span>}
                {long && tagLine(long).map((t) => <span key={t} className="chip">{t}</span>)}
                {!long && clip.hook_type && <span className="chip">{HOOK[clip.hook_type] ?? clip.hook_type}</span>}
                {clip.detector_score != null && <span className="chip">Chat spike {clip.detector_score.toFixed(1)}×</span>}
                {lastNote && <span className="chip warn" title={lastNote.note}>Last note: {lastNote.note}</span>}
                <Link className="chip" href={`/editor?clip=${clip.id}`}><Icon name="film" size={12} /> Open in editor</Link>
              </div>
            )}
            <BeforeAfter clip={clip}>
              <div className="scorebox">
                <Ring pct={((clip?.score_10 ?? 0) / 10) * 100} size={96} w={8} text={clip?.score_10 != null ? String(clip.score_10) : "—"}
                  label={`Clip score ${clip?.score_10 ?? "none"} out of 10`} />
                <dl className="metrics">
                  <div><dt>Hook</dt><dd>{hookWin}</dd></div>
                  <div><dt>Confidence</dt><dd>{clip?.confidence != null ? `${Math.round(clip.confidence * 100)}%` : "—"}</dd></div>
                  <div><dt>Captions</dt><dd>{typeof clip?.qa?.captions === "string" ? clip.qa.captions : clip ? "whisperX" : "—"}</dd></div>
                  <div><dt>QA</dt><dd className={clip?.qa?.passed === false ? "bad" : clip ? "ok" : ""}>{clip ? (clip.qa?.passed === false ? "failed" : "passed") : "—"}</dd></div>
                </dl>
              </div>
              <ReviewDock key={clip?.id ?? "none"} clip={clip} startOpen={params.get("revise") === "1"} />
            </BeforeAfter>
          </section>
          <WeekPulse />
        </div>

        <aside className="stack">
          <LinkBox />
          <section className="glass" aria-label="Up next">
            <div className="hd"><h3>Up next <span className="mut">· {Math.max(0, queue.length - 1)}</span></h3><span className="r">best first</span></div>
            <ul className="nextlist">
              {queue.filter((c) => c.id !== clip?.id).slice(0, 8).map((c) => {
                const s = c.streamer_id ? byId.get(c.streamer_id) : undefined;
                return (
                  <li key={c.id}>
                    <button type="button" onClick={() => pick(c.id)}>
                      <span className="mini"><ClipVideo clip={c} sound={false} /></span>
                      <span className="tx"><b>{c.title ?? c.job_id}</b><span>{s?.display_name ?? c.channel_key}{c.duration_s ? ` · ${mmss(c.duration_s)}` : ""}</span></span>
                      <PodChip clip={c} />
                      <span className="sc">{c.score_10 ?? "—"}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {queue.length <= 1 && <p className="quiet">Nothing behind this one.</p>}
            <LearnedRules />
          </section>
          <ApprovedList />
          <p className="keys" aria-hidden="true"><Icon name="bolt" /> Keys: <kbd>A</kbd> approve · <kbd>D</kbd> deny · <kbd>R</kbd> revise · <kbd>U</kbd> undo · <kbd>/</kbd> search</p>
        </aside>
      </div>

      <div style={{ marginTop: 18 }}><TikTokPanel /></div>
    </>
  );
}

"use client";
import { useMemo } from "react";
import { weekStats } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";
import { Icon } from "./Icon";

/** This week at a glance: approve streak, 7-day clip pills, approval rate and average score. */
export function WeekPulse() {
  const { snap } = useStore();
  const now = useNow(60_000);
  const w = useMemo(() => weekStats(snap.clips, now), [snap.clips, now]);
  const max = Math.max(1, ...w.days.map((d) => d.made));
  const rate = w.approvalRate == null ? null : Math.round(w.approvalRate * 100);
  return (
    <section className="card pulse" aria-label="This week">
      <div className="streak">
        <span className="flame" aria-hidden="true"><Icon name="flame" /></span>
        <b className="gnum">{w.streak}</b>
        <span>day approve streak</span>
      </div>
      <ol className="days" aria-label="Clips per day, last 7 days">
        {w.days.map((d) => (
          <li key={d.key} className={`${d.today ? "today" : ""}${d.approved ? " hit" : ""}`}
            title={`${d.made} clip${d.made === 1 ? "" : "s"}, ${d.approved} approved`}>
            <span className="dl">{d.label}</span>
            <span className="dbar" aria-hidden="true"><i style={{ height: `${Math.max(8, (d.made / max) * 100)}%` }} /></span>
            <span className="dn">{d.day}</span>
            <span className="sr-only">{d.made} clips, {d.approved} approved</span>
          </li>
        ))}
      </ol>
      <dl className="pstats">
        <div><dt><Icon name="trophy" /> Approved · 7d</dt><dd className="gnum">{w.approved7}</dd></div>
        <div><dt><Icon name="target" /> Approval rate</dt><dd className="gnum">{rate == null ? "—" : `${rate}%`}</dd>
          <span className="prob" aria-hidden="true"><i style={{ width: `${rate ?? 0}%` }} /></span></div>
        <div><dt><Icon name="bolt" /> Avg score</dt><dd className="gnum">{w.avgScore == null ? "—" : w.avgScore.toFixed(1)}</dd></div>
      </dl>
    </section>
  );
}

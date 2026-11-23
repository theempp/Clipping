"use client";
import { useMemo } from "react";
import { weekStats } from "@/lib/logic";
import { useNow, useStore } from "@/lib/store";

/** This week at a glance: approve streak, 7-day clip bars, approval rate and average score. */
export function WeekPulse() {
  const { snap } = useStore();
  const now = useNow(60_000);
  const w = useMemo(() => weekStats(snap.clips, now), [snap.clips, now]);
  const max = Math.max(1, ...w.days.map((d) => d.made));
  const rate = w.approvalRate == null ? null : Math.round(w.approvalRate * 100);
  return (
    <section className="glass" aria-label="This week">
      <div className="hd"><h3>This week</h3><span className="r">{w.streak} day approve streak</span></div>
      <ol className="days" aria-label="Clips per day, last 7 days">
        {w.days.map((d) => (
          <li key={d.key} className={`${d.today ? "today" : ""}${d.approved ? " hit" : ""}`}
            title={`${d.made} clip${d.made === 1 ? "" : "s"}, ${d.approved} approved`}>
            <span className="dbar" aria-hidden="true"><i style={{ height: `${Math.max(8, (d.made / max) * 100)}%` }} /></span>
            <span className="dn">{d.label} {d.day}</span>
            <span className="sr-only">{d.made} clips, {d.approved} approved</span>
          </li>
        ))}
      </ol>
      <div className="kv" style={{ marginTop: 14, gridTemplateColumns: "repeat(3, minmax(0,1fr))" }}>
        <div><b>{w.approved7}</b><span>approved · 7d</span></div>
        <div><b>{rate == null ? "—" : `${rate}%`}</b><span>approval rate</span></div>
        <div><b>{w.avgScore == null ? "—" : w.avgScore.toFixed(1)}</b><span>avg score</span></div>
      </div>
    </section>
  );
}
